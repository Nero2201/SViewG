from __future__ import annotations

import json
import sys
from pathlib import Path

_STRINGS: dict[str, dict[str, str]] = {}
LANGUAGE_NAMES: dict[str, str] = {}

_current: str = 'de'

# When frozen by PyInstaller, files land in sys._MEIPASS; otherwise next to project root.
_BASE = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
_LANG_DIR = _BASE / 'lang'


def _load_languages() -> None:
    for path in sorted(_LANG_DIR.glob('lang_*.json')):
        try:
            with open(path, encoding='utf-8') as f:
                data: dict = json.load(f)
            meta = data.get('meta', {})
            code: str = meta.get('code', path.stem.removeprefix('lang_'))
            name: str = meta.get('name', code)
            LANGUAGE_NAMES[code] = name
            _STRINGS[code] = {k: v for k, v in data.items() if k != 'meta'}
        except Exception:
            pass


_load_languages()


def set_language(lang: str) -> None:
    global _current
    if lang in _STRINGS:
        _current = lang


def current_language() -> str:
    return _current


def tr(key: str) -> str:
    fallback = next(iter(_STRINGS.values()), {}) if _STRINGS else {}
    return _STRINGS.get(_current, fallback).get(key, fallback.get(key, key))
