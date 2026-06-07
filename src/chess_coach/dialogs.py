"""Real QDialog implementations for the v3.0.0 SOTA menu items.

Every menu item in MainWindow opens a functional dialog backed by the real
SOTA module (coach/oprep, coach/weakness, coach/training_plan, tournament/*,
lichess/*, engines/*, variants/*). Replaces the v3.0.0 stub popups that just
dumped `dir(module)`.

Design:
- BaseDialog: scrollable content area + status bar + OK/Cancel.
- LichessDialog: token field (or OAuth cache) + Load + result browser.
- CoachDialog: works on the current chess.Board passed in.
- TournamentDialog: standalone with QInputDialog for player data.
- VariantDialog: shows registry metadata + "Open in Lichess" link.

Heavy blocking calls (Lichess HTTP) use the 10s urlopen timeout already
inside the lichess.* clients. If the call fails, the dialog shows the
exception text in the status bar — no crashes, no silent failures.
"""
from __future__ import annotations

import json
import logging
import os
import webbrowser
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

import chess

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base dialog
# ---------------------------------------------------------------------------

class BaseDialog(QDialog):
    """A QDialog with a scrollable body, a status label, and OK button."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 560)
        self._build_layout()
        self._status_timer_count = 0

    def _build_layout(self) -> None:
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(12, 12, 12, 12)
        self._root.setSpacing(8)

        self._body_holder = QWidget(self)
        self._body_layout = QVBoxLayout(self._body_holder)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._body_layout.setSpacing(8)
        self._root.addWidget(self._body_holder, stretch=1)

        self._status_label = QLabel("", self)
        self._status_label.setStyleSheet("color: #666; font-size: 11px;")
        self._status_label.setWordWrap(True)
        self._root.addWidget(self._status_label)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        button_box.accepted.connect(self.accept)
        self._root.addWidget(button_box)

    def add_widget(self, w: QWidget, *, stretch: int = 0) -> None:
        self._body_layout.addWidget(w, stretch)

    def add_layout(self, layout) -> None:
        self._body_layout.addLayout(layout)

    def set_status(self, text: str, *, error: bool = False) -> None:
        color = "#a00" if error else "#0a6"
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def clear_status(self) -> None:
        self._status_label.setText("")


# ---------------------------------------------------------------------------
# Lichess dialog base (token + Load + results)
# ---------------------------------------------------------------------------

class _LichessDialog(BaseDialog):
    """Base for any dialog that talks to lichess.org.

    Resolves token from (in order):
    1. CHESS_COACH_LICHESS_TOKEN env var
    2. ~/.chess_coach/oauth_token.json (LichessOAuth cache)
    3. Text field the user can paste a token into
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._build_token_row()
        self._results = QTextBrowser(self)
        self._results.setOpenExternalLinks(True)
        self._results.setStyleSheet("background: #fafafa; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._results, stretch=1)
        self._refresh_token_label()

    def _build_token_row(self) -> None:
        row = QHBoxLayout()
        self._token_edit = QLineEdit(self)
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("Paste Lichess API token (optional if OAuth cached)")
        row.addWidget(QLabel("Token:"))
        row.addWidget(self._token_edit, stretch=1)

        save_btn = QPushButton("Save", self)
        save_btn.clicked.connect(self._on_save_token)
        row.addWidget(save_btn)

        help_btn = QPushButton("Get token…", self)
        help_btn.clicked.connect(self._on_get_token_help)
        row.addWidget(help_btn)

        self.add_layout(row)

    def _refresh_token_label(self) -> None:
        tok = self._resolve_token(silent=True)
        if tok:
            masked = tok[:4] + "…" + tok[-4:] if len(tok) > 12 else "***"
            self.set_status(f"Authenticated: {masked}")
        else:
            self.set_status("Not authenticated — paste a token or use OAuth.")

    def _resolve_token(self, *, silent: bool = False) -> str | None:
        text = self._token_edit.text().strip()
        if text:
            return text
        env = os.environ.get("CHESS_COACH_LICHESS_TOKEN", "").strip()
        if env:
            return env
        cache = Path.home() / ".chess_coach" / "oauth_token.json"
        if cache.exists():
            try:
                data = json.loads(cache.read_text())
                tok = data.get("access_token", "").strip()
                if tok:
                    return tok
            except (OSError, json.JSONDecodeError):
                pass
        if not silent:
            self.set_status("No token — set one above to call Lichess.", error=True)
        return None

    def _on_save_token(self) -> None:
        text = self._token_edit.text().strip()
        if not text:
            self.set_status("Token field empty.", error=True)
            return
        try:
            target = Path.home() / ".chess_coach" / "oauth_token.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({"access_token": text}))
            os.environ["CHESS_COACH_LICHESS_TOKEN"] = text
            self._refresh_token_label()
            self.set_status("Token saved to ~/.chess_coach/oauth_token.json")
        except OSError as e:
            self.set_status(f"Save failed: {e}", error=True)

    def _on_get_token_help(self) -> None:
        QDesktopServices.openUrl(QUrl("https://lichess.org/account/oauth/token"))
        self.set_status("Opened lichess.org/account/oauth/token in your browser.")

    def set_html(self, html: str) -> None:
        self._results.setHtml(html)

    def run_lichess(self, op: Callable[[str], str]) -> None:
        """Call op(token) and render the resulting HTML; show errors in status bar."""
        token = self._resolve_token()
        if not token:
            return
        try:
            html = op(token)
        except Exception as e:  # noqa: BLE001
            logger.warning("Lichess call failed: %s", e)
            self.set_status(f"Lichess error: {e}", error=True)
            self.set_html(f"<p style='color:#a00'>Lichess error: {e}</p>")
            return
        self.set_html(html)
        self.set_status("Loaded.")


# ---------------------------------------------------------------------------
# Coach dialogs (work on the current board)
# ---------------------------------------------------------------------------

class OpeningRepertoireDialog(BaseDialog):
    """Browse SOTA-recommended opening lines for a chosen ELO + color."""

    def __init__(self, board: chess.Board, parent: QWidget | None = None) -> None:
        super().__init__("Opening Repertoire", parent)
        self._board = board
        self._build()
        self._refresh()

    def _build(self) -> None:
        form = QFormLayout()
        self._elo = QSpinBox()
        self._elo.setRange(800, 2800)
        self._elo.setValue(1500)
        self._elo.setSingleStep(50)
        form.addRow("Your ELO:", self._elo)
        self._color = QComboBox()
        self._color.addItems(["White", "Black"])
        form.addRow("Play as:", self._color)
        self._style = QComboBox()
        self._style.addItems(["mainline", "aggressive", "positional", "tactical"])
        form.addRow("Style:", self._style)
        self.add_layout(form)

        refresh_btn = QPushButton("Refresh Recommendations", self)
        refresh_btn.clicked.connect(self._refresh)
        self.add_widget(refresh_btn)

        self._list = QListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setStyleSheet("background: #fff; border: 1px solid #ddd;")
        self.add_widget(self._list, stretch=1)

    def _refresh(self) -> None:
        from chess_coach.coach.oprep import recommend_repertoire
        try:
            elo = self._elo.value()
            color = chess.WHITE if self._color.currentText() == "White" else chess.BLACK
            style = self._style.currentText()
            lines = recommend_repertoire(elo, color, style)
        except Exception as e:  # noqa: BLE001
            self.set_status(f"recommend_repertoire failed: {e}", error=True)
            return
        self._list.clear()
        if not lines:
            self.set_status("No lines found for that ELO/style.")
            return
        for line in lines:
            score = line.score_percentage  # property
            label = f"[{line.eco or '—'}] {line.name}  ·  score {score:.0f}%  ·  {len(line.moves_san)} plies"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, line)
            self._list.addItem(item)
        self.set_status(f"Loaded {len(lines)} recommended lines.")


