# src/market_decision_engine/data/loaders/yfinance.py
"""yfinance 専用ローダ（外部I/Oを局所化）。

設計意図:
- 外部I/O（株価取得）をこのモジュールに閉じ込める。
- 返り値は後段（preprocess/features）が扱いやすい pandas.DataFrame（OHLCV）とする。
- 取得失敗は ExternalServiceError として分類し、上位で縮退/スキップ可能にする。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Final, Protocol, cast

import pandas as pd
import yfinance as yf

from market_decision_engine.exceptions import ExternalServiceError
from market_decision_engine.pipeline.context import EngineContext

_REQUIRED_COLS: Final[list[str]] = ["Open", "High", "Low", "Close", "Volume"]


class _YFinanceDownload(Protocol):
    """yfinance の必要最小API（download）を型として定義する。

    yfinance は型スタブが不完全なことがあるため、mypy strict 下では
    Protocol + cast で外部境界を局所的に型付けする。
    """

    def download(
        self,
        *,
        tickers: str,
        start: datetime,
        end: datetime,
        interval: str,
        auto_adjust: bool,
        progress: bool,
        group_by: str,
        threads: bool,
    ) -> pd.DataFrame: ...


def load_ohlcv(ctx: EngineContext, symbol: str) -> pd.DataFrame:
    """yfinance で日足 OHLCV を取得する。

    Args:
        ctx: 実行文脈。
        symbol: yfinance で解釈可能なティッカー（例: "7203.T", "AAPL"）。

    Returns:
        日足OHLCVの DataFrame。
        - index: DatetimeIndex（tz naive）
        - columns: Open, High, Low, Close, Volume（必要最低限）
        - asof 以前のデータに切り詰め済み

    Raises:
        ExternalServiceError: yfinance の依存欠如・通信/取得失敗・形式不正など。
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ExternalServiceError("symbol must be a non-empty string.")

    lookback_days = _get_lookback_days(ctx)
    adjust_prices = _get_adjust_prices(ctx)

    asof = ctx.run.asof
    start_dt, end_dt = _calc_date_range(asof=asof, lookback_days=lookback_days)

    # yfinance の型情報が不十分な環境でも mypy strict を通すための局所対処
    yfl = cast(_YFinanceDownload, yf)

    try:
        # yfinance の end は排他的になりがちなので、翌日を指定
        df: pd.DataFrame = yfl.download(
            tickers=symbol,
            start=start_dt,
            end=end_dt,
            interval="1d",
            auto_adjust=bool(adjust_prices),
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception as e:  # noqa: BLE001
        raise ExternalServiceError(f"yfinance download failed for symbol={symbol}.") from e

    if df.empty:
        raise ExternalServiceError(f"No OHLCV data returned for symbol={symbol}.")

    # yfinance は MultiIndex columns を返す場合がある（tickers複数時など）。
    # m1.1 は単一 ticker 前提なので、必要なら単純化する。
    df = _flatten_columns_if_needed(df)

    missing = [c for c in _REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ExternalServiceError(
            f"OHLCV missing required columns for symbol={symbol}: {missing}"
        )

    # index を datetime に寄せ、tz を落とす
    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            df.index = pd.to_datetime(df.index)
        except Exception as e:  # noqa: BLE001
            raise ExternalServiceError(f"Invalid index type for symbol={symbol}.") from e

    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)

    # asof 以前に切り詰め（yfinance の日付境界差分を吸収）
    df = df.loc[df.index.date <= asof]

    # 必要最低限の列だけ残す（Adj Close 等は M1 では不要）
    df = df[_REQUIRED_COLS].sort_index()

    # すべて NaN の行を落とす
    df = df.dropna(how="all")

    if df.empty:
        raise ExternalServiceError(f"OHLCV became empty after cleaning for symbol={symbol}.")

    return df


def _get_lookback_days(ctx: EngineContext) -> int:
    data_cfg = ctx.config.get("data", {})
    if isinstance(data_cfg, dict):
        v = data_cfg.get("ohlcv_lookback_days")
        if isinstance(v, int) and v > 0:
            return v
    # defaults/resolver が正規化している想定だが、二重安全
    return 120


def _get_adjust_prices(ctx: EngineContext) -> bool:
    data_cfg = ctx.config.get("data", {})
    if isinstance(data_cfg, dict):
        v = data_cfg.get("adjust_prices")
        if isinstance(v, bool):
            return v
    return True


def _calc_date_range(*, asof: date, lookback_days: int) -> tuple[datetime, datetime]:
    """asof から取得期間を決める（営業日ではなく暦日で広めに取る）。"""
    # 休日分を吸収するため、少し余裕を持って遡る
    start = datetime.combine(asof - timedelta(days=int(lookback_days * 2)), datetime.min.time())
    end = datetime.combine(asof + timedelta(days=1), datetime.min.time())
    return start, end


def _flatten_columns_if_needed(df: pd.DataFrame) -> pd.DataFrame:
    """MultiIndex columns を単純化する（単一ティッカー前提の安全弁）。"""
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    try:
        if df.columns.nlevels >= 2:
            out = df.copy()
            out.columns = out.columns.get_level_values(0)
            return out
    except Exception:
        return df

    return df
