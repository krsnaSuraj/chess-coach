"""Internationalization: English, Hindi, Spanish, French, German.

SOTA 2026 standard for chess UIs. Lichess supports 100+ languages;
we ship 5 to start (the chess world's most-spoken languages).
"""

from chess_coach.i18n import en, hi, es, fr, de
from chess_coach.i18n.loader import I18n, get_string, available_languages, language_name

__all__ = [
    "I18n",
    "get_string",
    "available_languages",
    "language_name",
    "en",
    "hi",
    "es",
    "fr",
    "de",
]
