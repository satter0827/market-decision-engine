"""パイプライン実行文脈（RunContext）の組み立て。

設計意図:
- entrypoints（CLI/API）から渡された「契約オブジェクト」を、パイプライン内部で使う
  単一の実行文脈に正規化して固定する。
- pipeline はこの文脈のみを信頼し、外部 I/O や環境依存の取得をここに混入させない。
- 縮退運転（degraded）をここで表現できるようにし、後段の例外処理を単純化する。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from market_decision_engine.exceptions import ConfigurationError
from market_decision_engine.schemas.market import RunContext
from market_decision_engine.schemas.policy import PolicySnapshot


class EngineContext(BaseModel):
    """EOD パイプラインが参照する実行文脈（不変）。"""

    run: RunContext = Field(..., description="RunContext (market/asof/run_id)")
    policy: PolicySnapshot = Field(..., description="Policy snapshot for this run")

    # 設定は「解釈済み・正規化済み」を前提とする（resolver の出力を想定）
    config: dict[str, Any] = Field(default_factory=dict, description="Resolved config (normalized)")

    # 縮退運転フラグ（例: LLM/ML 不調、データ品質低下など）
    degraded: bool = Field(False, description="Whether pipeline runs in degraded mode")

    # 監査・デバッグ用の付帯情報（ログの材料）。値の意味は固定せず、keys を運用で統一。
    notes: dict[str, Any] = Field(default_factory=dict, description="Diagnostic notes")

    class Config:
        frozen = True


def build_engine_context(
    run: RunContext,
    policy: PolicySnapshot,
    *,
    config: dict[str, Any] | None = None,
    degraded: bool = False,
    notes: dict[str, Any] | None = None,
) -> EngineContext:
    """RunContext と PolicySnapshot から EngineContext を生成する。

    Args:
        run: `schemas/market.py` の RunContext。
        policy: `schemas/policy.py` の PolicySnapshot。
        config: resolver 済み設定（正規化済み dict）。未指定なら空 dict。
        degraded: 縮退運転フラグ。
        notes: 任意の診断情報。

    Returns:
        EngineContext: パイプライン内部で参照する不変文脈。

    Raises:
        ConfigurationError: run と policy の整合が取れない場合。
    """
    if policy.asof != run.asof:
        raise ConfigurationError("PolicySnapshot.asof must match RunContext.asof.")

    merged_config: dict[str, Any] = dict(config or {})
    merged_notes: dict[str, Any] = dict(notes or {})

    # 追跡上有用な最低限のメタを notes に寄せる（本体契約は崩さない）
    merged_notes.setdefault("market", getattr(run, "market", None))
    merged_notes.setdefault("asof", run.asof)
    merged_notes.setdefault("run_id", getattr(run, "run_id", None))

    return EngineContext(
        run=run,
        policy=policy,
        config=merged_config,
        degraded=degraded,
        notes=merged_notes,
    )
