"""i18n manager — localisation support for TenderClaw (it/en).

Loads JSON string catalogs from the same directory and exposes a simple
``t(key, locale, **kwargs)`` function with format-string interpolation and
graceful fallback to English or the raw key.

Usage::

    from backend.i18n.i18n_manager import i18n

    msg = i18n.t("intent.implement")
    msg_it = i18n.t("skill.selected", locale="it", skill_name="ralplan", confidence=0.85)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("tenderclaw.i18n")

_LOCALES_DIR = Path(__file__).parent


class I18nManager:
    """Loads string catalogs from ``*.json`` files next to this module.

    Supported locales are inferred from the JSON file names (``en.json``
    → locale ``"en"``). If a key is missing in the requested locale the
    manager falls back to ``"en"``, and if still missing it returns the
    raw key so callers never receive an empty string.
    """

    def __init__(self, default_locale: str = "en") -> None:
        self._locale: str = default_locale
        self._strings: dict[str, dict[str, str]] = {}
        self._load_all()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        """Discover and load all ``*.json`` catalogs in the locales directory."""
        for path in sorted(_LOCALES_DIR.glob("*.json")):
            locale = path.stem
            try:
                data = json.loads(path.read_text("utf-8"))
                if isinstance(data, dict):
                    self._strings[locale] = {str(k): str(v) for k, v in data.items()}
                    logger.debug("i18n: loaded locale '%s' (%d strings)", locale, len(data))
            except Exception as exc:
                logger.warning("i18n: failed to load %s: %s", path, exc)

    def reload(self) -> None:
        """Reload all catalogs from disk (useful after hot-deploy)."""
        self._strings.clear()
        self._load_all()

    # ------------------------------------------------------------------
    # Locale management
    # ------------------------------------------------------------------

    @property
    def locale(self) -> str:
        """Currently active locale."""
        return self._locale

    def set_locale(self, locale: str) -> None:
        """Set the default locale for subsequent ``t()`` calls."""
        if locale not in self._strings:
            logger.warning("i18n: unknown locale '%s', keeping '%s'", locale, self._locale)
            return
        self._locale = locale

    def available_locales(self) -> list[str]:
        """Return the list of loaded locale codes."""
        return sorted(self._strings.keys())

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def t(self, key: str, locale: str | None = None, **kwargs: Any) -> str:
        """Translate *key* in the requested (or default) locale.

        Falls back to ``"en"`` if the key is absent in the target locale,
        and to the raw *key* string if absent everywhere.

        Format-string interpolation is performed when keyword arguments are
        provided; any formatting error is swallowed and the unformatted
        template is returned instead.

        Args:
            key:    Dot-separated translation key, e.g. ``"intent.implement"``.
            locale: Override the default locale for this call.
            **kwargs: Values forwarded to ``str.format(**kwargs)``.

        Returns:
            Translated (and optionally formatted) string.
        """
        loc = locale or self._locale

        # Look up: preferred locale → English fallback → raw key
        template = (
            self._strings.get(loc, {}).get(key)
            or self._strings.get("en", {}).get(key)
            or key
        )

        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                return template

        return template

    def has_key(self, key: str, locale: str | None = None) -> bool:
        """Return True if *key* exists in the given (or default) locale."""
        loc = locale or self._locale
        return key in self._strings.get(loc, {})


# Module-level singleton — ready to use after import
i18n = I18nManager()