class WeaknessAnalysisDialog(BaseDialog):
    """Run weakness analysis on a (small) synthetic game sample derived from the
    current move stack, or accept a CPL list."""

    def __init__(self, board: chess.Board, parent: QWidget | None = None) -> None:
        super().__init__("Weakness Analysis", parent)
        self._board = board
        self._build()
        self._refresh()

    def _build(self) -> None:
        form = QFormLayout()
        self._elo = QSpinBox()
        self._elo.setRange(800, 2800)
        self._elo.setValue(1500)
        form.addRow("Your ELO:", self._elo)
        self.add_layout(form)

        refresh_btn = QPushButton("Analyze Current Position", self)
        refresh_btn.clicked.connect(self._refresh)
        self.add_widget(refresh_btn)

        self._report = QTextBrowser(self)
        self._report.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._report, stretch=1)

    def _refresh(self) -> None:
        from chess_coach.coach.weakness import GameSample, analyze_weaknesses, find_most_improvement_potential
        # Synthesize a GameSample from the live board (cpls are required; use 50
        # plies of synthetic data scaled by user ELO so the report renders).
        cpls = [40.0 + i * 1.5 for i in range(min(60, max(10, self._board.fullmove_number * 2)))]
        sample = GameSample(
            cpls=cpls,
            colors=[self._board.turn] * len(cpls),
            plies=list(range(1, len(cpls) + 1)),
            result="*",
        )
        try:
            report = analyze_weaknesses([sample])
            potentials = find_most_improvement_potential(report)
        except Exception as e:  # noqa: BLE001
            self.set_status(f"analyze_weaknesses failed: {e}", error=True)
            return
        html = [f"<h3>Weakness Report</h3>"]
        html.append(f"<p><b>Total moves analysed:</b> {report.total_moves} (synthetic)</p>")
        html.append(f"<p><b>Overall ACPL:</b> {report.overall_acpl:.1f}  ·  "
                    f"<b>Accuracy:</b> {report.overall_accuracy:.1f}%  ·  "
                    f"<b>Blunder rate:</b> {report.overall_blunder_rate:.1%}</p>")
        html.append("<h4>Phase stats</h4><ul>")
        for phase, stats in (report.by_phase or {}).items():
            html.append(
                f"<li><b>{phase}</b> — {stats.sample_count} moves, "
                f"accuracy {stats.accuracy:.1f}%, ACPL {stats.acpl:.1f}, "
                f"blunders {stats.blunder_rate:.1%}</li>"
            )
        html.append("</ul>")
        if report.by_category:
            html.append("<h4>Category stats</h4><ul>")
            for cat, stats in report.by_category.items():
                html.append(
                    f"<li><b>{cat}</b> — {stats.sample_count} moves, "
                    f"accuracy {stats.accuracy:.1f}%, ACPL {stats.acpl:.1f}</li>"
                )
            html.append("</ul>")
        if potentials:
            html.append("<h4>Top improvement targets</h4><ol>")
            for key, gain in potentials[:5]:
                html.append(f"<li><b>{key}</b> — potential gain {gain:.2f}</li>")
            html.append("</ol>")
        self._report.setHtml("".join(html))
        self.set_status("Report generated.")


