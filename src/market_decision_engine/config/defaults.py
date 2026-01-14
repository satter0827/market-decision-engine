"""デフォルト設定（最小）。

設計意図:
- M1 でパイプラインを動かすための「最低限の前提」を定義する。
- 環境依存・I/O・動的解決は行わない（resolver が責務を持つ）。
- ここにある値は「存在してよい初期値」であり、最適値ではない。
"""

from __future__ import annotations


# ====================
# Global defaults
# ====================

GLOBAL_DEFAULTS: dict[str, object] = {
    # 出力・挙動
    "max_candidates": 30,
    "max_positions": 10,
    "degraded_on_error": True,
}

# ====================
# Market-specific defaults
# ====================

MARKET_DEFAULTS: dict[str, dict[str, object]] = {
    "JP": {
        # universe
        "universe": {
            "source": "STATIC",  # M1: 固定リスト or 内部定義
        },
        # data
        "data": {
            "ohlcv_lookback_days": 120,
            "adjust_prices": True,
        },
        # features
        "features": {
            "daily": {
                "atr_period": 14,
                "rsi_period": 14,
            }
        },
        # plan
        "plan": {
            "default_plan_id": "swing_basic",
        },
    },
    "US": {
        "universe": {
            "source": "STATIC",
        },
        "data": {
            "ohlcv_lookback_days": 200,
            "adjust_prices": True,
        },
        "features": {
            "daily": {
                "atr_period": 14,
                "rsi_period": 14,
            }
        },
        "plan": {
            "default_plan_id": "swing_basic",
        },
    },
}

# ====================
# Report defaults
# ====================

REPORT_DEFAULTS: dict[str, object] = {
    "format": "JSON",
    "include_skipped": True,
}

# ====================
# LLM defaults (M1: dormant)
# ====================

LLM_DEFAULTS: dict[str, object] = {
    "enabled": False,  # M1 では常に false
}

