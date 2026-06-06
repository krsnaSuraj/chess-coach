"""Keyboard navigation: arrow keys, space, enter, tab, shortcuts.

SOTA 2026: full keyboard-only operation, like Lichess.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyboardShortcut:
    keys: tuple[str, ...]
    description: str
    action: str


KEY_HELP: list[KeyboardShortcut] = [
    KeyboardShortcut(("ArrowLeft",), "Previous move", "prev-move"),
    KeyboardShortcut(("ArrowRight",), "Next move", "next-move"),
    KeyboardShortcut(("ArrowUp",), "Jump to start", "jump-start"),
    KeyboardShortcut(("ArrowDown",), "Jump to end", "jump-end"),
    KeyboardShortcut(("f",), "Flip board", "flip"),
    KeyboardShortcut(("a",), "Toggle analysis", "toggle-analysis"),
    KeyboardShortcut(("h",), "Show this help", "show-help"),
    KeyboardShortcut(("?",), "Show shortcuts", "show-shortcuts"),
    KeyboardShortcut(("Ctrl", "k"), "Command palette", "command-palette"),
    KeyboardShortcut(("Ctrl", "n"), "New game", "new-game"),
    KeyboardShortcut(("Ctrl", "o"), "Open PGN", "open-pgn"),
    KeyboardShortcut(("Ctrl", "e"), "Export PGN", "export-pgn"),
    KeyboardShortcut(("Escape",), "Close dialog", "close-dialog"),
    KeyboardShortcut(("Tab",), "Focus next", "focus-next"),
    KeyboardShortcut(("Shift", "Tab"), "Focus previous", "focus-prev"),
    KeyboardShortcut(("Space",), "Play/pause", "toggle-play"),
    KeyboardShortcut(("Home",), "First move", "first-move"),
    KeyboardShortcut(("End",), "Last move", "last-move"),
]


class KeyboardHandler:
    """Translates raw key events into named actions."""

    def __init__(self) -> None:
        self._bindings: dict[str, str] = {
            "+".join(sc.keys): sc.action for sc in KEY_HELP
        }

    def resolve(self, key_combo: str) -> str | None:
        """Resolve a key combo like 'Ctrl+k' to an action name."""
        return self._bindings.get(key_combo)

    def all_shortcuts(self) -> list[KeyboardShortcut]:
        return list(KEY_HELP)

    def is_modifier_only(self, key: str) -> bool:
        return key in {"Control", "Shift", "Alt", "Meta"}

    def normalize_combo(self, parts: list[str]) -> str:
        """Normalize a list of key parts to a canonical combo string.

        Order: Ctrl, Shift, Alt, Meta, then key.
        """
        mod_order = {"Control": 0, "Ctrl": 0, "Shift": 1, "Alt": 2, "Meta": 3}
        mods: list[str] = []
        rest: list[str] = []
        for p in parts:
            if p in mod_order:
                mods.append(p)
            else:
                rest.append(p)
        # Sort mods in canonical order
        mods.sort(key=lambda m: mod_order.get(m, 99))
        # Dedupe rest while preserving order
        seen: set[str] = set()
        unique_rest: list[str] = []
        for r in rest:
            if r not in seen:
                unique_rest.append(r)
                seen.add(r)
        return "+".join(mods + unique_rest)