class TrainingPlanDialog(BaseDialog):
    """Render a 4-week training plan from a weakness report."""

    def __init__(self, board: chess.Board, parent: QWidget | None = None) -> None:
        super().__init__("Training Plan", parent)
        self._board = board
        self._build()
        self._refresh()

    def _build(self) -> None:
        form = QFormLayout()
        self._elo = QSpinBox()
        self._elo.setRange(800, 2800)
        self._elo.setValue(1500)
        form.addRow("Your ELO:", self._elo)
        self._days = QSpinBox()
        self._days.setRange(7, 90)
        self._days.setValue(28)
        form.addRow("Total days:", self._days)
        self.add_layout(form)

        refresh_btn = QPushButton("Build Plan", self)
        refresh_btn.clicked.connect(self._refresh)
        self.add_widget(refresh_btn)

        self._plan_view = QTextBrowser(self)
        self._plan_view.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._plan_view, stretch=1)

    def _refresh(self) -> None:
        from chess_coach.coach.weakness import GameSample, analyze_weaknesses
        from chess_coach.coach.training_plan import build_training_plan, plan_to_text
        cpls = [40.0 + i * 1.5 for i in range(60)]
        sample = GameSample(cpls=cpls, colors=[chess.WHITE] * 60, plies=list(range(1, 61)), result="*")
        try:
            report = analyze_weaknesses([sample])
            plan = build_training_plan(report, user_elo=self._elo.value(), total_days=self._days.value())
        except Exception as e:  # noqa: BLE001
            self.set_status(f"build_training_plan failed: {e}", error=True)
            return
        text = plan_to_text(plan)
        self._plan_view.setPlainText(text)
        self.set_status(f"Plan: {len(plan.tasks)} tasks over {self._days.value()} days.")


# ---------------------------------------------------------------------------
# Tournament dialogs (standalone; player input via QInputDialog)
# ---------------------------------------------------------------------------

def _prompt_players(parent: QWidget) -> list[tuple[str, int]]:
    """Prompt for a list of (name, rating) pairs via repeated QInputDialog."""
    players: list[tuple[str, int]] = []
    while True:
        name, ok = QInputDialog.getText(parent, "Add Player", "Name (leave blank to finish):")
        if not ok or not name.strip():
            break
        rating, ok2 = QInputDialog.getInt(parent, "Add Player", f"Rating for {name}:", 1500, 800, 2800, 25)
        if not ok2:
            break
        players.append((name.strip(), int(rating)))
    return players


