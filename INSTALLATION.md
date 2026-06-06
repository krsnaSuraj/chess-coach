# Installation Guide — Chess Coach

## Prerequisites

- **Python 3.10+**
- **Stockfish 18** — download from [stockfishchess.org](https://stockfishchess.org/download/)

---

## Quick Setup

### 1. Clone & Install

```bash
git clone https://github.com/krsnaSuraj/chess-coach.git
cd chess-coach
pip install -e .
```

> Installs the `chess_coach` package in editable mode + `chess-coach` CLI entry point.

### 2. (Optional) Download Stockfish

Chess Coach v3.0+ has a **one-shot auto-installer** that fetches Stockfish 18, Lc0 v0.32.1 and Maia-1 weights on first run. Nothing to do.

If you prefer manual setup, the old way still works:

| OS | Method |
|----|--------|
| **Windows** | Download `stockfish.exe`, place in project root |
| **macOS** | `brew install stockfish` |
| **Linux** | `sudo apt-get install stockfish` or `dnf install stockfish` |

CLI helpers:

```bash
python -m chess_coach --check      # verify deps
python -m chess_coach --install    # force re-install
python scripts/install_deps.py --help   # full options
```

### 3. Verify

```bash
python -c "import chess_coach; print('OK:', len(chess_coach.__all__), 'public symbols')"
python -m chess_coach --check
```

---

## Running

```bash
# Desktop GUI
python -m chess_coach

# Web server (LAN-access)
python -m chess_coach web
python -m chess_coach web 8080   # custom port
```

---

## Testing

```bash
pip install "pytest>=7"
pytest
pytest --cov=chess_coach   # with coverage
```

---

## Configuration

Edit `config.yaml`:

```yaml
engine:
  path: "stockfish.exe"     # Path to Stockfish binary
  threads: 2                 # CPU threads
  hash: 64                   # Hash table size (MB)
  movetime: 2000             # Desktop analysis time (ms)
  web_movetime: 0.15         # Web analysis time (seconds)

display:
  dark_square: "#B58863"
  light_square: "#F0D9B5"
  arrow_color: "#00FF00"
  arrow_opacity: 0.6
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | `pip install -e .` again |
| Stockfish not found | Set `engine.path` in `config.yaml` to full path |
| Port 8000 in use | `python -m chess_coach web 8080` |
| GUI won't open (Linux) | Use web mode: `python -m chess_coach web` |
| High DPI blurry | Set `QT_AUTO_SCREEN_SCALE_FACTOR=1` |
| Slow analysis | Increase `threads` and `hash` in `config.yaml` |
