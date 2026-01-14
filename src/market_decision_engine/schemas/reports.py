"""レポート（Report / ShortSummary）の契約定義。

設計意図:
- decision の数値・シグナルを改変しない「表現層」の契約を固定する。
- LLM は翻訳・要約のみ。数値生成・判断基準の追加は禁止（監査対象）。
- M1 は JSON/Markdown 出力の最小要件として、ShortSummary と Report を用意する。
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class SummarySource(str, Enum):
    """要約テキストの生成元（監査・追跡用）。"""

    TEMPLATE = "TEMPLATE"  # LLM 失敗時などのフォールバック
    LLM = "LLM"  # 翻訳・要約を LLM が生成
    HUMAN = "HUMAN"  # 手動編集（将来想定）


class ShortSummary(BaseModel):
    """EOD 実行1回分の短い総評（数値を作らない）。"""

    source: SummarySource = Field(..., description="Summary source")
    text: str = Field(..., min_length=1, description="Short summary text (no new numbers/rules)")
    warnings: list[str] = Field(default_factory=list, description="Warnings (e.g., degraded mode)")

    class Config:
        frozen = True


class ReportFormat(str, Enum):
    """レポートの表現形式（出力モジュール選択用）。"""

    JSON = "JSON"
    MARKDOWN = "MARKDOWN"


class Report(BaseModel):
    """EOD 出力のレポート契約（DecisionPack を包む）。"""

    market: str = Field(..., min_length=1, description="Market identifier (e.g., JP/US)")
    asof: date = Field(..., description="EOD date")
    run_id: str = Field(..., min_length=1, description="Run identifier")

    # 参照元（decision の出力）をそのまま内包する前提
    decision_pack: dict[str, Any] = Field(
        ...,
        description="Serialized DecisionPack (must be generated from schemas/decision.py objects)",
    )

    short_summary: ShortSummary | None = Field(
        None, description="Optional short summary (LLM may generate; must not change numbers)"
    )

    format: ReportFormat = Field(ReportFormat.JSON, description="Preferred report format")
    generated_at: str = Field(
        ...,
        min_length=1,
        description="Generation timestamp (ISO8601 string). Kept as str to avoid timezone policy in M1.",
    )

    class Config:
        frozen = True

    @model_validator(mode="after")
    def _validate_pack_identity(self) -> "Report":
        # decision_pack は辞書で受ける（M1では循環import回避・シリアライズ境界を明確化）
        pack = self.decision_pack
        if not isinstance(pack, dict):
            raise ValueError("decision_pack must be a dict (serialized DecisionPack).")
        for k in ("market", "asof", "run_id", "decisions"):
            if k not in pack:
                raise ValueError(f"decision_pack missing key: {k}")

        # 一致性チェック（外部整形でズレたら即検知）
        if str(pack.get("market")) != str(self.market):
            raise ValueError("decision_pack.market must match report.market.")
        if pack.get("asof") != self.asof:
            raise ValueError("decision_pack.asof must match report.asof.")
        if str(pack.get("run_id")) != str(self.run_id):
            raise ValueError("decision_pack.run_id must match report.run_id.")

        return self
