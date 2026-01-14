"""特徴量（Feature）の契約定義。

設計意図:
- feature 分離原則（daily / static / fundamental）を型で固定する。
- 計算ロジックは features/ 配下に閉じ、ここは意味論のみを定義する。
- execution / decision 層が参照してよい feature を構造で制限する。
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class FeatureBase(BaseModel):
    """全 feature 共通の基底契約。"""

    symbol: str = Field(..., min_length=1, description="Ticker / symbol")
    asof: date = Field(..., description="EOD date")

    class Config:
        frozen = True


class DailyFeature(FeatureBase):
    """日次価格由来の特徴量（Execution/Selection の主根拠）。"""

    close: float = Field(..., gt=0.0, description="Close price")
    volume: float = Field(..., ge=0.0, description="Trading volume")

    atr: float | None = Field(None, gt=0.0, description="Average True Range")
    rsi: float | None = Field(None, ge=0.0, le=100.0, description="RSI(14)")

    # M1 は最低限。移動平均などは後続で追加しても契約破壊にならない


class StaticFeature(FeatureBase):
    """静的特徴量（規模・流動性など。価格決定には使わない）。"""

    market_cap: float | None = Field(None, ge=0.0, description="Market capitalization")
    avg_volume_20d: float | None = Field(None, ge=0.0, description="20-day average volume")

    sector: str | None = Field(None, description="Sector classification")


class FundamentalFeature(FeatureBase):
    """財務特徴量（欠損前提・ML 専用）。"""

    revenue_growth_yoy: float | None = Field(
        None, description="Revenue growth YoY"
    )
    operating_margin: float | None = Field(
        None, description="Operating margin"
    )
    roe: float | None = Field(None, description="Return on equity")
