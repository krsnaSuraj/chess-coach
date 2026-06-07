<div align="center">

# ♟️ Chess Coach v3.0 - "The Humanizer"

**Anti-detection real-time chess sidekick · Stockfish 18 + optional Maia-1/Lc0**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)](https://www.riverbankcomputing.com/software/pyqt/)
[![FastAPI](https://img.shields.io/badge/Web-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Stockfish](https://img.shields.io/badge/Engine-Stockfish_18-FF6600?logo=chess&logoColor=white)](https://stockfishchess.org)
[![License](https://img.shields.io/badge/license-MIT-808080)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-899_passing-3fb950)](#-testing)

[Features](#-features) · [Quick Start](#-quick-start) · [Usage](#-usage) · [Configuration](#%EF%B8%8F-configuration) · [Architecture](#-architecture) · [Tech Stack](#-tech-stack)

</div>

---

## 🎯 Overview

Chess Coach is a professional real-time chess analysis sidekick that integrates **Stockfish 18** (and optionally **Maia-1** for human-policy priors) into a dual-interface application. v3.0 adds a **6-layer anti-detection architecture** so you can play chess.com without re-banning: multi-engine analysis, CAPS V2 classification, 5 style personalities, motif detection, opponent ELO modelling, and a chess.com-style risk score.

It evaluates positions exclusively during **your turn**, detects blunders and missed opportunities, suggests best moves with visual arrows, presents principal variation lines, and identifies openings via a **509-entry ECO database** - while staying completely silent when you manually enter opponent moves.

### v3.0 "The Humanizer" Highlights

* **Multi-engine**: Stockfish 18 + Maia-2 (neural policy) running in parallel, plus optional Berserk, Caissa, Crystal, Patricia, ShashChess
* **CAPS V2**: 11-tier move classification — 9 visible (Brilliant / Great / Best / Excellent / Good / Inaccuracy / Mistake / Miss / Blunder) + Book + Forced
* **5 personalities**: Aggressive, Positional, Tactical, Defensive, Balanced - each with its own move-bias dict and ECO preferences
* **Anti-cheat risk score**: 0-100 with 7 chess.com-style signals (top-1 match, CPL, time variance, style, tactical, blunder freq, phase variance)
* **Bayesian opponent modeler**: estimates opponent ELO and style from observed moves
* **Motif detector**: pin, fork, skewer, discovered attack, deflection, decoy, back-rank, zwischenzug
* **Lichess integration**: Explorer (Masters/Lichess/Player), Puzzles, OAuth PKCE, Study Sync, TV, Simuls, FIDE, Cloud Eval
* **WebSocket live analysis**: FastAPI WS server streams eval/PV to web UI in real time
* **4 tablebases**: Syzygy 7p, Lomonosov 7p, Lichess 8-piece (Op1), Gaviota
* **8 variants**: Standard, Chess960, Atomic, Antichess, Horde, KOTH, Three-Check, Crazyhouse
* **5 languages**: EN, HI, ES, FR, DE
* **a11y**: 18 keyboard shortcuts, ARIA live region, WCAG 2.2 AA
* **Graceful degradation**: works with Stockfish-only if Lc0/Maia are missing

**Perfect for:** Online chess (chess.com, lichess) where you play one side and want expert-level guidance without distraction.

> 📖 **Deep dive into design:** See **[ARCHITECTURE.md](ARCHITECTURE.md)** for module responsibilities, concurrency model, data flow, and testing strategy.

| Interface | Use Case |
|-----------|----------|
| **Desktop GUI** (PyQt6) | Full-featured analysis with premium UI, glass sidebar, animated eval bar, piece slide animation, coach dashboard, move history |
| **Web Interface** (FastAPI) | Lightweight browser access - play on PC, analyze on phone (same LAN) with 24 REST endpoints + WebSocket |

---

## ✨ Features

<table>
  <tr>
    <td>
      <h4>🧑‍🤝‍🧑 Single-Side Sidekick</h4>
      Select your side (White/Black). Coach analyzes only your moves. You manually enter opponent moves - coach stays silent during opponent's turn.
    </td>
    <td>
      <h4>🎯 ECO Opening Detection</h4>
      <strong>500 entries</strong> across A00-E99. Detects 50+ named openings (Ruy Lopez, Sicilian Najdorf, French, Grünfeld, Benoni, Catalan, etc.) with longest-prefix matching.
    </td>
  </tr>
  <tr>
    <td>
      <h4>⚡ Real-time Evaluation</h4>
      Continuous Stockfish 18 analysis updates eval, depth, and principal variation as you play. Eval bar with smooth 200ms animation.
    </td>
    <td>
      <h4>🚨 Blunder & Miss Detection</h4>
      Flags moves losing ≥1.0 pawns (blunders) <em>and</em> missed opportunities where opponent blundered but you failed to capitalize.
    </td>
  </tr>
  <tr>
    <td>
      <h4>🎯 Best Move Arrow</h4>
      Configurable arrow overlay (color + opacity) showing the top Stockfish line for the current position.
    </td>
    <td>
      <h4>📊 Coach Dashboard</h4>
      Premium glass-effect sidebar: eval bar (green→white→gray gradient), centipawn score, advantage label, engine depth, PV line, opening name, and natural-language coach feedback.
    </td>
  </tr>
  <tr>
    <td>
      <h4>🔄 Undo / Redo</h4>
      Full move-history navigation with Ctrl+Z / Ctrl+Y. Works even after checkmate - undo to continue.
    </td>
    <td>
      <h4>♟️ Underpromotion</h4>
      When a pawn reaches the 8th rank, a dialog lets you choose Queen, Rook, Bishop, or Knight - no auto-promotion.
    </td>
  </tr>
  <tr>
    <td>
      <h4>🔊 Move Sounds</h4>
      Subtle WAV click on each move via QSoundEffect. Auto-generated at first run - zero external assets needed.
    </td>
    <td>
      <h4>🌐 LAN Multi-device</h4>
      Web server auto-detects your LAN IP - analyze on your phone while Stockfish runs on your PC.
    </td>
  </tr>
  <tr>
    <td>
      <h4>⚙️ Configurable Engine</h4>
       Tweak Stockfish threads, hash size, analysis time via <code>config.yaml</code>. Thread-safe initialization with double-checked locking.
    </td>
    <td>
      <h4>🖌️ Premium UI</h4>
      Dark charcoal gradient background, frosted-glass sidebar, 150ms ease-out piece slide animation, blue glow button hover, smooth eval bar transitions.
    </td>
  </tr>
  <tr>
    <td>
      <h4>📋 PGN Import/Export</h4>
      Export games to PGN for analysis in any chess GUI. Import PGN files to replay annotated games.
    </td>
    <td>
      <h4>🔍 Analysis Board Mode</h4>
      Paste any FEN position for deep Stockfish analysis - ideal for post-game review or studying specific positions.
    </td>
  </tr>
</table>

---

## 📸 Screenshots

<p align="center">
  <img src="screenshots/Side-by-side.png" width="420" alt="Desktop GUI - Coach Dashboard with glass sidebar, eval bar, piece animation"/>
  <img src="screenshots/Server.png" width="420" alt="Web Interface - browser-based chess analysis"/>
</p>

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Stockfish 18** - download from [stockfishchess.org](https://stockfishchess.org/download/)

### Setup (All Platforms)

1. Clone the repo: `git clone https://github.com/krsnaSuraj/chess-coach.git && cd chess-coach`
2. Install dependencies: `pip install -r requirements.txt`
3. Download Stockfish 18 and place `stockfish.exe` in the project root
4. Done! Run the app below

For detailed platform-specific instructions, see **[INSTALLATION.md](INSTALLATION.md)**

### Launch

```bash
# Desktop GUI
python -m chess_coach

# Web server (http://localhost:8000)
python -m chess_coach web
python -m chess_coach web 8080    # custom port
```

---

## 🖥️ Usage

### Desktop GUI Workflow

1. Run `python -m chess_coach`
2. Select your color - **White** or **Black** (your side in the online game)
3. Play your move → coach analyzes and displays best move + opening + feedback
4. Opponent moves online → **drag their pieces on the app to record the move**
5. Coach shows "Waiting - *Color*'s turn" during opponent's turn (no analysis)
6. Repeat until game ends
7. Use **Undo** / **Redo** buttons or `Ctrl+Z` / `Ctrl+Y` to navigate history
8. **New Game** restarts with a fresh color choice

**Key Insight:** You can drag *any* piece at *any* time (unrestricted), so entering opponent moves is seamless.

The sidebar shows:

| Panel | Content | Shows When |
|-------|---------|-----------|
| **Turn Indicator** | Current side to move, check/checkmate/stalemate status | Always |
| **Opening** | ECO code + opening name (e.g., `[C42] Petrov Defense`) | Always |
| **Evaluation** | Centipawn score, colored eval bar, advantage label | Your turn only |
| **Best Line** | Top engine move and 4-ply principal variation | Your turn only |
| **Coach Feedback** | Position assessment + blunder/miss alerts | Your turn only |
| **Move History** | Annotated move list with SAN + check notation | Always |

### Web Interface Workflow

Same chess logic, served over HTTP:

1. Run `python -m chess_coach web`
2. Open **http://localhost:8000** in your browser (or the LAN URL for other devices)
3. Select your color → play as above
4. Promotion dialog appears when a pawn reaches the 8th rank

---

## 💡 The Sidekick Workflow

**Typical online chess session with Chess Coach:**

```
You (Playing Online)                                     Chess Coach App
─────────────────────────────────────────────────────────────────────────
Play move (e.g., 1.e4)                                   → [Coach analyzes]
                                                          → "Best: e4, Position equal"
                                                          → "[C42] Petrov Defense"
                                                          
Opponent plays (e.g., ...c5)                             [You drag c7→c5]
                                                          [Coach says "Waiting - Black's turn"]
                                                          (No analysis during opponent's turn)
                                                          
Play move (e.g., 2.Nf3)                                  → [Coach analyzes]
                                                          → "Best: Nf3, You're better"
                                                          
Opponent plays (e.g., ...d6)                             [You drag d7→d6]
                                                          [Coach stays silent]
                                                          
[… game continues …]
```

---

## ⚙️ Configuration

Edit `config.yaml`:

```yaml
engine:
  path: "stockfish.exe"        # Stockfish binary path
  threads: 2                    # CPU threads
  hash: 64                      # Hash table (MB)
  movetime: 2000                # Desktop analysis (ms)
  web_movetime: 0.15            # Web analysis (seconds)

display:
  dark_square: "#B58863"
  light_square: "#F0D9B5"
  arrow_color: "#00FF00"
  arrow_opacity: 0.6
```

**Note:** `arrow_opacity` must be a number (0.0-1.0). Boolean values are rejected.

---

## 🏗️ Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full system design (module responsibilities, data flow, concurrency model, ECO detection, testing strategy).

**High-level overview:**

```mermaid
graph TB
    MAIN["python -m chess_coach [web]"]
    
    subgraph Desktop["Desktop GUI (PyQt6)"]
        MW["MainWindow"]
        CB["ChessBoard<br/>Drag-drop · Animation · Arrows"]
        CD["CoachDashboard<br/>Glass Sidebar · Eval Bar · Feedback"]
        SP["SoundManager<br/>Move Sounds"]
        MW --> CB & CD & SP
    end
    
    subgraph Web["Web Server (FastAPI)"]
        SV["FastAPI Server<br/>REST API"]
        STATIC["static/ frontend<br/>chessboard.js"]
        SV --> STATIC
    end
    
    subgraph Core["Shared Core"]
        GC["GameController<br/>Board · Phases · Undo/Redo · Cache"]
        EH["EngineHandler<br/>Stockfish · QThread · UCI"]
        ECO["ECO Handler<br/>500 Openings"]
        GC --> EH
        MW --> GC & ECO
        SV --> GC
    end
    
    MAIN --> Desktop & Web
    EH --> SF["Stockfish 18<br/>(UCI Process)"]
```

---

## 📁 Project Structure

```
chess-coach/
│
├── src/chess_coach/              # Python package (127 files)
│   ├── __init__.py               # Public API re-exports
│   ├── __main__.py               # CLI entry: python -m chess_coach [web]
│   ├── config.py                 # YAML loader, port probe, IP lookup
│   ├── game_controller.py        # Shared game state, undo/redo, phases, cache
│   ├── engine_handler.py         # Stockfish 18 UCI wrapper (QObject + QThread)
│   ├── chess_board.py            # Board widget: drag-drop, highlights, arrows
│   ├── coach_dashboard.py        # Glass sidebar: animated eval bar, feedback
│   ├── promotion_dialog.py       # Underpromotion choice dialog (Q/R/B/K)
│   ├── main_window.py            # Wires board + dashboard + engine + menus
│   ├── server.py                 # FastAPI web server, 24 REST endpoints + WebSocket
│   ├── eco_handler.py            # ECO opening detection (longest-prefix)
│   ├── eco_data.py               # 509-entry ECO database (A00-E99)
│   ├── sound_manager.py          # WAV generation + QSoundEffect
│   ├── pgn_handler.py            # PGN export/import
│   ├── elo_calibrator.py         # Bayesian ELO estimator
│   ├── personality.py            # 5 personality profiles
│   ├── maia_engine.py            # Lc0 + Maia wrapper
│   ├── caps.py                   # V2 Expected Points classifier
│   ├── motif_detector.py         # 8 tactical pattern detectors
│   ├── opponent_modeler.py       # Bayesian ELO + style classifier
│   ├── anti_cheat_risk.py        # 7-signal risk scorer
│   ├── humanizer.py              # Move selection + think time sim
│   ├── multi_engine_handler.py   # SF + Maia parallel orchestration
│   │
│   ├── engines/                  # 7 SOTA engines
│   │   ├── base.py               # Engine interface + EngineInfo
│   │   ├── stockfish.py          # Stockfish 18
│   │   ├── lc0.py                # Leela Chess Zero
│   │   ├── maia2.py              # Maia-2 (human policy)
│   │   ├── berserk.py            # Berserk 3550 ELO
│   │   ├── caissa.py             # Caissa 3500 ELO
│   │   ├── crystal.py            # Crystal 3490 ELO
│   │   ├── patricia.py           # Patricia 3520 ELO
│   │   ├── shashchess.py         # ShashChess 3540 ELO
│   │   └── multi_engine_pool.py  # Parallel aggregation
│   │
│   ├── tablebase/                # 4 tablebases
│   │   ├── syzygy.py             # Syzygy 7-piece
│   │   ├── lomonosov.py          # Lomonosov 7-piece
│   │   ├── lichess_8p.py         # Lichess 8-piece (Op1)
│   │   └── gaviota.py            # Gaviota fallback
│   │
│   ├── classify/                 # SOTA move classification
│   │   ├── classify_v2.py        # 11 categories (9 visible + Book + Forced)
│   │   ├── epd.py                # EPD-based scoring
│   │   ├── phase_detector.py     # Opening/Middlegame/Endgame
│   │   ├── brilliant.py          # Brilliant detector
│   │   ├── great.py              # Great detector
│   │   ├── miss.py               # Miss detector
│   │   ├── motifs.py             # Tactical motifs
│   │   └── report_card.py        # Accuracy report
│   │
│   ├── lichess/                  # 15+ Lichess API endpoints
│   ├── ws/                       # WebSocket server/client
│   ├── openings/                 # ECO + polyglot
│   ├── coach/                    # Op prep, weakness, training plan
│   ├── tournament/               # Arena, Swiss, Bracket
│   ├── variants/                 # 8 variants registry
│   ├── eval/                     # Glicko-2, CPL, perf rating
│   ├── widgets/                  # 9 Qt widgets
│   ├── a11y/                     # Screen reader, keyboard nav
│   ├── i18n/                     # 5 languages
│   ├── db/                       # PGN index (SQLite)
│   └── theme_manager.py          # 10 themes
│
├── scripts/                      # install_deps, audit_cruft, audit_new
│
├── tests/                        # 899 tests across 34 test files
│   ├── test_v3_sota_fixes.py     # SOTA regression tests
│   ├── test_engines.py           # All 7 engines
│   ├── test_tablebase.py         # 4 tablebases
│   ├── test_classify_v2.py       # 11 categories (9 visible + Book + Forced)
│   ├── test_lichess.py           # 15+ endpoints
│   ├── test_ws.py                # WebSocket protocol
│   ├── test_coach.py             # Op prep, weakness, training plan
│   ├── test_variants.py          # 8 variants
│   ├── test_widgets_v2.py        # 9 widgets
│   ├── test_i18n.py              # 5 languages
│   ├── test_a11y.py              # a11y modules
│   ├── test_theme_manager.py     # 10 themes
│   └── test_db.py                # PGN index
│
├── static/                       # Web frontend (PWA)
│   ├── index.html                # 10 theme picker
│   ├── manifest.json             # v3.0.0 PWA manifest
│   ├── css/
│   │   ├── themes.css            # 10 themes CSS vars
│   │   └── chessboard.css        # Board grid + animation
│   ├── js/
│   │   ├── board.js              # ChessBoard class
│   │   ├── app.js                # REST + WebSocket wiring
│   │   ├── sound.js              # SoundEngine
│   │   └── icons/                # PWA icons
│   └── service-worker.js         # Offline cache
│
├── .github/workflows/ci.yml      # 3 OS × 3 Python matrix
├── screenshots/                  # App screenshots
├── config.yaml                   # Engine & humanizer settings
├── pyproject.toml                # Modern Python packaging (PEP 621)
├── requirements.txt              # Python dependencies
├── ARCHITECTURE.md               # Single source of truth
├── INSTALLATION.md               # Detailed setup guide
├── README.md                     # This file
└── LICENSE                       # MIT License
```

---

## 🛠️ Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Language** | Python 3.10+ | Core logic and glue |
| **Desktop UI** | PyQt6 | Native chess board, drag-drop, glass sidebar, piece animation |
| **Web Framework** | FastAPI + Uvicorn | REST API, static serving, CORS |
| **Engine Protocol** | python-chess (`chess.engine`) | UCI communication with Stockfish |
| **Engine** | Stockfish 18 | Position evaluation, best move, PV extraction |
| **Web Frontend** | chessboard.js + chess.js | Browser-based board interaction |
| **Concurrency** | `threading` (RLock) + `QThread` | Non-blocking engine analysis, thread-safe state |
| **Sound** | PyQt6.QtMultimedia (QSoundEffect) | Move click sound (auto-generated WAV) |
| **AI/Detection** | ECO database (509 entries) | Opening name recognition via longest-prefix match |
| **Configuration** | PyYAML | `config.yaml` parsing with type validation |
| **Testing** | pytest | 899 tests across 34 test files (36 .py files incl. conftest + __init__) |

### SOTA Engines (v3.0+)

| Layer | Technology | Role |
|-------|-----------|------|
| **Multi-Engine Pool** | Stockfish 18 + Lc0 v0.32.2 + Maia-2 (optional) | Parallel engine aggregation with weight-based blending and auto-disable on failure |
| **Syzygy Tablebase** | python-chess + Lichess API fallback | 7-piece endgame perfect play lookup (offline + online) |
| **CAPS v2** | Engine-corrected SOTA classifier | 11 move categories (Brilliant, Great, Best, Excellent, Good, Inaccuracy, Mistake, Miss, Blunder, Book, Forced) with phase-aware grading |
| **WebSocket Live** | FastAPI WebSocket + asyncio | Real-time eval stream to web UI with auto-reconnect and broadcast |
| **Lichess API** | Opening Explorer + Puzzles + OAuth PKCE + Study Sync | 19 puzzle themes, 3 Explorer sources (Masters / Lichess / Player), PKCE-secured OAuth, NDJSON game streaming |
| **Variants** | python-chess + custom engines | Standard, Chess960, Atomic, Antichess, Horde, KOTH, Three-Check, Crazyhouse |
| **i18n** | stdlib only | 5 languages (EN, HI, ES, FR, DE) with fallback chain |
| **a11y** | stdlib only | 18 keyboard shortcuts, ARIA live region announcer, AAA high-contrast theme |

---

## 🧪 Testing

```bash
pytest                  # Run all 899 tests
pytest -v               # Verbose output
pytest --cov=chess_coach # Coverage report
```

**Test categories:**
- **Config**: YAML loading, display validation, type safety, opacity rejection
- **Game Controller**: Board state, human moves, undo/redo, phase transitions, SAN generation
- **ECO**: Database integrity (no duplicates, valid codes), opening detection for 7+ named lines
- **PGN Handler**: Export/import roundtrip, check symbols, game results, replay
- **Engines**: SF18, Berserk, Caissa, Crystal, Patricia, ShashChess, Maia-2, Multi-Engine Pool
- **Tablebase**: Syzygy 7p, Lomonosov 7p, Lichess 8p, Gaviota
- **Classify V2**: 11 SOTA move categories with phase-aware grading
- **Motif detector**: 8 tactical patterns (pin, fork, skewer, etc.)
- **Lichess**: Explorer, Puzzles, OAuth PKCE, Study Sync, TV, Simuls, FIDE, Cloud Eval
- **WebSocket**: protocol, server broadcast, client auto-reconnect
- **Coach**: oprep, weakness, training plan
- **Variants**: 8 variants, openings, polyglot, ECO

---

## 🤝 Contributing

1. Fork → `git checkout -b feat/your-idea`
2. Code → `pytest` must pass
3. Commit → `git commit -m "feat: add your feature"`
4. Push → `git push origin feat/your-idea`
5. Pull Request

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE).

---

<p align="center">
  <a href="https://github.com/krsnaSuraj/chess-coach">
    <img src="https://img.shields.io/badge/-View_on_GitHub-181717?logo=github&logoColor=white" alt="GitHub">
  </a>
  <br>
  <sub>Built with ♟️ by <a href="https://github.com/krsnaSuraj">Krsna Suraj</a></sub>
</p>
