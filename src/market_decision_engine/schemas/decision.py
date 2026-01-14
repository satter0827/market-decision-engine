"""意思決定（Decision）および発注可能数値（Execution）の契約定義。

設計意図:
- decision 層の出力を「発注可能な数値」を含む契約として固定する。
- LLM 層・レポート層は本契約の値を改変しない（翻訳・監査のみ）。
- 曖昧さを持ち込まないため、BUY_SIGNAL は 3 値に固定する。
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class BuySignal(str, Enum):
    """売買シグナル（3値固定）。"""

    YES = "YES"
    YES_HALF = "YES_HALF"
    NO = "NO"


class ExecutionNumbers(BaseModel):
    """発注可能な数値（決定論で生成されることを前提）。"""

    entry_price: float = Field(..., gt=0.0, description="Entry price")
    stop_price: float = Field(..., gt=0.0, description="Stop loss price")
    target_price: float = Field(..., gt=0.0, description="Target (take profit) price")

    quantity: int = Field(..., ge=0, description="Order quantity (0 allowed for NO)")
    risk_amount: float = Field(..., ge=0.0, description="Risk amount in base currency")
    reward_amount: float = Field(..., ge=0.0, description="Reward amount in base currency")

    r_multiple: float = Field(
        ..., ge=0.0, description="Reward/Risk multiple (= reward_amount / risk_amount if risk>0)"
    )

    class Config:
        frozen = True

    @model_validator(mode="after")
    def _validate_price_order(self) -> "ExecutionNumbers":
        # 設計: M1 はロング前提（スイング例）。将来ショート導入時は side を別契約で追加する。
        if not (self.stop_price < self.entry_price < self.target_price):
            raise ValueError("Invalid price order: expected stop < entry < target (long-only in M1).")

        # quantity=0 の場合は、リスク/リワードも 0 に寄せる（NO の自然形）
        if self.quantity == 0:
            if self.risk_amount != 0.0 or self.reward_amount != 0.0 or self.r_multiple != 0.0:
                raise ValueError("If quantity is 0, risk_amount/reward_amount/r_multiple must be 0.")
            return self

        # quantity>0 の場合は、リスクが正であることを要求
        if self.risk_amount <= 0.0:
            raise ValueError("risk_amount must be > 0 when quantity > 0.")

        # r_multiple の整合（許容誤差は downstream で丸める）
        implied = self.reward_amount / self.risk_amount
        if abs(implied - self.r_multiple) > 1e-6:
            raise ValueError("r_multiple mismatch with reward_amount / risk_amount.")

        return self


class DecisionCore(BaseModel):
    """銘柄単位の最終判断（数値と根拠の最小）。"""

    symbol: str = Field(..., min_length=1, description="Ticker / symbol")
    asof: date = Field(..., description="EOD date")

    buy_signal: BuySignal = Field(..., description="3-valued buy signal")
    plan_id: str = Field(..., min_length=1, description="Applied plan identifier")

    # 候補内ランキング等（NO でも順位は付けられるが、M1 は任意）
    rank: int | None = Field(None, ge=1, description="Rank within candidates (1 is best)")
    score: float | None = Field(None, description="Rule-based score (optional in M1)")

    execution: ExecutionNumbers = Field(..., description="Deterministic execution numbers")

    # 最小の説明責任（LLM 以前の機械生成テキスト。LLM はこれを翻訳・整形するだけ）
    rationale: str = Field(
        "",
        description="Short deterministic rationale (LLM must not change numbers; can paraphrase rationale).",
    )

    class Config:
        frozen = True

    @model_validator(mode="after")
    def _validate_signal_quantity_consistency(self) -> "DecisionCore":
        # NO は quantity=0 を強制（安全側）
        if self.buy_signal == BuySignal.NO and self.execution.quantity != 0:
            raise ValueError("For NO signal, quantity must be 0.")

        # YES/YES_HALF は quantity>0 を要求（発注可能契約）
        if self.buy_signal in (BuySignal.YES, BuySignal.YES_HALF) and self.execution.quantity <= 0:
            raise ValueError("For YES/YES_HALF signal, quantity must be > 0.")

        return self


class DecisionPack(BaseModel):
    """EOD 1回分の意思決定パッケージ（再現性と監査の単位）。"""

    market: str = Field(..., min_length=1, description="Market identifier (e.g., JP/US)")
    asof: date = Field(..., description="EOD date")
    run_id: str = Field(..., min_length=1, description="Run identifier")

    decisions: list[DecisionCore] = Field(default_factory=list, description="Decisions for symbols")

    class Config:
        frozen = True
