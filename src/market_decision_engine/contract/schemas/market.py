"""スキーマ定義：マーケット意思決定エンジンの契約データ構造.
Notes:
    - 日次OHLCVおよびテクニカル指標
    - 1行あたりの特徴量データ（ティッカー×日付）
    - バッチの特徴量データパック

Policy:
    - Pydanticを使用してデータ検証とシリアル化を行う
    - 将来の拡張のために柔軟なスキーマ設計を維持する
    - ドキュメント文字列で各フィールドとモデルの目的を明確に
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from typing import Any
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 基本型
Ticker = Annotated[str, Field(min_length=1, max_length=32, description="Ticker symbol")]
ISODate = date

FiniteFloat = Annotated[
    float,
    Field(description="Finite float (NaN/inf should be filtered before validation)"),
]

NonNegativeFloat = Annotated[
    float,
    Field(ge=0.0, description="Must be >= 0"),
]

# Enum型
class BuySignal(str, Enum):
    """Buy decision signal.

    Notes:
        - YES: full size (subject to sizing rules)
        - YES_HALF: half size (conservative)
        - NO: skip
    """

    YES = "YES"
    YES_HALF = "YES_HALF"
    NO = "NO"

# 日次OHLCVデータ
class OhlcvDaily(BaseModel):
    """日時OHLCVデータ."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    open: FiniteFloat
    high: FiniteFloat
    low: FiniteFloat
    close: FiniteFloat
    adj_close: FiniteFloat | None = Field(
        default=None, description="If available; otherwise None"
    )
    volume: NonNegativeFloat


