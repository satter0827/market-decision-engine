"""Domain model: price history and derived indicators per ticker/date."""
from __future__ import annotations

from typing import Literal

from market_decision_engine.contract.schemas.market import IndicatorsDaily, OhlcvDaily, DecisionCore
from market_decision_engine.domain.rules.market_data import (
    fetch_ohlcv_frame,
    frame_to_ohlcv_by_date,
    build_indicators_by_date,
    build_decision_core_by_date
)
from market_decision_engine.domain.rules.chart_view import (
    format_indicators_table,
    format_ohlcv_table,
    format_decision_table,
)
from market_decision_engine.contract.schemas.policy import UserPolicySnapshot

class ChartLogic:
    """ティッカー別のOHLCVとテクニカル指標を保持する.

    保持形式:
        ticker -> YYYY-MM-DD -> {"ohlcv": OhlcvDaily, "indicators": IndicatorsDaily}
    """
    def __init__(self, *, policy: UserPolicySnapshot) -> None:
        """初期化.

        Args:
            policy: 運用者側のポリシー（口座・リスク・制約など）。
        """
        self._policy = policy

        self._daily_by_ticker: dict[
            str,
            dict[str, dict[str, OhlcvDaily | IndicatorsDaily | DecisionCore]],
        ] = {}

        self._tickers: list[str] = []
        self._start: str | None = None
        self._end: str | None = None
        self._interval: str = "1d"

        self._is_loaded: bool = False

    @property
    def plan(self) -> dict[str, object]:
        """運用者側ポリシーを辞書形式で返す."""
        return self._policy.model_dump()

    @property
    def charts(self) -> dict[str, dict[str, dict[str, OhlcvDaily | IndicatorsDaily | DecisionCore]]]:
        """取得・計算済みの日次データを返す."""
        return self._daily_by_ticker

    @property
    def interval(self) -> str:
        """データ間隔を返す."""
        return self._interval

    @property
    def is_loaded(self) -> bool:
        """データが取得・計算済みかどうかを返す."""
        return self._is_loaded

    def load_charts(
        self,
        tickers: str | list[str],
        *,
        start: str | None = None,
        end: str | None = None,
        interval: str = "1d",
    ) -> None:
        """OHLCV取得→指標計算→DecisionCore生成→ticker/date配下へ保持する.
        Args:

            tickers: 取得・計算対象のティッカーまたはティッカーリスト。
            start: 取得開始日（YYYY-MM-DD形式）。Noneの場合、デフォルト期間。
            end: 取得終了日（YYYY-MM-DD形式）。Noneの場合、デフォルト期間。
            interval: 取得間隔。"1d", "1wk", "1mo"など。

        raises:
            RuntimeError: データ取得・計算に失敗した場合。
        """
        ticker_list = [tickers] if isinstance(tickers, str) else tickers

        for ticker in ticker_list:
            ohlcv_frame = fetch_ohlcv_frame(
                ticker=ticker,
                start=start,
                end=end,
                interval=interval,
            )

            ohlcv_by_date = frame_to_ohlcv_by_date(ohlcv_frame=ohlcv_frame)
            indicators_by_date = build_indicators_by_date(ohlcv_frame=ohlcv_frame)
            decision_core_by_date = build_decision_core_by_date(
                ohlcv_by_date=ohlcv_by_date,
                indicators_by_date=indicators_by_date,
                policy=self._policy,
            )

            bucket = self._daily_by_ticker.setdefault(ticker, {})

            for date_key, ohlcv_daily in ohlcv_by_date.items():
                bucket[date_key] = {
                    "ohlcv": ohlcv_daily,
                    "indicators": indicators_by_date[date_key],
                    "decision_core": decision_core_by_date[date_key],
                }

        self._tickers = ticker_list
        self._start = start
        self._end = end
        self._interval = interval
        self._is_loaded = True


    def explain(self) -> str:
        """計算結果の説明を返す."""
        return "This is a placeholder explanation."

    def scan(
        self,
        *,
        ticker: str,
        view: Literal["ohlcv", "indicators", "decision"],
        start: str | None = None,
        end: str | None = None,
        last_n: int = 20,
        tablefmt: str = "github",
    ) -> str:
        """指定した view を日次テーブルとして表示する.

        Args:
            ticker: 対象ティッカー。
            view: 表示種別（"ohlcv" | "indicators" | "decision"）。
            start: 開始日（YYYY-MM-DD）。None の場合は制限なし。
            end: 終了日（YYYY-MM-DD）。None の場合は制限なし。
            last_n: 直近 n 件のみ表示。
            tablefmt: `tabulate` の tablefmt。

        Returns:
            フォーマット済み表文字列。

        Raises:
            RuntimeError: データがロードされていない場合。
            KeyError: 指定ティッカーが存在しない場合。
            ValueError: view が不正な場合。
        """
        if not self._is_loaded:
            raise RuntimeError("Charts are not loaded. Call load_charts() first.")
        if ticker not in self._daily_by_ticker:
            raise KeyError(f"Ticker not found: {ticker}")

        if view == "ohlcv":
            formatter = format_ohlcv_table

        elif view == "indicators":
            formatter = format_indicators_table

        elif view == "decision":
            formatter = format_decision_table

        else:
            raise ValueError(f"Invalid view: {view}")

        return formatter(
            daily_by_date=self._daily_by_ticker[ticker],
            start=start,
            end=end,
            last_n=last_n,
            tablefmt=tablefmt,
        )
