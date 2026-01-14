"""ユーザーポリシー（運用方針）の契約定義。

設計意図:
- EOD の判断・サイズ計算・除外ルールの「前提」をここで固定する。
- 計算ロジックは持たず、値の意味と制約のみを定義する。
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class UserPolicy(BaseModel):
    """ユーザーの運用ポリシー（入力・設定由来）。"""

    base_currency: Literal["JPY", "USD"] = Field(..., description="Base currency")
    equity: float = Field(..., ge=0.0, description="Total equity in base currency")

    # リスク上限（M1はシンプルに固定）
    risk_per_trade: float = Field(
        0.01, ge=0.0, le=0.05, description="Risk per trade (fraction of equity)"
    )
    max_positions: int = Field(10, ge=1, le=200, description="Max concurrent positions")
    max_candidates: int = Field(30, ge=1, le=500, description="Max candidates to output")

    # 取引コスト等（M1では未使用でも契約として先に置く）
    commission_rate: float = Field(
        0.0, ge=0.0, le=0.02, description="Commission rate"
    )
    slippage_rate: float = Field(0.0, ge=0.0, le=0.02, description="Slippage rate")

    class Config:
        frozen = True


class PolicySnapshot(BaseModel):
    """実行時点のポリシースナップショット（監査・再現用）。"""

    asof: date = Field(..., description="Snapshot date")
    policy: UserPolicy = Field(..., description="Frozen user policy")

    class Config:
        frozen = True
