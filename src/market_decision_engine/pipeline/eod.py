"""EOD 一方向パイプライン（オーケストレーション）。

設計意図:
- 手続き（Step の順序）をここで固定し、各 Step の中身は別モジュールへ委譲する。
- 依存（universe/data/features/selection/...）は services（関数群）として注入し、
  段階リリース（M1→M9）や将来 API 化でも差し替えしやすくする。
- 例外分類（Fatal/Degraded/Skip）に従って、停止・縮退・銘柄スキップを一貫して扱う。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from market_decision_engine.exceptions import (
    ContractViolation,
    DegradedError,
    FatalError,
    MarketDecisionEngineError,
    SkipSymbol,
)
from market_decision_engine.pipeline.context import EngineContext
from market_decision_engine.schemas.decision import DecisionCore, DecisionPack
from market_decision_engine.schemas.reports import Report


# -------------------------
# Service contracts (DI)
# -------------------------


@dataclass(frozen=True)
class PipelineServices:
    """パイプラインが呼び出す機能群（依存注入）。

    各関数は「I/O を局所化」したモジュールから提供される想定。
    eod.py は関数を呼び出して順番を制御するだけ。
    """

    build_universe: Callable[[EngineContext], list[str]]

    # data load / preprocess
    load_ohlcv: Callable[[EngineContext, str], Any]
    preprocess_ohlcv: Callable[[EngineContext, str, Any], Any]

    # features
    build_daily_features: Callable[[EngineContext, str, Any], Any]
    build_static_features: Callable[[EngineContext, str], Any] | None = None
    build_fundamental_features: Callable[[EngineContext, str], Any] | None = None

    # selection / ranking
    select_candidates: Callable[[EngineContext, dict[str, Any]], list[str]] | None = None
    rank_candidates: Callable[[EngineContext, dict[str, Any], list[str]], list[str]] | None = None

    # plan / execution / decision
    decide_for_symbol: Callable[[EngineContext, str, dict[str, Any]], DecisionCore] | None = None

    # report
    build_report: Callable[[EngineContext, DecisionPack, list[str]], Report] | None = None


# -------------------------
# Helpers
# -------------------------


def _ctx_with_note(ctx: EngineContext, key: str, value: Any) -> EngineContext:
    """EngineContext は frozen なので、notes を更新した新インスタンスを返す。"""
    notes = dict(ctx.notes)
    notes[key] = value
    return ctx.model_copy(update={"notes": notes})


def _ctx_mark_degraded(ctx: EngineContext, reason: str) -> EngineContext:
    """縮退運転フラグを立て、理由を notes に残した新インスタンスを返す。"""
    notes = dict(ctx.notes)
    reasons = list(notes.get("degraded_reasons", []))
    reasons.append(reason)
    notes["degraded_reasons"] = reasons
    return ctx.model_copy(update={"degraded": True, "notes": notes})


def _require(fn: Callable[..., Any] | None, name: str) -> Callable[..., Any]:
    """必須 service の欠落を起動時に検知する。"""
    if fn is None:
        raise ContractViolation(f"Missing required service: {name}")
    return fn


# -------------------------
# Public API
# -------------------------Any


def run(ctx: EngineContext, services: PipelineServices) -> Report | Any:
    """EOD パイプラインを実行し、Report を返す。

    Args:
        ctx: `pipeline/context.py` で生成された実行文脈。
        services: 各 Step の実装（依存注入）。

    Returns:
        Report: `schemas/reports.py` 契約に従うレポート。

    Raises:
        FatalError: バッチ停止が必要な致命的障害。
        ContractViolation: 契約逸脱（原則 Fatal）。
        MarketDecisionEngineError: その他、分類済み例外。
    """
    build_universe = _require(services.build_universe, "build_universe")
    load_ohlcv = _require(services.load_ohlcv, "load_ohlcv")
    preprocess_ohlcv = _require(services.preprocess_ohlcv, "preprocess_ohlcv")
    build_daily_features = _require(services.build_daily_features, "build_daily_features")

    decide_for_symbol = _require(services.decide_for_symbol, "decide_for_symbol")
    build_report = _require(services.build_report, "build_report")

    # 1) Universe
    symbols = build_universe(ctx)
    if not symbols:
        raise FatalError("Universe is empty.")

    ctx = _ctx_with_note(ctx, "universe_size", len(symbols))

    # 2) Per-symbol: data -> preprocess -> daily features
    per_symbol: dict[str, Any] = {}
    skipped: list[str] = []
    degraded_reasons: list[str] = []

    for sym in symbols:
        try:
            raw = load_ohlcv(ctx, sym)
            clean = preprocess_ohlcv(ctx, sym, raw)
            daily_feat = build_daily_features(ctx, sym, clean)
            per_symbol[sym] = {
                "ohlcv": clean,
                "daily": daily_feat,
            }
        except SkipSymbol:
            skipped.append(sym)
            continue
        except DegradedError as e:
            # 銘柄単位の縮退: 可能ならスキップ/縮退で継続
            degraded_reasons.append(str(e))
            skipped.append(sym)
            continue
        except MarketDecisionEngineError:
            # 分類済みはそのまま上げる（停止/縮退は上位で扱う）
            raise
        except Exception as e:  # noqa: BLE001
            # 未分類例外は致命的として扱う（契約外のため）
            raise FatalError(f"Unhandled exception in feature stage: {e}") from e

    if degraded_reasons:
        ctx = _ctx_mark_degraded(ctx, "feature_stage_degraded")

    ctx = _ctx_with_note(ctx, "skipped_symbols", skipped)
    ctx = _ctx_with_note(ctx, "feature_ready_symbols", len(per_symbol))

    if not per_symbol:
        raise FatalError("No symbols available after preprocessing/feature generation.")

    # 3) Candidate selection / ranking（未提供なら universe 全体を候補とする）
    candidate_symbols: list[str]
    if services.select_candidates is None:
        candidate_symbols = list(per_symbol.keys())
    else:
        candidate_symbols = services.select_candidates(ctx, per_symbol)

    if services.rank_candidates is not None:
        candidate_symbols = services.rank_candidates(ctx, per_symbol, candidate_symbols)

    if not candidate_symbols:
        raise FatalError("Candidate list is empty.")

    ctx = _ctx_with_note(ctx, "candidate_size", len(candidate_symbols))

    # 4) Decision（plan/execution/decision を一括で委譲）
    decisions: list[DecisionCore] = []
    for sym in candidate_symbols:
        if sym not in per_symbol:
            # select/rank が per_symbol 外を返した場合は契約違反
            raise ContractViolation("Candidate symbol not found in per_symbol feature map.")

        try:
            decision = decide_for_symbol(ctx, sym, per_symbol[sym])
            decisions.append(decision)
        except SkipSymbol:
            skipped.append(sym)
            continue
        except DegradedError as e:
            ctx = _ctx_mark_degraded(ctx, f"decision_stage_degraded: {e}")
            skipped.append(sym)
            continue
        except MarketDecisionEngineError:
            raise
        except Exception as e:  # noqa: BLE001
            raise FatalError(f"Unhandled exception in decision stage: {e}") from e

    # 5) Pack -> Report
    pack = DecisionPack(
        market=str(getattr(ctx.run, "market")),
        asof=ctx.run.asof,
        run_id=str(getattr(ctx.run, "run_id")),
        decisions=decisions,
    )

    report = build_report(ctx, pack, skipped)
    return report
