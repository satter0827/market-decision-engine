# src/market_decision_engine/universe/jp.py
"""日本株 Universe（M1: 固定リスト）。

設計意図:
- m1.1 の最小E2Eを成立させるため、まずは固定銘柄リストを返す。
- 将来は市場別 Universe 実装（TOPIX500 等）やフィルタに置き換えるが、
  本モジュールの I/F（build_universe）は維持する。
- config で銘柄リストを上書きできるようにしておく（任意）。
"""

from __future__ import annotations

from typing import Any

from market_decision_engine.pipeline.context import EngineContext


# M1 の固定 Universe（例: 大型・流動性が高い銘柄中心）
_DEFAULT_JP_SYMBOLS: list[str] = [
    "7203.T",  # トヨタ
    "6758.T",  # ソニーG
    "9432.T",  # NTT
    "8306.T",  # 三菱UFJ
    "9984.T",  # ソフトバンクG
    "6861.T",  # キーエンス
    "7974.T",  # 任天堂
    "8035.T",  # 東京エレクトロン
]


def build_universe(ctx: EngineContext) -> list[str]:
    """日本株 Universe を返す。

    Args:
        ctx: パイプライン実行文脈。

    Returns:
        銘柄コード（yfinance 前提のティッカー）リスト。
        config に universe.symbols があればそれを優先する。
    """
    cfg_universe: Any = ctx.config.get("universe", {})
    if isinstance(cfg_universe, dict):
        symbols_any: Any = cfg_universe.get("symbols")
        symbols = _coerce_symbols(symbols_any)
        if symbols:
            return symbols

    return list(_DEFAULT_JP_SYMBOLS)


def _coerce_symbols(value: Any) -> list[str]:
    """symbols を list[str] に正規化する（失敗時は空）。"""
    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
    return out
