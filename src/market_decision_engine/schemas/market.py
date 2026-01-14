"""市場実行コンテキストの契約定義。

設計意図:
- EOD バッチの「現在」を不変オブジェクトとして固定する
- CLI / API / テストの全入口で共通利用する
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RunContext(BaseModel):
    """EOD 実行コンテキスト（不変）。"""

    market: Literal["JP", "US"] = Field(..., description="Target market")
    asof: date = Field(..., description="EOD date (market close 기준)")
    run_id: str = Field(..., description="Unique run identifier")

    class Config:
        frozen = True