# テクニカル指標
class IndicatorsDaily(BaseModel):
    """テクニカル指標.

    Policy:
        - すべてのフィールドはオプション（None許容）
        - 将来の指標追加のために柔軟に設計
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Returns / volatility
    ret_1d: FiniteFloat | None = Field(default=None, description="Close-to-close return")
    ret_5d: FiniteFloat | None = Field(default=None)
    ret_20d: FiniteFloat | None = Field(default=None)

    logret_1d: FiniteFloat | None = Field(default=None, description="Log return")
    vol_20d: NonNegativeFloat | None = Field(default=None, description="Rolling vol (stdev)")
    atr_14: NonNegativeFloat | None = Field(default=None, description="ATR(14)")

    # Trend / moving averages
    sma_5: FiniteFloat | None = Field(default=None)
    sma_20: FiniteFloat | None = Field(default=None)
    sma_50: FiniteFloat | None = Field(default=None)
    ema_20: FiniteFloat | None = Field(default=None)
    ema_50: FiniteFloat | None = Field(default=None)

    close_over_sma_20: FiniteFloat | None = Field(default=None, description="close / sma_20")
    close_over_sma_50: FiniteFloat | None = Field(default=None, description="close / sma_50")

    # Momentum / oscillators
    rsi_14: FiniteFloat | None = Field(default=None, description="RSI(14) 0-100")
    stoch_k_14: FiniteFloat | None = Field(default=None, description="%K")
    stoch_d_3: FiniteFloat | None = Field(default=None, description="%D")

    macd: FiniteFloat | None = Field(default=None)
    macd_signal: FiniteFloat | None = Field(default=None)
    macd_hist: FiniteFloat | None = Field(default=None)

    # Bollinger Bands (20,2)
    bb_mid_20: FiniteFloat | None = Field(default=None)
    bb_upper_20_2: FiniteFloat | None = Field(default=None)
    bb_lower_20_2: FiniteFloat | None = Field(default=None)
    bb_width_20_2: NonNegativeFloat | None = Field(
        default=None, description="(upper-lower)/mid"
    )
    bb_percent_b_20_2: FiniteFloat | None = Field(
        default=None, description="(close-lower)/(upper-lower)"
    )

    # Range / candles
    true_range: NonNegativeFloat | None = Field(default=None)
    hl_range: NonNegativeFloat | None = Field(default=None, description="high - low")
    body: FiniteFloat | None = Field(default=None, description="close - open")
    upper_wick: NonNegativeFloat | None = Field(default=None)
    lower_wick: NonNegativeFloat | None = Field(default=None)

    gap: FiniteFloat | None = Field(default=None, description="open - prev_close")
    gap_pct: FiniteFloat | None = Field(default=None)

    # Volume-derived
    v_sma_20: NonNegativeFloat | None = Field(default=None, description="volume SMA(20)")
    v_ratio_20: FiniteFloat | None = Field(default=None, description="volume / v_sma_20")
    obv: FiniteFloat | None = Field(default=None, description="On-Balance Volume (level)")

    # Breakout / levels
    hh_20: FiniteFloat | None = Field(default=None, description="20d highest high")
    ll_20: FiniteFloat | None = Field(default=None, description="20d lowest low")
    close_to_hh_20: FiniteFloat | None = Field(default=None, description="close / hh_20")
    close_to_ll_20: FiniteFloat | None = Field(default=None, description="close / ll_20")


# 意思決定コア
class DecisionCore(BaseModel):
    """意思決定コア構造体.

    Notes:
        - 成立した意思決定のみ価格・サイズが入る
        - 未成立日は None を保持する（ダミー値は使わない）
        - Schema は「事実の表現」に徹する
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Buy判断
    buy_signal: BuySignal = Field(description="Final decision signal (YES/YES_HALF/NO).")

    # 購入価格とターゲット（未成立日は None）
    entry: FiniteFloat | None = Field(
        default=None, description="Planned entry price."
    )
    stop: FiniteFloat | None = Field(
        default=None, description="Stop loss price."
    )
    target_2r: FiniteFloat | None = Field(
        default=None, description="Take profit at 2R."
    )
    target_3r: FiniteFloat | None = Field(
        default=None, description="Take profit at 3R."
    )

    # ポジションサイズとリスク管理（未成立日は None）
    position_size: NonNegativeFloat | None = Field(
        default=None,
        description="Position size in shares/units. None means not applicable.",
    )
    max_loss: NonNegativeFloat | None = Field(
        default=None,
        description="Max loss in account currency. None means not applicable.",
    )

    time_stop_days: int = Field(ge=1, description="Time stop in days.")

    # スコアリングとランキング
    plan_score: FiniteFloat = Field(description="Deterministic plan score for ranking.")
    rank: int = Field(ge=1, description="Rank within the batch (1 is best).")

    # メタデータとトレーサビリティ
    plan_args: dict[str, Any] = Field(
        default_factory=dict,
        description="Plan parameters used to compute this decision (deterministic).",
    )
    policy_snapshot_id: str = Field(
        min_length=1, description="Identifier of the policy snapshot used."
    )

    # 警告や注意事項
    warnings: list[str] = Field(
        default_factory=list,
        description="Short warnings (should be limited in downstream formatting).",
    )

    @model_validator(mode="after")
    def _validate_structure(self) -> "DecisionCore":
        """成立している場合のみ構造検証を行う."""

        # ---- 未成立（NO）は None を自然状態として許可
        if self.buy_signal == BuySignal.NO:
            return self

        # ---- 成立時は必須項目がすべて揃っていること
        required = (
            self.entry,
            self.stop,
            self.target_2r,
            self.target_3r,
            self.position_size,
            self.max_loss,
        )
        if any(v is None for v in required):
            raise ValueError("Invalid structure: decision fields must not be None when active.")

        assert self.entry is not None
        assert self.stop is not None
        assert self.target_2r is not None
        assert self.target_3r is not None
        assert self.position_size is not None
        assert self.max_loss is not None

        # ---- 価格構造
        if self.entry <= self.stop:
            raise ValueError("Invalid structure: entry must be greater than stop.")

        risk = self.entry - self.stop
        if self.target_2r < self.entry + 2.0 * risk:
            raise ValueError("Invalid structure: target_2r must be >= entry + 2R.")

        if self.target_3r < self.entry + 3.0 * risk:
            raise ValueError("Invalid structure: target_3r must be >= entry + 3R.")

        # ---- サイズ整合性
        if self.position_size <= 0.0:
            raise ValueError("Invalid structure: active decision requires position_size > 0.")

        return self
