"""共通例外定義（import なしで完結させる）。

設計意図:
- パイプライン全体で共通の失敗モデル（致命的 / 縮退 / スキップ）を揃える。
- I/O や外部依存を持たず、最下層に置ける「根のモジュール」として機能させる。
- 例外メッセージは英語で統一する（ログ・CI の一貫性）。
"""


class MarketDecisionEngineError(Exception):
    """本プロジェクトの基底例外。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class FatalError(MarketDecisionEngineError):
    """バッチ全体を停止すべき致命的障害（契約違反・整合性破綻など）。"""


class DegradedError(MarketDecisionEngineError):
    """縮退運転へ移行すべき障害（LLM 不調・ML 不調など）。"""


class SkipSymbol(MarketDecisionEngineError):
    """銘柄単位でのスキップ（データ欠損など）。"""


class ContractViolation(FatalError):
    """契約（schemas）逸脱。市場バッチ停止を原則とする。"""


class DataQualityError(DegradedError):
    """データ品質問題。原則は安全側（NO/YES_HALF/スキップ）へ倒す。"""


class ExternalServiceError(DegradedError):
    """外部サービス障害（例: データ取得失敗、LLM 呼び出し失敗）。"""


class ConfigurationError(FatalError):
    """設定不備（起動前に検知し停止する）。"""
