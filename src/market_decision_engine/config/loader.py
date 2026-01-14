"""設定ファイルローダ（I/O 境界）。

設計意図:
- JSON/YAML 等の読み込み（I/O）に責務を限定する。
- 合成・正規化・検証は resolver/schemas に寄せる。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from market_decision_engine.exceptions import ConfigurationError


def load_config(path: str | Path) -> dict[str, Any]:
    """設定ファイルを読み込む（JSON / YAML）。

    Args:
        path: 設定ファイルパス。

    Returns:
        読み込まれた設定（辞書）。

    Raises:
        ConfigurationError: ファイルが存在しない、形式不正、読み込み失敗など。
    """
    p = Path(path)
    if not p.exists():
        raise ConfigurationError(f"Config file not found: {p}")

    if not p.is_file():
        raise ConfigurationError(f"Config path is not a file: {p}")

    suffix = p.suffix.lower()

    try:
        if suffix in {".json"}:
            return _load_json(p)

        if suffix in {".yml", ".yaml"}:
            return _load_yaml(p)

        raise ConfigurationError(f"Unsupported config format: {suffix}")

    except ConfigurationError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ConfigurationError(f"Failed to load config: {p}") from e


def _load_json(path: Path) -> dict[str, Any]:
    """JSON を読み込む。"""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON: {e}") from e

    if not isinstance(data, dict):
        raise ConfigurationError("Config root must be a JSON object (dict).")

    return data


def _load_yaml(path: Path) -> dict[str, Any]:
    """YAML を読み込む（PyYAML が必要）。"""
    try:
        import yaml  # type: ignore
    except Exception as e:  # noqa: BLE001
        raise ConfigurationError("PyYAML is required to load YAML config files.") from e

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:  # noqa: BLE001
        raise ConfigurationError(f"Invalid YAML: {e}") from e

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ConfigurationError("Config root must be a YAML mapping (dict).")

    return data
