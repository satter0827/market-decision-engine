"""スキーマ定義：ユーザー（運用者）側のポリシー・口座前提.

このスキーマは市場データ（yfinance等）では得られない、運用者固有の前提を保持する。
例：口座残高、リスク予算、最大建玉、売買単位、執行時の保守的前提（スリッページ等）。

Policy:
    - Pydantic v2 による検証とシリアライズ
    - extra="forbid", frozen=True
    - 数値生成はルール側で行い、本スキーマは「設定値（前提）」のみを持つ
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


FiniteFloat = Annotated[
    float,
    Field(description="Finite float (NaN/inf should be filtered before validation)"),
]
PositiveFloat = Annotated[float, Field(gt=0.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]
Percent01 = Annotated[float, Field(ge=0.0, le=1.0, description="Ratio in [0,1]")]


class Market(str, Enum):
    """市場区分（最小）."""

    JP = "JP"
    US = "US"


class Currency(str, Enum):
    """通貨（最小）."""

    JPY = "JPY"
    USD = "USD"


class AccountPolicy(BaseModel):
    """口座前提（あなた側の情報）.

    - equity: 現金/証拠金など、サイズ算出に用いる基準残高
    - currency: 残高の通貨
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    equity: PositiveFloat = Field(description="Account equity used for sizing.")
    currency: Currency = Field(default=Currency.JPY, description="Account base currency.")


class RiskPolicy(BaseModel):
    """リスク管理ポリシー（サイズ・損失上限）."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    risk_per_trade_pct: Percent01 = Field(
        default=0.005,
        description="Risk budget per trade as % of equity. Example: 0.005 = 0.5%.",
    )
    max_position_pct: Percent01 = Field(
        default=0.10,
        description="Max position notional as % of equity. Example: 0.10 = 10%.",
    )
    max_concurrent_positions: Annotated[int, Field(ge=1)] = Field(
        default=10, description="Soft cap for diversification (optional gate)."
    )


class ExecutionPolicy(BaseModel):
    """執行・発注の前提（保守的見積り）.

    Notes:
        - 初期は固定値でよい（ゼロでも可）。
        - 将来、market別・銘柄別に拡張してもよいが、現段階では最小で固定。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slippage_pct: Percent01 = Field(
        default=0.001,
        description="Assumed slippage ratio applied to entry/exit estimates.",
    )
    commission_per_order: NonNegativeFloat = Field(
        default=0.0, description="Flat commission per order in account currency."
    )
    tax_pct: Percent01 = Field(
        default=0.0, description="Optional tax ratio for PnL estimation (not required)."
    )


class MarketConstraints(BaseModel):
    """市場・売買単位・流動性などの制約.

    - lot_size: 最小売買単位（JP=100株など、US=1株など）
    - min_price: 低位株除外（任意）
    - min_avg_dollar_volume: 流動性下限（任意、static側指標が整うまでゲートに使う）
    - impact_cap_pct: 1回の建玉が平均売買代金の何%まで許容か（任意）
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    market: Market = Field(description="Target market.")
    lot_size: Annotated[int, Field(ge=1)] = Field(
        description="Minimum tradable unit size in shares."
    )

    min_price: NonNegativeFloat = Field(
        default=0.0, description="Exclude too-cheap tickers if needed."
    )

    min_avg_dollar_volume: NonNegativeFloat = Field(
        default=0.0,
        description="Liquidity floor (0 disables). Requires static feature to be meaningful.",
    )
    impact_cap_pct: Percent01 = Field(
        default=0.0,
        description="Cap position notional by ADV * impact_cap_pct (0 disables).",
    )


class TradePlanPolicy(BaseModel):
    """価格計算ルール（最小）.

    - entry_buffer_pct: ブレイクアウト注文の上乗せ（例：0.1%）
    - atr_n: ATR期間
    - atr_stop_k: ATRストップ係数
    - swing_lookback: スイング安値の参照期間（例：20日）
    - time_stop_days: 時間切れ日数（初期は固定で十分）
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_buffer_pct: Percent01 = Field(default=0.001, description="Entry buffer ratio.")
    atr_n: Annotated[int, Field(ge=1)] = Field(default=14, description="ATR window.")
    atr_stop_k: PositiveFloat = Field(default=2.0, description="ATR stop multiplier.")
    swing_lookback: Annotated[int, Field(ge=2)] = Field(
        default=20, description="Lookback days for swing low/high."
    )
    time_stop_days: Annotated[int, Field(ge=1)] = Field(
        default=40, description="Time stop in calendar days (fixed for M1)."
    )


class UserPolicySnapshot(BaseModel):
    """ユーザー（運用者）側ポリシーのスナップショット.

    DecisionCore の算出は、この snapshot と daily/static/regime を入力にして決定論で行う。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    account: AccountPolicy
    risk: RiskPolicy = Field(default_factory=RiskPolicy)
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    constraints: MarketConstraints
    trade_plan: TradePlanPolicy = Field(default_factory=TradePlanPolicy)