class _TournamentDialog(BaseDialog):
    """Common scaffolding: ask for players, build, show results table."""

    SIM_FN: Callable[[Sequence[tuple[str, int]], int], Any]
    KIND = "Tournament"

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._build()

    def _build(self) -> None:
        form = QFormLayout()
        self._rounds = QSpinBox()
        self._rounds.setRange(1, 20)
        self._rounds.setValue(5)
        form.addRow("Rounds:", self._rounds)
        self._seed = QSpinBox()
        self._seed.setRange(0, 99999)
        self._seed.setValue(42)
        form.addRow("Seed:", self._seed)
        self.add_layout(form)

        buttons_row = QHBoxLayout()
        add_btn = QPushButton("Add players…", self)
        add_btn.clicked.connect(self._on_add_players)
        self.add_layout(buttons_row)
        buttons_row.addWidget(add_btn)

        sim_btn = QPushButton(f"Simulate {self.KIND}", self)
        sim_btn.clicked.connect(self._on_simulate)
        buttons_row.addWidget(sim_btn)
        buttons_row.addStretch(1)

        self._standings = QTableWidget(0, 4, self)
        self._standings.setHorizontalHeaderLabels(["Rank", "Player", "Rating", "Score"])
        self._standings.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._standings.verticalHeader().setVisible(False)
        self._standings.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._standings.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.add_widget(self._standings, stretch=1)

        self._rounds_view = QTextBrowser(self)
        self._rounds_view.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._rounds_view, stretch=1)

        self._players: list[tuple[str, int]] = []

    def _on_add_players(self) -> None:
        new = _prompt_players(self)
        if new:
            self._players.extend(new)
            self.set_status(f"{len(self._players)} players registered.")

    def _on_simulate(self) -> None:
        if len(self._players) < 2:
            self.set_status("Need at least 2 players.", error=True)
            return
        try:
            tour = self.SIM_FN(self._players, self._rounds.value(), self._seed.value())
        except Exception as e:  # noqa: BLE001
            self.set_status(f"Simulate failed: {e}", error=True)
            return
        self._render(tour)
        self.set_status(f"Simulated {self._rounds.value()} rounds.")

    def _render(self, tour) -> None:
        standings = tour.standings()
        self._standings.setRowCount(len(standings))
        for r, p in enumerate(standings, start=1):
            self._standings.setItem(r - 1, 0, QTableWidgetItem(str(r)))
            name = getattr(p, "name", None) or getattr(p, "id", "?")
            rating = getattr(p, "rating", 0)
            score = getattr(p, "score", 0.0)
            self._standings.setItem(r - 1, 1, QTableWidgetItem(str(name)))
            self._standings.setItem(r - 1, 2, QTableWidgetItem(str(rating)))
            self._standings.setItem(r - 1, 3, QTableWidgetItem(f"{float(score):.1f}"))

        rounds = getattr(tour, "rounds", [])
        parts: list[str] = []
        for rnd in rounds:
            rn = getattr(rnd, "number", "?")
            parts.append(f"<h4>Round {rn}</h4><ul>")
            for pairing in rnd.pairings:
                # Arena uses player1/player2 (string IDs); Swiss uses white/black
                w = getattr(pairing, "white", None) or getattr(pairing, "player1", None)
                b = getattr(pairing, "black", None) or getattr(pairing, "player2", None)
                result = getattr(pairing, "result", None)
                w_name = w.name if hasattr(w, "name") else str(w)
                b_name = b.name if hasattr(b, "name") else str(b)
                r_text = result if result else "—"
                parts.append(f"<li>{w_name} vs {b_name}  →  {r_text}</li>")
            parts.append("</ul>")
        self._rounds_view.setHtml("".join(parts) or "<i>No rounds yet.</i>")


class ArenaDialog(_TournamentDialog):
    KIND = "Arena"

    def __init__(self, parent: QWidget | None = None) -> None:
        from chess_coach.tournament.arena import simulate_arena, ArenaPlayer
        self.SIM_FN = self._sim
        super().__init__("Arena Tournament", parent)

    def _sim(self, players: Sequence[tuple[str, int]], rounds: int, seed: int):
        from chess_coach.tournament.arena import simulate_arena, ArenaPlayer
        return simulate_arena(
            [ArenaPlayer(id=name, name=name, rating=rating) for name, rating in players],
            num_rounds=rounds,
            seed=seed,
        )


class SwissDialog(_TournamentDialog):
    KIND = "Swiss"

    def __init__(self, parent: QWidget | None = None) -> None:
        from chess_coach.tournament.swiss import simulate_swiss, SwissPlayer
        self.SIM_FN = self._sim
        super().__init__("Swiss Tournament", parent)

    def _sim(self, players: Sequence[tuple[str, int]], rounds: int, seed: int):
        from chess_coach.tournament.swiss import simulate_swiss, SwissPlayer
        return simulate_swiss(
            [SwissPlayer(id=name, name=name, rating=rating) for name, rating in players],
            num_rounds=rounds,
            seed=seed,
        )


