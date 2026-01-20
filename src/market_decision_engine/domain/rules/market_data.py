"""Rules: market data fetching and normalization."""
from __future__ import annotations

from typing import Any, Hashable
import math
import numpy as np
import json
import hashlib

import pandas as pd
import yfinance as yf

from market_decision_engine.contract.errors import DataError, ExternalDataError, SkipTicker
from market_decision_engine.contract.schemas.market import OhlcvDaily, IndicatorsDaily, DecisionCore, BuySignal
from market_decision_engine.contract.schemas.policy import UserPolicySnapshot


def fetch_ohlcv_frame(
    *,
    ticker: str,
    start: str | None,
    end: str | None,
    interval: str,
) -> pd.DataFrame:
    """yfinanceからOHLCVを取得し、正規化済みDataFrameを返す.

    Args:
        ticker: ティッカーシンボル.
        start: 開始日（YYYY-MM-DD形式）またはNone.
        end: 終了日（YYYY-MM-DD形式）またはNone.
        interval: データ間隔（例: "1d", "1wk", "1mo"）.

    Returns:
        pd.DataFrame: columns=["date","open","high","low","close","volume"] を満たす。
    """
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
    except Exception as err:
        raise ExternalDataError(
            "Failed to download OHLCV via yfinance.",
            context={"ticker": ticker, "start": start, "end": end, "interval": interval},
        ) from err

    if df is None or df.empty:
        raise SkipTicker(
            "OHLCV is empty.",
            context={"ticker": ticker, "start": start, "end": end, "interval": interval},
        )

    # MultiIndex: ('Open','AAPL') 等を 'Open' に潰す
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)

    needed = {"Open", "High", "Low", "Close", "Volume"}
    if not needed.issubset(set(df.columns)):
        raise DataError(
            "OHLCV columns are missing.",
            context={"ticker": ticker, "columns": list(df.columns), "required": sorted(needed)},
        )

    df2 = df.reset_index().rename(
        columns={
            "Date": "date",
            "Datetime": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    required = {"date", "open", "high", "low", "close", "volume"}
    if not required.issubset(set(df2.columns)):
        raise DataError(
            "OHLCV normalized columns are missing.",
            context={"ticker": ticker, "columns": list(df2.columns), "required": sorted(required)},
        )

    return df2[["date", "open", "high", "low", "close", "volume"]].copy()


def frame_to_ohlcv_by_date(*, ohlcv_frame: pd.DataFrame) -> dict[str, OhlcvDaily]:
    """正規化済みOHLCVフレームを dateキーへ落として OhlcvDaily を返す.

    Args:
        ohlcv_frame: 正規化済みOHLCVデータを含むDataFrame（日次）.
    """
    by_date: dict[str, OhlcvDaily] = {}

    for row in ohlcv_frame.itertuples(index=False):
        dt = getattr(row, "date")
        if isinstance(dt, pd.Timestamp):
            date_key = dt.date().isoformat()
        else:
            date_key = str(dt)[:10]

        payload = {
            "open": float(getattr(row, "open")),
            "high": float(getattr(row, "high")),
            "low": float(getattr(row, "low")),
            "close": float(getattr(row, "close")),
            "volume": float(getattr(row, "volume")),
        }
        by_date[date_key] = OhlcvDaily.model_validate(payload)

    return by_date

def build_indicators_by_date(*, ohlcv_frame: pd.DataFrame) -> dict[str, IndicatorsDaily]:
    """OHLCVフレームから指標を計算し、dateキーに対して IndicatorsDaily を返す.
    Args:
        ohlcv_frame: OHLCVデータを含むDataFrame（日次）.

    Returns:
        dict[str, IndicatorsDaily]: 指標データの辞書（日付文字列をキーとする）.
    """
    ind_df = compute_indicators_frame(ohlcv_frame=ohlcv_frame)

    out: dict[str, IndicatorsDaily] = {}
    for date_key, row in ind_df.iterrows():
        out[str(date_key)] = _validate_indicators(row.to_dict())
    return out


def compute_indicators_frame(*, ohlcv_frame: pd.DataFrame) -> pd.DataFrame:
    """指標をDataFrameで計算し、index=YYYY-MM-DD のDataFrameを返す.

    Args:
        ohlcv_frame: OHLCVデータを含むDataFrame（日次）.

    Returns:
        pd.DataFrame: 計算された指標を含むDataFrame（indexはYYYY-MM-DD形式の日付）.
    """
    date_key = _date_key_series(ohlcv_frame)

    close = pd.to_numeric(ohlcv_frame["close"], errors="coerce").astype("float64")
    open_ = pd.to_numeric(ohlcv_frame["open"], errors="coerce").astype("float64")
    high = pd.to_numeric(ohlcv_frame["high"], errors="coerce").astype("float64")
    low = pd.to_numeric(ohlcv_frame["low"], errors="coerce").astype("float64")
    volume = pd.to_numeric(ohlcv_frame["volume"], errors="coerce").astype("float64")

    prev_close = close.shift(1)

    # Returns / volatility
    ret_1d = close.pct_change(1)
    ret_5d = close.pct_change(5)
    ret_20d = close.pct_change(20)

    ratio = close / prev_close
    logret_1d = ratio.where(ratio > 0).apply(math.log)
    vol_20d = logret_1d.rolling(20).std()

    # True Range / ATR(14)
    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr_14 = true_range.rolling(14).mean()

    # Trend / moving averages
    sma_5 = close.rolling(5).mean()
    sma_20 = close.rolling(20).mean()
    sma_50 = close.rolling(50).mean()
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, adjust=False).mean()

    close_over_sma_20 = close / sma_20
    close_over_sma_50 = close / sma_50

    # RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    rsi_14 = 100 - (100 / (1 + rs))

    # Stochastic (14,3)
    hh14 = high.rolling(14).max()
    ll14 = low.rolling(14).min()
    stoch_k_14 = (close - ll14) / (hh14 - ll14) * 100
    stoch_d_3 = stoch_k_14.rolling(3).mean()

    # MACD (12,26,9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_signal

    # Bollinger Bands (20,2)
    bb_mid_20 = sma_20
    bb_std_20 = close.rolling(20).std()
    bb_upper_20_2 = bb_mid_20 + 2 * bb_std_20
    bb_lower_20_2 = bb_mid_20 - 2 * bb_std_20
    bb_width_20_2 = (bb_upper_20_2 - bb_lower_20_2) / bb_mid_20
    bb_percent_b_20_2 = (close - bb_lower_20_2) / (bb_upper_20_2 - bb_lower_20_2)

    # Range / candles
    hl_range = (high - low).abs()
    body = close - open_
    upper_wick = (high - pd.concat([open_, close], axis=1).max(axis=1)).clip(lower=0)
    lower_wick = (pd.concat([open_, close], axis=1).min(axis=1) - low).clip(lower=0)

    gap = open_ - prev_close
    gap_pct = gap / prev_close

    # Volume-derived
    v_sma_20 = volume.rolling(20).mean()
    v_ratio_20 = volume / v_sma_20

    delta_close = close.diff()
    direction = (delta_close > 0).astype("int8") - (delta_close < 0).astype("int8")
    obv: pd.Series = (direction * volume).fillna(0).cumsum()

    # Breakout / levels
    hh_20 = high.rolling(20).max()
    ll_20 = low.rolling(20).min()
    close_to_hh_20 = close / hh_20
    close_to_ll_20 = close / ll_20

    ind = pd.DataFrame(
        {
            "ret_1d": ret_1d,
            "ret_5d": ret_5d,
            "ret_20d": ret_20d,
            "logret_1d": logret_1d,
            "vol_20d": vol_20d,
            "atr_14": atr_14,
            "sma_5": sma_5,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "close_over_sma_20": close_over_sma_20,
            "close_over_sma_50": close_over_sma_50,
            "rsi_14": rsi_14,
            "stoch_k_14": stoch_k_14,
            "stoch_d_3": stoch_d_3,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "bb_mid_20": bb_mid_20,
            "bb_upper_20_2": bb_upper_20_2,
            "bb_lower_20_2": bb_lower_20_2,
            "bb_width_20_2": bb_width_20_2,
            "bb_percent_b_20_2": bb_percent_b_20_2,
            "true_range": true_range,
            "hl_range": hl_range,
            "body": body,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick,
            "gap": gap,
            "gap_pct": gap_pct,
            "v_sma_20": v_sma_20,
            "v_ratio_20": v_ratio_20,
            "obv": obv,
            "hh_20": hh_20,
            "ll_20": ll_20,
            "close_to_hh_20": close_to_hh_20,
            "close_to_ll_20": close_to_ll_20,
        }
    )

    ind.index = pd.Index(date_key)
    logret_1d = pd.Series(np.log(ratio.where(ratio > 0).to_numpy()), index=ratio.index)
    return ind


def _date_key_series(df: pd.DataFrame) -> pd.Series:
    """date列から YYYY-MM-DD の Series を作る.

    Args:
        df: 日付列を含むDataFrame.

    Returns:
        pd.Series: YYYY-MM-DD 形式の日付文字列シリーズ.
    """
    s = df["date"]
    first = s.iloc[0]
    if isinstance(first, pd.Timestamp):
        return s.dt.date.astype(str)
    return s.astype(str).str.slice(0, 10)


def _validate_indicators(data: dict[Hashable, Any]) -> IndicatorsDaily:
    """Pydantic v2/v1 どちらでも通る形で IndicatorsDaily を生成する.

    Args:
        data: 指標データの辞書.

    Returns:
        IndicatorsDaily: バリデート済みの指標データオブジェクト.
    """
    # 1) NaN/inf を None に落とす（NonNegativeFloat 対策）
    cleaned: dict[str, Any] = {}
    for k, v in data.items():
        key = str(k)
        if v is None:
            cleaned[key] = None
            continue
        if isinstance(v, float) and not math.isfinite(v):
            cleaned[key] = None
            continue
        cleaned[key] = v

    # 2) Pydantic v2
    mv = getattr(IndicatorsDaily, "model_validate", None)
    if callable(mv):
        return mv(cleaned)  # type: ignore[misc]

    # 3) v1 fallback
    po = getattr(IndicatorsDaily, "parse_obj", None)
    if callable(po):
        return po(cleaned)  # type: ignore[misc]

    # 4) 最終手段
    return IndicatorsDaily(**cleaned)


def build_decision_core_by_date(
    *,
    ohlcv_by_date: dict[str, OhlcvDaily],
    indicators_by_date: dict[str, IndicatorsDaily],
    policy: UserPolicySnapshot,
) -> dict[str, DecisionCore]:
    """日付ごとに DecisionCore を生成する（常に返す）."""
    policy_id = _policy_snapshot_id(policy=policy)

    out: dict[str, DecisionCore] = {}
    for date_key in ohlcv_by_date.keys():
        ind = indicators_by_date.get(date_key, IndicatorsDaily())
        out[date_key] = _build_decision_core_for_day(
            date_key=date_key,
            ind=ind,
            policy=policy,
            policy_snapshot_id=policy_id,
        )

    return out


def _build_decision_core_for_day(
    *,
    date_key: str,
    ind: IndicatorsDaily,
    policy: UserPolicySnapshot,
    policy_snapshot_id: str,
) -> DecisionCore:
    """1日分の DecisionCore を生成する（未成立は None を入れる）."""
    hh_20 = ind.hh_20
    ll_20 = ind.ll_20

    active = hh_20 is not None and ll_20 is not None and hh_20 > ll_20
    if not active:
        return DecisionCore(
            buy_signal=BuySignal.NO,
            entry=None,
            stop=None,
            target_2r=None,
            target_3r=None,
            position_size=None,
            max_loss=None,
            time_stop_days=policy.trade_plan.time_stop_days,
            plan_score=0.0,
            rank=1,
            plan_args={"date": date_key, "status": "inactive"},
            policy_snapshot_id=policy_snapshot_id,
            warnings=["insufficient_indicators"],
        )

    assert hh_20 is not None
    assert ll_20 is not None

    # active=True なので None ではない
    entry = float(hh_20)
    stop = float(ll_20)
    risk = entry - stop

    return DecisionCore(
        buy_signal=BuySignal.NO,  # ここは後でゲート条件で YES/YES_HALF に更新
        entry=entry,
        stop=stop,
        target_2r=entry + 2.0 * risk,
        target_3r=entry + 3.0 * risk,
        position_size=0.0,
        max_loss=0.0,
        time_stop_days=policy.trade_plan.time_stop_days,
        plan_score=0.0,
        rank=1,
        plan_args={"date": date_key, "status": "active"},
        policy_snapshot_id=policy_snapshot_id,
        warnings=[],
    )


def _policy_snapshot_id(*, policy: UserPolicySnapshot) -> str:
    """policy から決定的な短いIDを生成する."""
    s = json.dumps(policy.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]
