"""Annotated PGN export — produce a PGN with humanizer comments + eval graph.

Reads a list of moves with eval, accuracy, and commentary data; emits
standard PGN with inline { %eval ... } and { %clk ... } comments plus
text annotations for blunders, brilliant moves, and critical moments.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExportMove:
    """A single move in the export."""
    ply: int
    san: str
    fen_after: str
    eval_cp: Optional[float] = None        # from side-to-move's POV after the move
    cpl: Optional[float] = None
    accuracy_pct: Optional[float] = None
    classification: Optional[str] = None   # brilliant/great/good/inaccuracy/mistake/blunder
    commentary: Optional[str] = None
    critical_moment: Optional[dict] = None  # from critical_moments.py
    plan_summary: Optional[str] = None


@dataclass
class ExportConfig:
    """Game metadata for PGN export."""
    event: str = "Chess Coach v3.0.0 Review"
    site: str = "Local"
    date: str = ""                          # YYYY.MM.DD
    round: str = "?"
    white: str = "Human"
    black: str = "Engine"
    result: str = "*"
    eco: str = "?"
    opening: str = "?"
    time_control: str = "?"


def export_pgn(moves: list[ExportMove], config: ExportConfig,
               include_eval: bool = True,
               include_accuracy: bool = True,
               include_commentary: bool = True) -> str:
    """Build a PGN string with all annotations.

    Args:
        moves: list of ExportMove in ply order
        config: game metadata
        include_eval: include { %eval ... } comments
        include_accuracy: include { %acc ... } comments
        include_commentary: include humanizer text comments
    """
    if not config.date:
        config.date = datetime.date.today().strftime("%Y.%m.%d")

    headers = [
        f'[Event "{_escape(config.event)}"]',
        f'[Site "{_escape(config.site)}"]',
        f'[Date "{config.date}"]',
        f'[Round "{_escape(config.round)}"]',
        f'[White "{_escape(config.white)}"]',
        f'[Black "{_escape(config.black)}"]',
        f'[Result "{config.result}"]',
        f'[ECO "{config.eco}"]',
        f'[Opening "{_escape(config.opening)}"]',
        f'[TimeControl "{_escape(config.time_control)}"]',
    ]
    out = "\n".join(headers) + "\n\n"

    # Build move text
    move_tokens: list[str] = []
    for i, m in enumerate(moves):
        # Move number prefix every 2 plies (after white's move)
        if m.ply % 2 == 1:
            move_number = (m.ply + 1) // 2
            move_tokens.append(f"{move_number}.")

        # The move itself
        move_str = m.san

        # Append { %eval } if present
        comments: list[str] = []
        if include_eval and m.eval_cp is not None:
            comments.append(f"%eval {_format_eval(m.eval_cp)}")
        if include_accuracy and m.accuracy_pct is not None:
            comments.append(f"%acc {m.accuracy_pct:.1f}")
        if m.critical_moment and include_commentary:
            cm = m.critical_moment
            comments.append(f"CRITICAL: {cm.get('classification', '').upper()} swing {cm.get('swing_cp', 0):.0f}cp")
        if m.classification and include_commentary:
            if m.classification in ("brilliant", "great"):
                comments.append(f"[{m.classification.upper()}]")
            elif m.classification in ("mistake", "blunder"):
                comments.append(f"[{m.classification.upper()}]")
        if m.commentary and include_commentary:
            comments.append(_escape(m.commentary))
        if m.plan_summary and m.ply == 1:
            comments.append(f"PLAN: {_escape(m.plan_summary)}")

        if comments:
            move_str += " { " + "; ".join(comments) + " }"
        move_tokens.append(move_str)

    # Append result
    move_tokens.append(config.result)

    # Wrap at 80 chars
    out += _wrap_text(" ".join(move_tokens), 80) + "\n"
    return out


def export_pgn_to_file(path: str, moves: list[ExportMove], config: ExportConfig,
                       **kwargs) -> None:
    """Write a PGN to disk."""
    pgn = export_pgn(moves, config, **kwargs)
    with open(path, "w", encoding="utf-8") as f:
        f.write(pgn)


def export_review_report(moves: list[ExportMove], config: ExportConfig,
                         overall_accuracy: float,
                         critical_moments_count: int,
                         rating_estimate: int) -> str:
    """Build a textual review report (separate from PGN)."""
    lines = [
        "=" * 60,
        "  CHESS COACH v3.0.0 — GAME REVIEW",
        "=" * 60,
        "",
        f"Event:       {config.event}",
        f"Date:        {config.date}",
        f"White:       {config.white}",
        f"Black:       {config.black}",
        f"Result:      {config.result}",
        f"Opening:     {config.opening} ({config.eco})",
        "",
        "-" * 60,
        "  STATISTICS",
        "-" * 60,
        f"Overall accuracy:      {overall_accuracy:.1f}%",
        f"Estimated rating:      ~{rating_estimate} ELO",
        f"Critical moments:      {critical_moments_count}",
        f"Total moves:           {len(moves)}",
        "",
    ]
    # Classification summary
    cls_counts: dict[str, int] = {}
    for m in moves:
        if m.classification:
            cls_counts[m.classification] = cls_counts.get(m.classification, 0) + 1
    if cls_counts:
        lines.append("Move classifications:")
        for cls in ("brilliant", "great", "good", "inaccuracy", "mistake", "blunder"):
            if cls in cls_counts:
                lines.append(f"  {cls:12s}: {cls_counts[cls]:3d}")
        lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def _escape(s: str) -> str:
    """Escape a string for PGN header value."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _format_eval(cp: float) -> str:
    """Format centipawn eval for { %eval } comment."""
    if abs(cp) >= 9900:
        # Mate score approximation
        if cp > 0:
            return "#+99"
        return "#-99"
    return f"{cp / 100:+.2f}"


def _wrap_text(text: str, width: int) -> str:
    """Wrap text at width, breaking only at spaces."""
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            if cur:
                cur += " " + w
            else:
                cur = w
    if cur:
        lines.append(cur)
    return "\n".join(lines)
