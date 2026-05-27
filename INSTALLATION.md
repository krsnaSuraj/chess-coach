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

### 2. Download Stockfish

| OS | Method |
|----|--------|
| **Windows** | Download `stockfish.exe`, place in project root |
| **macOS** | `brew install stockfish` |
| **Linux** | `sudo apt-get install stockfish` or `dnf install stockfish` |

### 3. Verify

```bash
python -c "import chess_coach; print('OK:', chess_coach.__all__)"
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
