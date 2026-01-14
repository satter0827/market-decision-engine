"""設定リゾルバ（defaults + user config の合成と正規化）。

設計意図:
- defaults（不変）と user config（可変）を合成し、パイプラインで扱いやすい形へ正規化する。
- I/O は loader に限定し、本モジュールは純粋関数として扱えるようにする。
- schemas による厳密検証は後段に寄せ、M1 は「最低限の型・範囲」をここで担保する。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from market_decision_engine.config.defaults import (
    GLOBAL_DEFAULTS,
    LLM_DEFAULTS,
    MARKET_DEFAULTS,
    REPORT_DEFAULTS,
)
from market_decision_engine.exceptions import ConfigurationError


def resolve_config(
    *,
    market: str,
    user_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """defaults と user config を合成し、正規化済み config を返す。

    Args:
        market: 市場識別子（例: "JP", "US"）。
        user_config: loader が読み込んだユーザー設定（dict 相当）。

    Returns:
        正規化済み設定 dict（pipeline/context.py に渡せる形）。

    Raises:
        ConfigurationError: 市場が不明、設定の型が不正、値が許容範囲外など。
    """
    market_key = _normalize_market_key(market)

    if user_config is None:
        user_config_dict: dict[str, Any] = {}
    else:
        if not isinstance(user_config, Mapping):
            raise ConfigurationError("user_config must be a mapping.")
        user_config_dict = dict(user_config)

    base: dict[str, Any] = {}
    base = _deep_merge(base, deepcopy(GLOBAL_DEFAULTS))
    base = _deep_merge(base, deepcopy(MARKET_DEFAULTS.get(market_key, {})))
    base = _deep_merge(base, deepcopy(REPORT_DEFAULTS))
    base = _deep_merge(base, deepcopy(LLM_DEFAULTS))

    merged = _deep_merge(base, user_config_dict)
    normalized = _normalize_config(merged, market_key=market_key)
    return normalized


def _normalize_market_key(market: str) -> str:
    """市場キーを正規化する。"""
    if not isinstance(market, str) or not market.strip():
        raise ConfigurationError("market must be a non-empty string.")

    mk = market.strip().upper()
    if mk not in MARKET_DEFAULTS:
        allowed = ", ".join(sorted(MARKET_DEFAULTS.keys()))
        raise ConfigurationError(f"Unknown market: {mk}. Allowed: {allowed}")
    return mk


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """辞書を deep merge する（override が優先）。

    - dict 同士は再帰的に merge
    - それ以外（list/str/int/...）は override で上書き
    """
    if not isinstance(override, Mapping):
        raise ConfigurationError("override must be a mapping.")

    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            # user_config は Mapping の可能性があるため dict へ落とす
            if isinstance(value, Mapping):
                result[key] = dict(value)
            else:
                result[key] = value
    return result


def _normalize_config(config: dict[str, Any], *, market_key: str) -> dict[str, Any]:
    """最小の正規化（型・範囲・必須キー補完）を行う。"""
    if not isinstance(config, dict):
        raise ConfigurationError("Resolved config must be a dict.")

    cfg = dict(config)

    # ---- top-level (global) ----
    cfg["max_candidates"] = _as_int(cfg.get("max_candidates"), name="max_candidates", min_value=1, max_value=5000)
    cfg["max_positions"] = _as_int(cfg.get("max_positions"), name="max_positions", min_value=1, max_value=2000)
    cfg["degraded_on_error"] = _as_bool(cfg.get("degraded_on_error"), name="degraded_on_error")

    # ---- data ----
    data = _ensure_dict(cfg.get("data"), name="data")
    data["ohlcv_lookback_days"] = _as_int(
        data.get("ohlcv_lookback_days"),
        name="data.ohlcv_lookback_days",
        min_value=10,
        max_value=5000,
    )
    data["adjust_prices"] = _as_bool(data.get("adjust_prices"), name="data.adjust_prices")
    cfg["data"] = data

    # ---- features.daily ----
    features = _ensure_dict(cfg.get("features"), name="features")
    daily = _ensure_dict(features.get("daily"), name="features.daily")
    daily["atr_period"] = _as_int(daily.get("atr_period"), name="features.daily.atr_period", min_value=2, max_value=200)
    daily["rsi_period"] = _as_int(daily.get("rsi_period"), name="features.daily.rsi_period", min_value=2, max_value=200)
    features["daily"] = daily
    cfg["features"] = features

    # ---- plan ----
    plan = _ensure_dict(cfg.get("plan"), name="plan")
    default_plan_id = plan.get("default_plan_id")
    if not isinstance(default_plan_id, str) or not default_plan_id.strip():
        raise ConfigurationError("plan.default_plan_id must be a non-empty string.")
    plan["default_plan_id"] = default_plan_id.strip()
    cfg["plan"] = plan

    # ---- universe ----
    universe = _ensure_dict(cfg.get("universe"), name="universe")
    source = universe.get("source")
    if source is None:
        universe["source"] = "STATIC"
    else:
        if not isinstance(source, str) or not source.strip():
            raise ConfigurationError("universe.source must be a non-empty string.")
        universe["source"] = source.strip().upper()
    cfg["universe"] = universe

    # ---- report ----
    # defaults.py では REPORT_DEFAULTS をフラットに置いているため、ここもフラット運用に合わせる
    fmt = cfg.get("format")
    if fmt is None:
        cfg["format"] = "JSON"
    else:
        if not isinstance(fmt, str):
            raise ConfigurationError("format must be a string.")
        fmt_u = fmt.strip().upper()
        if fmt_u not in {"JSON", "MARKDOWN"}:
            raise ConfigurationError("format must be one of: JSON, MARKDOWN.")
        cfg["format"] = fmt_u

    cfg["include_skipped"] = _as_bool(cfg.get("include_skipped"), name="include_skipped")

    # ---- llm ----
    enabled = cfg.get("enabled")
    cfg["enabled"] = _as_bool(enabled, name="enabled")

    # 最低限のメタ（デバッグ用）
    cfg.setdefault("_meta", {})
    meta = _ensure_dict(cfg["_meta"], name="_meta")
    meta["market"] = market_key
    cfg["_meta"] = meta

    return cfg


def _ensure_dict(value: Any, *, name: str) -> dict[str, Any]:
    """dict を要求し、None なら空 dict とする。"""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigurationError(f"{name} must be a dict.")
    return dict(value)


def _as_bool(value: Any, *, name: str) -> bool:
    """bool を要求（厳格）。"""
    if isinstance(value, bool):
        return value
    if value is None:
        raise ConfigurationError(f"{name} must be a bool.")
    raise ConfigurationError(f"{name} must be a bool.")


def _as_int(value: Any, *, name: str, min_value: int, max_value: int) -> int:
    """int を要求し、範囲チェックを行う（厳格）。"""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigurationError(f"{name} must be an int.")
    if value < min_value or value > max_value:
        raise ConfigurationError(f"{name} out of range: {value} (allowed: {min_value}-{max_value}).")
    return value
