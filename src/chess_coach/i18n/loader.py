"""i18n runtime: lookup strings by language code, format with placeholders."""

from __future__ import annotations

from typing import Any

from chess_coach.i18n import en, hi, es, fr, de

LANGUAGES: dict[str, Any] = {
    "en": en,
    "hi": hi,
    "es": es,
    "fr": fr,
    "de": de,
}

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "हिन्दी (Hindi)",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
}

DEFAULT_LANGUAGE = "en"


class I18n:
    """Internationalization helper. Holds the current language + lookup logic."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self._language = language if language in LANGUAGES else DEFAULT_LANGUAGE

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, code: str) -> None:
        if code in LANGUAGES:
            self._language = code

    def t(self, key: str, **kwargs: Any) -> str:
        """Translate a key, formatting with kwargs. Falls back to English, then to the key itself."""
        mod = LANGUAGES.get(self._language, en)
        val = getattr(mod, key, None)
        if val is None and self._language != DEFAULT_LANGUAGE:
            val = getattr(en, key, None)
        if val is None:
            return key
        if kwargs:
            try:
                return val.format(**kwargs)
            except (KeyError, IndexError):
                return val
        return val


_default_i18n = I18n()


def get_string(key: str, language: str | None = None, **kwargs: Any) -> str:
    """Convenience function: get a translated string."""
    if language:
        i = I18n(language)
        return i.t(key, **kwargs)
    return _default_i18n.t(key, **kwargs)


def available_languages() -> list[str]:
    return list(LANGUAGES.keys())


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)