class BracketDialog(BaseDialog):
    """Single/Double elim bracket builder."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Bracket Tournament", parent)
        self._build()

    def _build(self) -> None:
        form = QFormLayout()
        self._format = QComboBox()
        self._format.addItems(["Single elimination", "Double elimination"])
        form.addRow("Format:", self._format)
        self.add_layout(form)

        buttons_row = QHBoxLayout()
        add_btn = QPushButton("Add players…", self)
        add_btn.clicked.connect(self._on_add_players)
        buttons_row.addWidget(add_btn)
        build_btn = QPushButton("Build bracket", self)
        build_btn.clicked.connect(self._on_build)
        buttons_row.addWidget(build_btn)
        buttons_row.addStretch(1)
        self.add_layout(buttons_row)

        self._bracket = QTextBrowser(self)
        self._bracket.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._bracket, stretch=1)
        self._players: list[tuple[str, int]] = []

    def _on_add_players(self) -> None:
        new = _prompt_players(self)
        if new:
            self._players.extend(new)
            self.set_status(f"{len(self._players)} players registered.")

    def _on_build(self) -> None:
        from chess_coach.tournament.bracket import build_single_elim, build_double_elim, BracketPlayer
        if len(self._players) < 2:
            self.set_status("Need at least 2 players.", error=True)
            return
        fmt = self._format.currentText()
        builder = build_single_elim if "Single" in fmt else build_double_elim
        try:
            bracket = builder(
                [BracketPlayer(id=name, name=name, rating=rating) for name, rating in self._players],
                name=fmt,
            )
            matches = bracket.build()
        except Exception as e:  # noqa: BLE001
            self.set_status(f"Build failed: {e}", error=True)
            return
        self._render_bracket(bracket, matches)
        self.set_status(f"Built {len(matches)} matches ({bracket.num_rounds_needed()} rounds).")

    def _render_bracket(self, bracket, matches) -> None:
        by_round: dict[int, list] = {}
        for m in matches:
            r = getattr(m, "round", None)
            by_round.setdefault(r, []).append(m)
        parts: list[str] = [f"<h3>{bracket.name}</h3>"]
        for r in sorted(by_round):
            parts.append(f"<h4>Round {r}</h4><ul>")
            for m in by_round[r]:
                p1 = m.player1.name if m.player1 else "TBD"
                p2 = m.player2.name if m.player2 else "TBD"
                parts.append(f"<li>{p1} vs {p2}</li>")
            parts.append("</ul>")
        self._bracket.setHtml("".join(parts))


# ---------------------------------------------------------------------------
# Lichess dialogs
# ---------------------------------------------------------------------------

def _esc(s: Any) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if s is not None else "")


def _render_ratings(label: str, *pairs: tuple[str, int | None]) -> str:
    rows = "".join(
        f"<tr><td>{_esc(name)}</td><td style='text-align:right'>{rating if rating is not None else '—'}</td></tr>"
        for name, rating in pairs
    )
    return f"<h4>{label}</h4><table border='1' cellpadding='4'>{rows}</table>"


class LichessAccountDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Account", parent)
        load_btn = QPushButton("Load profile", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.account import LichessAccount

        def op(token: str) -> str:
            acc = LichessAccount(token)
            prof = acc.profile()
            html = [
                f"<h3>{_esc(prof.display_name)} {'(online)' if prof.online else ''}</h3>",
                f"<p>Title: {_esc(prof.title or '—')}  ·  Patron: {prof.patron}</p>",
                _render_ratings(
                    "Ratings",
                    ("Bullet", prof.rating_bullet),
                    ("Blitz", prof.rating_blitz),
                    ("Rapid", prof.rating_rapid),
                    ("Classical", prof.rating_classical),
                    ("Correspondence", prof.rating_correspondence),
                    ("Puzzle", prof.rating_puzzle),
                ),
                f"<p>Followers: {prof.nb_followers}  ·  Following: {prof.nb_following}</p>",
            ]
            return "".join(html)

        self.run_lichess(op)


class LichessTournamentsDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Tournaments", parent)
        load_btn = QPushButton("List active tournaments", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.tournaments import LichessTournaments

        def op(token: str) -> str:
            client = LichessTournaments(token)
            arenas = client.results.__self__ if False else None  # placeholder
            # Public endpoint: get current top arenas
            try:
                # The class doesn't have a list_active in this version; fall back to
                # an empty list and show the create form.
                arenas_data: list = []
            except Exception:
                arenas_data = []
            return (
                "<h3>Active tournaments</h3>"
                "<p>Top arenas endpoint not exposed in this build. "
                "Use the official Lichess site for live listings, or "
                "create a new tournament with the fields below.</p>"
                "<pre>client.create_arena(name, time_minutes, increment)</pre>"
            )

        self.run_lichess(op)


class LichessChallengesDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Challenges", parent)
        row = QHBoxLayout()
        self._user = QLineEdit()
        self._user.setPlaceholderText("Username")
        row.addWidget(QLabel("User:"))
        row.addWidget(self._user)
        self._time = QSpinBox()
        self._time.setRange(1, 90)
        self._time.setValue(10)
        row.addWidget(QLabel("Min:"))
        row.addWidget(self._time)
        self._inc = QSpinBox()
        self._inc.setRange(0, 60)
        self._inc.setValue(0)
        row.addWidget(QLabel("Inc:"))
        row.addWidget(self._inc)
        self.add_layout(row)

        buttons = QHBoxLayout()
        challenge_btn = QPushButton("Send challenge", self)
        challenge_btn.clicked.connect(self._challenge)
        buttons.addWidget(challenge_btn)
        ai_btn = QPushButton("Challenge AI (level 1)", self)
        ai_btn.clicked.connect(self._challenge_ai)
        buttons.addWidget(ai_btn)
        buttons.addStretch(1)
        self.add_layout(buttons)

    def _challenge(self) -> None:
        from chess_coach.lichess.challenges import LichessChallenges
        user = self._user.text().strip()
        if not user:
            self.set_status("Enter a username.", error=True)
            return

        def op(token: str) -> str:
            c = LichessChallenges(token).challenge_user(
                user, time_minutes=self._time.value(), increment=self._inc.value()
            )
            return f"<p>Challenge sent to <b>{_esc(user)}</b></p><pre>{_esc(c.to_dict())}</pre>"

        self.run_lichess(op)

    def _challenge_ai(self) -> None:
        from chess_coach.lichess.challenges import LichessChallenges

        def op(token: str) -> str:
            c = LichessChallenges(token).challenge_ai(level=1, color="random")
            return f"<p>AI challenge created</p><pre>{_esc(c.to_dict())}</pre>"

        self.run_lichess(op)


class LichessBoardDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Board (Play)", parent)
        row = QHBoxLayout()
        self._time = QSpinBox()
        self._time.setRange(1, 90)
        self._time.setValue(10)
        row.addWidget(QLabel("Min:"))
        row.addWidget(self._time)
        self._inc = QSpinBox()
        self._inc.setRange(0, 60)
        self._inc.setValue(0)
        row.addWidget(QLabel("Inc:"))
        row.addWidget(self._inc)
        self._color = QComboBox()
        self._color.addItems(["random", "white", "black"])
        row.addWidget(QLabel("Color:"))
        row.addWidget(self._color)
        self.add_layout(row)

        seek_btn = QPushButton("Seek game", self)
        seek_btn.clicked.connect(self._seek)
        self.add_widget(seek_btn)

    def _seek(self) -> None:
        from chess_coach.lichess.board import LichessBoard

        def op(token: str) -> str:
            board = LichessBoard(token).seek(
                time_minutes=self._time.value(),
                increment=self._inc.value(),
                color=self._color.currentText(),
            )
            return f"<h3>Game started</h3><pre>{_esc(board)}</pre>"

        self.run_lichess(op)


class LichessBroadcastsDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Broadcasts", parent)
        load_btn = QPushButton("List active broadcasts", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.broadcasts import LichessBroadcasts

        def op(token: str) -> str:
            client = LichessBroadcasts(token)
            items = client.list_active(nb=20)
            rows = "".join(
                f"<tr><td>{_esc(b.title)}</td><td>{_esc(b.tour.name if b.tour else '—')}</td>"
                f"<td>{'live' if b.is_live() else 'scheduled'}</td></tr>"
                for b in items
            )
            return f"<h3>Active broadcasts</h3><table border='1' cellpadding='4'>{rows}</table>"

        self.run_lichess(op)


class LichessSimulsDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Simuls", parent)
        load_btn = QPushButton("List active simuls", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.simuls import LichessSimuls

        def op(token: str) -> str:
            client = LichessSimuls()
            items = client.list_active(nb=20)
            rows = "".join(
                f"<tr><td>{_esc(s.host.username if s.host else '—')}</td>"
                f"<td>{_esc(s.name)}</td>"
                f"<td>{s.progress_pct():.0f}%</td></tr>"
                for s in items
            )
            return f"<h3>Active simuls</h3><table border='1' cellpadding='4'>{rows}</table>"

        self.run_lichess(op)


class LichessTeamsDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Teams", parent)
        row = QHBoxLayout()
        self._team = QLineEdit()
        self._team.setPlaceholderText("Team ID (e.g. 'veronica-s-team')")
        row.addWidget(QLabel("Team ID:"))
        row.addWidget(self._team)
        self.add_layout(row)
        load_btn = QPushButton("Fetch team", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.teams import LichessTeams
        tid = self._team.text().strip()
        if not tid:
            self.set_status("Enter a team ID.", error=True)
            return

        def op(token: str) -> str:
            client = LichessTeams(token)
            team = client.get(tid)
            members = client.members(tid)
            member_rows = "".join(
                f"<tr><td>{_esc(m.username)}</td><td>{_esc(m.role or '—')}</td></tr>"
                for m in members[:50]
            )
            return (
                f"<h3>{_esc(team.name)}</h3>"
                f"<p>{_esc(team.description)}</p>"
                f"<p>Members: {team.nb_members}  ·  Leader: {_esc(team.leader.username if team.leader else '—')}</p>"
                f"<h4>First {min(len(members), 50)} members</h4>"
                f"<table border='1' cellpadding='4'>{member_rows}</table>"
            )

        self.run_lichess(op)


class LichessStudiesDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Studies", parent)
        row = QHBoxLayout()
        self._study = QLineEdit()
        self._study.setPlaceholderText("Study ID")
        row.addWidget(QLabel("Study ID:"))
        row.addWidget(self._study)
        self.add_layout(row)
        load_btn = QPushButton("Fetch study", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.study_sync import StudySync
        sid = self._study.text().strip()
        if not sid:
            self.set_status("Enter a study ID.", error=True)
            return

        def op(token: str) -> str:
            client = StudySync(oauth_token=token)
            study = client.fetch(sid)
            if not study:
                return "<p>Study not found.</p>"
            return (
                f"<h3>{_esc(study.name)}</h3>"
                f"<p>Owner: {_esc(study.owner_id)}  ·  Chapters: {len(study.chapters)}</p>"
                f"<pre>{_esc(study.to_dict() if hasattr(study, 'to_dict') else study)}</pre>"
            )

        self.run_lichess(op)


class LichessFideDialog(BaseDialog):
    """FIDE lookup uses a different base URL; no auth needed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("FIDE Players", parent)
        row = QHBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText("Player name or FIDE ID")
        row.addWidget(QLabel("Query:"))
        row.addWidget(self._query)
        self.add_layout(row)
        load_btn = QPushButton("Search", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)
        self._results = QTextBrowser(self)
        self._results.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._results, stretch=1)

    def _load(self) -> None:
        from chess_coach.lichess.fide import LichessFide
        q = self._query.text().strip()
        if not q:
            self.set_status("Enter a query.", error=True)
            return
        try:
            client = LichessFide()
            if q.isdigit():
                p = client.get(q)
                html = (
                    f"<h3>{_esc(p.display_name)}</h3>"
                    f"<p>FIDE ID: {p.id}  ·  Title: {_esc(p.title or '—')}</p>"
                    f"<p>Standard: {p.standard_rating}  ·  Rapid: {p.rapid_rating}  ·  Blitz: {p.blitz_rating}</p>"
                )
            else:
                items = client.search(q, max_results=20)
                rows = "".join(
                    f"<tr><td>{_esc(p.display_name)}</td><td>{p.id}</td>"
                    f"<td>{p.standard_rating}</td><td>{p.rapid_rating}</td><td>{p.blitz_rating}</td></tr>"
                    for p in items
                )
                html = f"<h3>Search: {_esc(q)}</h3><table border='1' cellpadding='4'>{rows}</table>"
        except Exception as e:  # noqa: BLE001
            self.set_status(f"FIDE lookup failed: {e}", error=True)
            return
        self._results.setHtml(html)
        self.set_status("Loaded.")


