"""Auto-remove unused imports from a list of files.

This script parses each file with AST, finds unused imports, and rewrites
the file without them. Safe to run repeatedly (idempotent).
"""
from __future__ import annotations
import ast
import os
import re

FILES = [
    "src/chess_coach/pgn/comments.py",
    "src/chess_coach/eval/cpl.py",
    "src/chess_coach/eval/perf_rating.py",
    "src/chess_coach/db/pgn_index.py",
    "src/chess_coach/coach/oprep.py",
    "src/chess_coach/coach/training_plan.py",
    "src/chess_coach/coach/weakness.py",
    "src/chess_coach/tournament/bracket.py",
    "src/chess_coach/tournament/swiss.py",
    "src/chess_coach/openings/eco.py",
    "src/chess_coach/openings/polyglot.py",
    "src/chess_coach/lichess/oauth.py",
    "src/chess_coach/lichess/study_sync.py",
    "src/chess_coach/lichess/teams.py",
    "src/chess_coach/engines/multi_engine_pool.py",
    "src/chess_coach/tablebase/syzygy.py",
    "src/chess_coach/widgets/captured_pieces.py",
    "src/chess_coach/widgets/eval_bar.py",
    "src/chess_coach/widgets/settings_dialog.py",
    "src/chess_coach/widgets/toast.py",
]


def fix_file(path: str) -> int:
    """Remove unused imports from a file. Returns count removed."""
    with open(path, "r", encoding="utf-8") as fh:
        src = fh.read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"  {path}: parse error: {e}")
        return 0
    # Collect imports (with source line numbers)
    import_lines: dict[int, list[str]] = {}  # line -> names actually used
    import_nodes = []  # (lineno, end_lineno, node)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            import_nodes.append((node.lineno, node.end_lineno, node))
        elif isinstance(node, ast.Import):
            import_nodes.append((node.lineno, node.end_lineno, node))
    # Find used names
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            n = node
            while isinstance(n, ast.Attribute):
                n = n.value
            if isinstance(n, ast.Name):
                used.add(n.id)
    # Walk imports and determine which to keep
    new_src = src
    total_removed = 0
    # Process in reverse line order to preserve offsets
    for lineno, end_lineno, node in sorted(import_nodes, key=lambda x: -x[0]):
        if isinstance(node, ast.ImportFrom):
            # Get original source lines
            lines = src.split("\n")
            orig = "\n".join(lines[lineno - 1:end_lineno])
            kept = []
            for n in node.names:
                local = n.asname or n.name
                if local in used or local == "annotations":
                    kept.append(n)
            if len(kept) == 0:
                # Remove entire line (including any trailing parens)
                new_src = new_src.replace(orig + "\n", "", 1) if orig + "\n" in new_src else _remove_line(new_src, lineno, end_lineno)
                total_removed += len(node.names)
            elif len(kept) < len(node.names):
                # Replace with reduced import
                if node.module:
                    names_str = ", ".join(_format_alias(n) for n in kept)
                    if len(kept) == 1:
                        replacement = f"from {node.module} import {names_str}"
                    else:
                        replacement = f"from {node.module} import (\n    {names_str},\n)"
                else:
                    names_str = ", ".join(_format_alias(n) for n in kept)
                    replacement = f"import {names_str}"
                new_src = new_src.replace(orig, replacement, 1)
                total_removed += len(node.names) - len(kept)
        elif isinstance(node, ast.Import):
            lines = src.split("\n")
            orig = "\n".join(lines[lineno - 1:end_lineno])
            kept = []
            for n in node.names:
                local = (n.asname or n.name).split(".")[0]
                if local in used:
                    kept.append(n)
            if len(kept) == 0:
                new_src = _remove_line(new_src, lineno, end_lineno)
                total_removed += len(node.names)
            elif len(kept) < len(node.names):
                names_str = ", ".join(_format_alias(n) for n in kept)
                replacement = f"import {names_str}"
                new_src = new_src.replace(orig, replacement, 1)
                total_removed += len(node.names) - len(kept)
    if new_src != src:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(new_src)
    return total_removed


def _format_alias(n: ast.alias) -> str:
    if n.asname:
        return f"{n.name} as {n.asname}"
    return n.name


def _remove_line(src: str, lineno: int, end_lineno: int) -> str:
    lines = src.split("\n")
    del lines[lineno - 1:end_lineno]
    return "\n".join(lines)


for f in FILES:
    if not os.path.exists(f):
        print(f"  {f}: missing")
        continue
    n = fix_file(f)
    print(f"  {f}: removed {n}")
