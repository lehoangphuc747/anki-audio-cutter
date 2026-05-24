# -*- coding: utf-8 -*-
"""
Minimal i18n module for Audio Card Cutter.

Usage:
    from ._tr import tr
    tr("key")                   # simple lookup
    tr("key", name="value")     # with interpolation

Adding a language:
    1. Copy  i18n/en.json  →  i18n/<lang>.json
    2. Translate every value (keep the keys unchanged).
    3. Set  "language": "<lang>"  in the add-on config, or leave
       blank to auto-detect from Anki's UI language.
"""

from __future__ import annotations

import json
import os
from typing import Optional

_ADDON_ROOT = os.path.dirname(__file__)
_I18N_DIR = os.path.join(_ADDON_ROOT, "i18n")

_fallback: dict[str, str] = {}
_translations: dict[str, str] = {}


def _load_lang(lang: str) -> dict[str, str]:
    path = os.path.join(_I18N_DIR, f"{lang}.json")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def init_i18n(lang: Optional[str] = None) -> None:
    """Call once at add-on startup.  *lang* = ISO code or ``None`` for
    auto-detect (Anki UI language → English fallback)."""
    global _translations, _fallback  # noqa: PLW0603
    _fallback = _load_lang("en")

    if not lang:
        # Try to detect from Anki
        try:
            import anki.lang
            lang = anki.lang.current_lang  # e.g. "en", "vi", "ja"
        except Exception:
            lang = "en"

    if lang and lang != "en":
        _translations = _load_lang(lang)
    else:
        _translations = {}


def tr(key: str, **kwargs: object) -> str:
    """Return the translated string for *key*.

    Falls back: current language → English → raw key.
    Supports ``{name}`` placeholders via *kwargs*.
    """
    text = _translations.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass  # return un-interpolated rather than crash
    return text