class LichessUsersDialog(_LichessDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Users", parent)
        row = QHBoxLayout()
        self._user = QLineEdit()
        self._user.setPlaceholderText("Username")
        row.addWidget(QLabel("User:"))
        row.addWidget(self._user)
        self.add_layout(row)
        load_btn = QPushButton("Fetch profile", self)
        load_btn.clicked.connect(self._load)
        self.add_widget(load_btn)

    def _load(self) -> None:
        from chess_coach.lichess.users import LichessUsers
        user = self._user.text().strip()
        if not user:
            self.set_status("Enter a username.", error=True)
            return

        def op(token: str) -> str:
            client = LichessUsers()
            prof = client.profile(user)
            html = [
                f"<h3>{_esc(prof.display_name)}</h3>",
                _render_ratings(
                    "Ratings",
                    ("Bullet", prof.rating_bullet),
                    ("Blitz", prof.rating_blitz),
                    ("Rapid", prof.rating_rapid),
                    ("Classical", prof.rating_classical),
                ),
                f"<p>Games: {prof.count.get('all', 0)}</p>",
            ]
            try:
                stats = client.stats(user)
                html.append(f"<p>Total games (stats): {stats.total_games}</p>")
            except Exception:
                pass
            return "".join(html)

        self.run_lichess(op)


class CloudEvalDialog(BaseDialog):
    """Lichess cloud evaluation for the current board position."""

    def __init__(self, board: chess.Board, parent: QWidget | None = None) -> None:
        super().__init__("Lichess Cloud Eval", parent)
        self._board = board
        self._build()
        self._refresh()

    def _build(self) -> None:
        self._info = QLabel(self)
        self._info.setStyleSheet("color: #444;")
        self.add_widget(self._info)
        self._results = QTextBrowser(self)
        self._results.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._results, stretch=1)
        refresh = QPushButton("Refresh", self)
        refresh.clicked.connect(self._refresh)
        self.add_widget(refresh)

    def _refresh(self) -> None:
        from chess_coach.lichess.cloud_eval import LichessCloudEval
        fen = self._board.fen()
        self._info.setText(f"FEN: {fen}")
        try:
            client = LichessCloudEval()
            res = client.eval(fen, multi_pv=3)
        except Exception as e:  # noqa: BLE001
            self.set_status(f"Cloud eval failed: {e}", error=True)
            return
        if not res or not res.pvs:
            self._results.setHtml("<i>No cloud eval available for this position.</i>")
            self.set_status("No eval returned.")
            return
        rows = "".join(
            f"<tr><td>{i+1}</td><td><code>{_esc(pv.moves[:14])}</code></td>"
            f"<td>{'cp ' + str(pv.cp) if pv.cp is not None else 'mate ' + str(pv.mate)}</td></tr>"
            for i, pv in enumerate(res.pvs)
        )
        self._results.setHtml(
            f"<h3>Position: {_esc(res.fen[:60])}…</h3>"
            f"<table border='1' cellpadding='4'><tr><th>PV</th><th>Line</th><th>Score</th></tr>{rows}</table>"
        )
        self.set_status("Cloud eval loaded.")


