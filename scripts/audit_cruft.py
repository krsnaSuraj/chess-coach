"""Audit new modules for cruft, dead code, and unused imports."""
from __future__ import annotations
import ast
import os
import re

ROOT = "src/chess_coach"

# --- 1. Unused imports ---
real_unused = []
for root, _, files in os.walk(ROOT):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as fh:
                src = fh.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    for n in node.names:
                        if n.name == "annotations":
                            continue
                        imports.append((n.asname or n.name, node.module))
                elif isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append(((n.asname or n.name).split(".")[0], None))
            used = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used.add(node.id)
                elif isinstance(node, ast.Attribute):
                    n = node
                    while isinstance(n, ast.Attribute):
                        n = n.value
                    if isinstance(n, ast.Name):
                        used.add(n.id)
            for name, mod in imports:
                if name not in used and name not in ("TYPE_CHECKING", "annotations"):
                    real_unused.append((p, name, mod))

# Group by file
from collections import defaultdict
by_file = defaultdict(list)
for p, name, mod in real_unused:
    by_file[p].append((name, mod))

print("=== UNUSED IMPORTS ===")
for p, items in sorted(by_file.items()):
    print(f"\n{p}")
    for name, mod in items:
        print(f"  {name}  # from {mod}")

# --- 2. Cruft patterns ---
print("\n=== CRUFT PATTERNS ===")
for root, _, files in os.walk(ROOT):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as fh:
                src = fh.read()
            for label, pat in [
                ("TODO", r"#\s*TODO"),
                ("FIXME", r"#\s*FIXME"),
                ("XXX", r"#\s*XXX"),
                ("HACK", r"#\s*HACK"),
                ("NotImplementedError", r"raise\s+NotImplementedError"),
                ("print(", r"\bprint\("),
                ("breakpoint()", r"breakpoint\("),
                ("sys.exit()", r"\bsys\.exit\("),
                ("input(", r"\binput\("),
            ]:
                matches = re.findall(pat, src)
                if matches:
                    print(f"  {p}: {label}: {len(matches)}")

# --- 3. Find duplicate / overlapping module functions ---
print("\n=== DUPLICATE FUNCTIONS ===")
fn_defs = defaultdict(list)
for root, _, files in os.walk(ROOT):
    for f in files:
        if f.endswith(".py"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as fh:
                src = fh.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn_defs[node.name].append(p)
for name, files in sorted(fn_defs.items()):
    if len(files) > 1 and not name.startswith("__"):
        # Filter to truly duplicate (same simple name across unrelated files)
        if len(set(files)) > 1:
            # Check if it's in __init__.py exports (those are re-exports, OK)
            non_init = [f for f in files if not f.endswith("__init__.py")]
            if len(non_init) > 1:
                print(f"  {name}: {non_init}")
