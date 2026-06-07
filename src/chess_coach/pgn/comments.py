"""Structured PGN comment parsing.

Modern PGN comments include structured data in `{ }` blocks:
- `{[%eval 0.34]}` — engine evaluation (pawns, +M5 for mate)
- `{[%clk 0:01:23]}` — clock time
- `{[%csl Ra1,Rb2,Yg3]}` — colored arrow targets (Lichess)
- `{[%cal Ge2e4,Re2e4]}` — colored arrows (Lichess)
- `{[%mdt 0:00:42]}` — move duration (Lichess)

This module parses these structured directives into typed values, while
keeping the plain text comment content accessible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import (
    List, Optional,
)


EVAL_RE = re.compile(r"\[%eval\s+([^\]]+)\]")
CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")
CSL_RE = re.compile(r"\[%csl\s+([^\]]+)\]")
CAL_RE = re.compile(r"\[%cal\s+([^\]]+)\]")
MDT_RE = re.compile(r"\[%mdt\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]")


def _parse_pawns(token: str) -> Optional[float]:
    """Parse an eval token. Returns cp if '#M' returns None (mate)."""
    token = token.strip()
    if token.startswith("#"):
        return None
    try:
        return float(token)
    except ValueError:
        return None


def parse_mate(token: str) -> Optional[int]:
    """Parse mate token '#M5' or '#-3' into signed plies-to-mate.

    Returns None if not a mate token. Positive = white mates, negative = black.
    """
    token = token.strip()
    if not token.startswith("#"):
        return None
    try:
        return int(token[1:])
    except ValueError:
        return None


def _parse_clock(hours: str, minutes: str, seconds: str) -> float:
    return int(hours) * 3600.0 + int(minutes) * 60.0 + float(seconds)


@dataclass
class StructuredComment:
    """Parsed structured PGN comment."""

    text: str = ""
    eval_cp: Optional[float] = None
    mate_in: Optional[int] = None
    clock_seconds: Optional[float] = None
    arrows_colored: List[str] = field(default_factory=list)
    squares_colored: List[str] = field(default_factory=list)
    move_duration: Optional[float] = None

    @property
    def has_eval(self) -> bool:
        return self.eval_cp is not None or self.mate_in is not None

    @property
    def has_clock(self) -> bool:
        return self.clock_seconds is not None

    @property
    def eval_string(self) -> str:
        if self.mate_in is not None:
            return f"#{self.mate_in}"
        if self.eval_cp is not None:
            return f"{self.eval_cp:+.2f}"
        return ""

    @property
    def clock_string(self) -> str:
        if self.clock_seconds is None:
            return ""
        h, rem = divmod(self.clock_seconds, 3600.0)
        m, s = divmod(rem, 60.0)
        # PGN standard [%clk H:MM:SS.d] — always emit all three components
        return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def parse_comment(text: str) -> StructuredComment:
    """Parse a single PGN comment into a structured object."""
    result = StructuredComment(text=text or "")

    if not text:
        return result

    m = EVAL_RE.search(text)
    if m:
        token = m.group(1)
        result.mate_in = parse_mate(token)
        if result.mate_in is None:
            result.eval_cp = _parse_pawns(token)

    m = CLK_RE.search(text)
    if m:
        result.clock_seconds = _parse_clock(m.group(1), m.group(2), m.group(3))

    m = CSL_RE.search(text)
    if m:
        result.squares_colored = [s for s in m.group(1).split(",") if s]

    m = CAL_RE.search(text)
    if m:
        result.arrows_colored = [s for s in m.group(1).split(",") if s]

    m = MDT_RE.search(text)
    if m:
        result.move_duration = _parse_clock(m.group(1), m.group(2), m.group(3))

    return result


def is_structured_comment(text: str) -> bool:
    """Return True if the comment contains any structured directive."""
    if not text:
        return False
    return bool(
        EVAL_RE.search(text)
        or CLK_RE.search(text)
        or CSL_RE.search(text)
        or CAL_RE.search(text)
        or MDT_RE.search(text)
    )


def extract_plain_comment(text: str) -> str:
    """Return the comment text with structured directives removed."""
    if not text:
        return ""
    cleaned = EVAL_RE.sub("", text)
    cleaned = CLK_RE.sub("", cleaned)
    cleaned = CSL_RE.sub("", cleaned)
    cleaned = CAL_RE.sub("", cleaned)
    cleaned = MDT_RE.sub("", cleaned)
    return cleaned.strip()


def format_comment(sc: StructuredComment) -> str:
    """Format a StructuredComment back into a PGN comment string."""
    parts: List[str] = []
    plain = (sc.text or "").strip()
    if sc.has_eval:
        parts.append(f"[%eval {sc.eval_string}]")
    if sc.has_clock:
        parts.append(f"[%clk {sc.clock_string}]")
    if sc.squares_colored:
        parts.append("[%csl " + ",".join(sc.squares_colored) + "]")
    if sc.arrows_colored:
        parts.append("[%cal " + ",".join(sc.arrows_colored) + "]")
    if sc.move_duration is not None:
        h, rem = divmod(sc.move_duration, 3600.0)
        m, s = divmod(rem, 60.0)
        if h > 0:
            parts.append(f"[%mdt {int(h)}:{int(m):02d}:{s:05.2f}]")
        else:
            parts.append(f"[%mdt {int(m)}:{s:05.2f}]")
    if plain:
        parts.insert(0, plain)
    if not parts:
        return ""
    return "{ " + " ".join(parts) + " }"


def parse_all_comments(comments: List[str]) -> List[StructuredComment]:
    """Parse a list of PGN comment strings into structured objects."""
    return [parse_comment(c) for c in comments]


__all__ = [
    "StructuredComment",
    "parse_comment",
    "parse_mate",
    "is_structured_comment",
    "extract_plain_comment",
    "format_comment",
    "parse_all_comments",
    "EVAL_RE",
    "CLK_RE",
    "CSL_RE",
    "CAL_RE",
    "MDT_RE",
]