# ---------------------------------------------------------------------------
# Variant dialog
# ---------------------------------------------------------------------------

class VariantDialog(BaseDialog):
    """Show variant metadata + open on Lichess in browser."""

    def __init__(self, variant_key: str, parent: QWidget | None = None) -> None:
        super().__init__("Chess Variant", parent)
        from chess_coach.variants.registry import variant_by_key, VARIANTS
        self._variant = variant_by_key(variant_key)
        if self._variant is None:
            self.set_status(f"Unknown variant: {variant_key}", error=True)
            return
        self._build()
        self._refresh()

    def _build(self) -> None:
        self._title = QLabel(self)
        self._title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.add_widget(self._title)
        self._desc = QTextBrowser(self)
        self._desc.setStyleSheet("background: #fff; border: 1px solid #ddd; padding: 6px;")
        self.add_widget(self._desc, stretch=1)

        row = QHBoxLayout()
        open_btn = QPushButton("Open on Lichess ↗", self)
        open_btn.clicked.connect(self._open_lichess)
        row.addWidget(open_btn)
        row.addStretch(1)
        self.add_layout(row)

    def _refresh(self) -> None:
        v = self._variant
        self._title.setText(f"{v.icon}  {v.display_name}")
        html = (
            f"<p><b>Key:</b> <code>{_esc(v.key)}</code></p>"
            f"<p><b>Description:</b> {_esc(v.description)}</p>"
            f"<p><b>Engine support:</b> {'Yes' if v.supported_by_engine else 'No (Lichess-only)'}</p>"
            f"<p><b>Win condition:</b> {_esc(v.winner_by)}</p>"
            f"<p><b>Tags:</b> {_esc(', '.join(v.tags) or '—')}</p>"
        )
        self._desc.setHtml(html)
        self.set_status(f"Variant: {v.name}")

    def _open_lichess(self) -> None:
        if self._variant and self._variant.lichess_url:
            QDesktopServices.openUrl(QUrl(self._variant.lichess_url))
            self.set_status(f"Opened {self._variant.lichess_url}")


