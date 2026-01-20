"""Market Decision Engine における例外定義モジュール.

Purpose:
    - 設定不備や契約違反を明確に区別する（利用者/開発者が原因を特定しやすい）
    - パイプライン制御（銘柄スキップ / 縮退 / バッチ停止）を明示する

Notes:
    - 例外メッセージは英語（ログ/CI の一貫性）。
    - LLM は翻訳器であり、LLM 障害は「縮退（DecisionCoreのみ）」へ倒すのが原則。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

ErrorSeverity = Literal["error", "degraded", "skip", "fatal"]


@dataclass(eq=False, slots=True)
class MarketDecisionEngineError(Exception):
    """プロジェクト共通の基底例外.

    Attributes:
        - message: 例外メッセージ（英語）
        - code: 機械判定用の短い識別子
        - severity: パイプライン上の重要度（error/degraded/skip/fatal）
        - context: 追加情報（ticker, step, policy_snapshot_id など任意）
    """

    message: str
    code: str = "MDE_ERROR"
    severity: ErrorSeverity = "error"
    context: dict[str, Any] = field(default_factory=dict)

    def with_context(self, **kwargs: Any) -> "MarketDecisionEngineError":
        """コンテキストを追加した同型例外を返す.

        Raises:
            - MarketDecisionEngineError: 常に返す（例外自体は raise しない）
        """
        merged = dict(self.context)
        merged.update(kwargs)
        return type(self)(
            message=self.message,
            code=self.code,
            severity=self.severity,
            context=merged,
        )


class ContractError(MarketDecisionEngineError):
    """呼び出し契約違反（開発者/利用者の誤用）.

    Examples:
        - fit 前に explain を呼ぶ
        - Contract-first の schema を満たさない入力を渡す
    """

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="CONTRACT_ERROR",
            severity="fatal",
            context=dict(context or {}),
        )


class ConfigurationError(MarketDecisionEngineError):
    """設定不備（起動前に検出したい種類のエラー）."""

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            severity="fatal",
            context=dict(context or {}),
        )

class DataError(MarketDecisionEngineError):
    """データ起因のエラー（欠損/範囲不足/品質不備など）."""

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="DATA_ERROR",
            severity="error",
            context=dict(context or {}),
        )


class ExternalDataError(DataError):
    """外部データ取得失敗（Examples: yfinance 失敗、レート制限、ネットワーク等）."""

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            context=context,
        )
        self.code = "EXTERNAL_DATA_ERROR"


class ExecutionError(MarketDecisionEngineError):
    """実行時エラー（ライブラリ例外の正規化など）.

    Examples:
        - 指標計算の数値例外
        - 予期しない型/形状
    """

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="EXECUTION_ERROR",
            severity="error",
            context=dict(context or {}),
        )


class LLMError(MarketDecisionEngineError):
    """LLM 関連のエラー（ShortSummary 生成の失敗など）.

    Policy:
        - DecisionCore を維持して縮退するため severity は degraded を既定とする。
    """

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="LLM_ERROR",
            severity="degraded",
            context=dict(context or {}),
        )


class SkipTicker(MarketDecisionEngineError):
    """当該銘柄をスキップするための制御例外.

    Examples:
        - required daily data is missing
        - contract is satisfied but decision cannot be computed safely
    """

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="SKIP_TICKER",
            severity="skip",
            context=dict(context or {}),
        )


class FatalPipelineError(MarketDecisionEngineError):
    """バッチ全体を停止すべき致命的エラー.

    Examples:
        - 契約違反（schema破り）
        - 依存方向違反や不整合が検出された
        - 出力の監査可能性を損なう事象
    """

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="FATAL_PIPELINE_ERROR",
            severity="fatal",
            context=dict(context or {}),
        )
