"""Audit NEW modules (post-Phase H) for cruft, dead code."""
from __future__ import annotations
import ast
import os
import re

# New modules to audit
NEW_DIRS = [
    "src/chess_coach/pgn",
    "src/chess_coach/eval",
    "src/chess_coach/db",
    "src/chess_coach/coach",
    "src/chess_coach/tournament",
    "src/chess_coach/openings",
    "src/chess_coach/lichess",
    "src/chess_coach/engines",
    "src/chess_coach/tablebase",
    "src/chess_coach/variants",
    "src/chess_coach/widgets",
    "src/chess_coach/capabilities",
    "src/chess_coach/training",
    "src/chess_coach/api",
]

print("=" * 70)
print("CRUFT AUDIT - NEW MODULES")
print("=" * 70)

for d in NEW_DIRS:
    if not os.path.isdir(d):
        continue
    print(f"\n--- {d} ---")
    for root, _, files in os.walk(d):
        for f in files:
            if not f.endswith(".py"):
                continue
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as fh:
                src = fh.read()
            # TODO/FIXME
            for label, pat in [
                ("TODO", r"#\s*TODO[:\s]"),
                ("FIXME", r"#\s*FIXME"),
                ("XXX", r"#\s*XXX"),
                ("HACK", r"#\s*HACK"),
                ("NotImpl", r"raise\s+NotImplementedError"),
                ("print", r"\bprint\("),
                ("breakpoint", r"breakpoint\("),
                ("input", r"\binput\("),
            ]:
                matches = re.findall(pat, src)
                if matches:
                    print(f"  {p}: {label}: {len(matches)}")
            # Check for unused imports within this file
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
                        imports.append(n.asname or n.name)
                elif isinstance(node, ast.Import):
                    for n in node.names:
                        imports.append((n.asname or n.name).split(".")[0])
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
            unused = [i for i in imports if i not in used]
            if unused:
                print(f"  {p}: unused imports: {unused}")
            # Check for empty pass / placeholder code
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        # Check for docstring
                        if not (isinstance(node.body[0], ast.Expr) and
                                isinstance(node.body[0].value, (ast.Str, ast.Constant))):
                            print(f"  {p}: stub function: {node.name}()")
