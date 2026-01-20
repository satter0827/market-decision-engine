"""Rules: pretty view for OHLCV and indicators per date."""
from __future__ import annotations

from typing import Mapping, Sequence

from tabulate import tabulate # type: ignore

from market_decision_engine.contract.schemas.market import IndicatorsDaily, OhlcvDaily, DecisionCore


DailyPack = Mapping[str, Mapping[str, OhlcvDaily | IndicatorsDaily | DecisionCore]]


def format_ohlcv_table(
    *,
    daily_by_date: DailyPack,
    start: str | None = None,
    end: str | None = None,
    last_n: int = 20,
    tablefmt: str = "github",
) -> str:
    """日次OHLCVをテーブル表示用文字列に整形する."""
    date_keys = _select_dates(
        daily_by_date=daily_by_date,
        start=start,
        end=end,
        last_n=last_n,
    )

    headers = ["date", "open", "high", "low", "close", "volume"]
    rows: list[list[object]] = []

    for d in date_keys:
        pack = daily_by_date[d]
        ohlcv = pack.get("ohlcv")

        if not isinstance(ohlcv, OhlcvDaily):
            # データ欠損は空で出す（運用で見やすい）
            rows.append([d, None, None, None, None, None])
            continue

        rows.append([d, ohlcv.open, ohlcv.high, ohlcv.low, ohlcv.close, ohlcv.volume])

    return tabulate(rows, headers=headers, tablefmt=tablefmt, floatfmt=".6f")


def format_indicators_table(
    *,
    daily_by_date: DailyPack,
    start: str | None = None,
    end: str | None = None,
    last_n: int = 20,
    tablefmt: str = "github",
    columns: Sequence[str] | None = None,
) -> str:
    """日次テクニカル指標をテーブル表示用文字列に整形する."""
    date_keys = _select_dates(
        daily_by_date=daily_by_date,
        start=start,
        end=end,
        last_n=last_n,
    )

    cols = list(
        columns
        if columns is not None
        else [
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "logret_1d",
            "vol_20d",
            "atr_14",
            "sma_5",
            "sma_20",
            "sma_50",
            "ema_20",
            "ema_50",
            "close_over_sma_20",
            "close_over_sma_50",
            "rsi_14",
            "stoch_k_14",
            "stoch_d_3",
            "macd",
            "macd_signal",
            "macd_hist",
            "bb_mid_20",
            "bb_upper_20_2",
            "bb_lower_20_2",
            "bb_width_20_2",
            "bb_percent_b_20_2",
            "true_range",
            "hl_range",
            "body",
            "upper_wick",
            "lower_wick",
            "gap",
            "gap_pct",
            "v_sma_20",
            "v_ratio_20",
            "obv",
            "hh_20",
            "ll_20",
            "close_to_hh_20",
            "close_to_ll_20",
        ]
    )

    headers = ["date", *cols]
    rows: list[list[object]] = []

    for d in date_keys:
        pack = daily_by_date[d]
        ind = pack.get("indicators")
        if not isinstance(ind, IndicatorsDaily):
            ind = IndicatorsDaily()

        row: list[object] = [d]
        for c in cols:
            row.append(getattr(ind, c, None))
        rows.append(row)

    return tabulate(rows, headers=headers, tablefmt=tablefmt, floatfmt=".6f")


def _select_dates(
    *,
    daily_by_date: DailyPack,
    start: str | None,
    end: str | None,
    last_n: int,
) -> list[str]:
    date_keys = sorted(daily_by_date.keys())
    if start is not None:
        date_keys = [d for d in date_keys if d >= start]
    if end is not None:
        date_keys = [d for d in date_keys if d <= end]
    if last_n > 0:
        date_keys = date_keys[-last_n:]
    return date_keys


def format_decision_table(
    *,
    daily_by_date: DailyPack,
    start: str | None = None,
    end: str | None = None,
    last_n: int = 20,
    tablefmt: str = "github",
) -> str:
    """日次 DecisionCore をテーブル表示用文字列に整形する.

    Args:
        daily_by_date: 日次データパック（日付キー辞書）
        start: 開始日（YYYY-MM-DD形式）, Noneの場合は最初から
        end: 終了日（YYYY-MM-DD形式）, Noneの場合は最後まで
        last_n: 最後からN件だけ表示（0以下の場合は全件）
        tablefmt: tabulateのtablefmt指定

    Returns:
        整形済みテーブル文字列
    """
    date_keys = _select_dates(
        daily_by_date=daily_by_date,
        start=start,
        end=end,
        last_n=last_n,
    )

    headers = [
        "date",
        "buy_signal",
        "entry",
        "stop",
        "target_2r",
        "target_3r",
        "position_size",
        "max_loss",
        "time_stop_days",
        "plan_score",
        "rank",
    ]

    rows: list[list[object]] = []

    for d in date_keys:
        pack = daily_by_date[d]
        dc = pack.get("decision_core")

        if not isinstance(dc, DecisionCore):
            rows.append([d, None, None, None, None, None, None, None, None, None, None])
            continue

        rows.append(
            [
                d,
                dc.buy_signal,
                dc.entry,
                dc.stop,
                dc.target_2r,
                dc.target_3r,
                dc.position_size,
                dc.max_loss,
                dc.time_stop_days,
                dc.plan_score,
                dc.rank,
            ]
        )

    return tabulate(rows, headers=headers, tablefmt=tablefmt, floatfmt=".6f")
