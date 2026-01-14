# src/market_decision_engine/reports/json_report.py
"""JSON レポート生成（表現層）。

設計意図:
- DecisionPack（数値・判断）を改変せず、そのままシリアライズして Report に包む。
- LLM は使わない（M1）。必要ならテンプレ short_summary を付与するのみ。
- 出力（ファイル保存などの I/O）はここでは行わない。呼び出し側に委譲する。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from market_decision_engine.pipeline.context import EngineContext
from market_decision_engine.schemas.decision import DecisionPack
from market_decision_engine.schemas.reports import (
    Report,
    ReportFormat,
    ShortSummary,
    SummarySource,
)


def build_report(ctx: EngineContext, pack: DecisionPack, skipped: list[str]) -> Report:
    """DecisionPack を JSON レポート（Report）として返す。

    Args:
        ctx: 実行文脈（degraded や notes を参照する）。
        pack: 意思決定パック（schemas/decision.py）。
        skipped: スキップされた銘柄一覧。

    Returns:
        Report: `schemas/reports.py` 契約に従う Report（format=JSON）。
    """
    decision_pack = _serialize_decision_pack(pack, skipped=skipped, ctx=ctx)

    short_summary: ShortSummary | None = None
    if ctx.degraded:
        short_summary = ShortSummary(
            source=SummarySource.TEMPLATE,
            text="Degraded mode: some steps were skipped or reduced for safety.",
            warnings=_build_warnings(ctx),
        )

    return Report(
        market=str(getattr(ctx.run, "market")),
        asof=ctx.run.asof,
        run_id=str(getattr(ctx.run, "run_id")),
        decision_pack=decision_pack,
        short_summary=short_summary,
        format=ReportFormat.JSON,
        generated_at=_now_iso_seconds(),
    )


def _serialize_decision_pack(pack: DecisionPack, *, skipped: list[str], ctx: EngineContext) -> dict[str, Any]:
    """DecisionPack を Python dict としてシリアライズする（date は date のまま保持）。

    注意:
    - `schemas/reports.Report` 側で asof の一致検証があるため、json mode ではなく
      python mode（model_dump デフォルト）で date を date のまま保持する。
    """
    data = pack.model_dump()

    # レポート都合のメタは追加してよい（DecisionCore の数値は改変しない）
    include_skipped = bool(ctx.config.get("include_skipped", True))
    if include_skipped:
        data["skipped_symbols"] = list(skipped)

    # 診断情報（任意）。必要なら出力側で落とせる
    data["degraded"] = bool(ctx.degraded)
    data["notes"] = dict(ctx.notes)

    return data


def _build_warnings(ctx: EngineContext) -> list[str]:
    """縮退時の警告を生成する（テンプレ）。"""
    warnings: list[str] = []
    reasons = ctx.notes.get("degraded_reasons")
    if isinstance(reasons, list):
        for r in reasons:
            if isinstance(r, str) and r.strip():
                warnings.append(r.strip())
    if not warnings:
        warnings.append("Pipeline ran in degraded mode.")
    return warnings


def _now_iso_seconds() -> str:
    """ISO8601 文字列（秒粒度）。タイムゾーン方針は M1 では固定しない。"""
    return datetime.now().isoformat(timespec="seconds")
