"""
src/main.py

このファイルは「リポジトリ直下（src/）での実行エントリポイント」です。

設計意図:
- CLI/バッチ前提の“入口”を 1 箇所（src/main.py）に固定する
- 入口の I/O 境界（引数→RunRequest 変換）は market_decision_engine.entrypoints.parser に閉じる
- 実行制御（RunRequest→main.run 呼び出し/終了コード変換）は market_decision_engine.entrypoints.handler に閉じる
- 将来 Django/FastAPI 化しても core 実行（main.run 相当）を移植しやすくする

注意:
- `python main.py` は “スクリプト実行” のため import 解決が壊れやすい。
  そのため、本ファイルは `src/` を sys.path に追加してパッケージ import を成立させる。
"""

from __future__ import annotations

import sys
from typing import Sequence


def run(argv: Sequence[str] | None = None) -> int:
    """
    共通実行関数（CLI/バッチから利用可能な薄い入口）。

    Args:
        argv: コマンドライン引数（sys.argv[1:] 相当）。None の場合は sys.argv[1:] を使用。

    Returns:
        終了コード。
        - 0: 正常終了
        - 2: 入口層の欠落/インポート失敗（実行不能）
        - その他: handler 側が決定（例外→終了コードの方針は handler の責務）
    """
    if argv is None:
        argv = sys.argv[1:]

    exit_code = 0

    return int(exit_code)


def main() -> None:
    """スクリプト実行用 main。"""
    exit_code = run()
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