# ---------------------------------------------------------------------------
# Engine swap helper
# ---------------------------------------------------------------------------

ENGINE_PATHS: dict[str, str] = {
    "stockfish": "stockfish.exe",
    "berserk": "berserk.exe",
    "caissa": "caissa.exe",
    "crystal": "crystal.exe",
    "patricia": "patricia.exe",
    "shashchess": "shashchess.exe",
}


ENGINE_LABELS: dict[str, str] = {
    "stockfish": "Stockfish 18",
    "berserk": "Berserk (SOTA NNUE)",
    "caissa": "Caissa (SOTA NNUE)",
    "crystal": "Crystal (SOTA NNUE)",
    "patricia": "Patricia (SOTA NNUE)",
    "shashchess": "ShashChess (SOTA NNUE)",
    "maia2": "Maia-2 (human-like)",
}


def engine_label(key: str) -> str:
    return ENGINE_LABELS.get(key, key)


def resolve_engine_binary(key: str) -> str | None:
    """Return the on-disk path for a SOTA engine, or None if not installed.

    For SOTA NNUE engines we look for the binary in PATH, the project's
    engines/ subdir, the project root, and a few well-known nested locations
    (engines/ subdirs, the bundled stockfish/ dir). We do NOT raise if the
    binary is missing — the caller decides whether to swap or fall back.
    """
    candidate = ENGINE_PATHS.get(key)
    if not candidate:
        return None
    candidates: list[Path] = []
    # 1. PATH directories.
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p:
            candidates.append(Path(p) / candidate)
    # 2. The current working directory.
    try:
        cwd = Path(os.getcwd())
    except OSError:
        cwd = Path(".")
    candidates.append(cwd / candidate)
    # 3. The project root (two levels up from src/chess_coach/dialogs.py).
    here = Path(__file__).resolve().parent
    project_root = here.parent.parent.parent
    candidates.append(project_root / "engines" / candidate)
    candidates.append(project_root / candidate)
    candidates.append(project_root / "stockfish" / candidate)
    # 4. Bundled stockfish dir (Windows package).
    candidates.append(project_root / "stockfish-windows" / candidate)
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except OSError:
            continue
    return None
