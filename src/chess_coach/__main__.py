"""Chess Coach v3.0 "The Humanizer" — Real-time chess analysis sidekick.

v3.0 adds a 6-layer anti-detection architecture (multi-engine, CAPS, humanizer,
personality, motif, risk) so users can play chess.com without re-banning.

On first run, the app auto-downloads Stockfish 18, Lc0 v0.32.1 and Maia-1 weights
into ./lc0/ and verifies them. No manual setup needed.

Usage:
  python -m chess_coach                       Desktop GUI mode
  python -m chess_coach web                   Web server mode (http://localhost:8000)
  python -m chess_coach web 8080              Web server on custom port
  python -m chess_coach --personality aggressive --elo 1500
                                               Start with personality + target ELO
  python -m chess_coach --no-maia             Run without Maia (Stockfish only)
  python -m chess_coach --install             Force re-install Stockfish/Lc0/Maia
  python -m chess_coach --check               Just check dependencies, don't run
"""

from __future__ import annotations

import sys

logging_configured: bool = False


def _init_logging() -> None:
    global logging_configured
    if not logging_configured:
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        logging_configured = True


def _ensure_dependencies(force: bool = False, verbose: bool = True) -> bool:
    """Auto-install Stockfish + Lc0 + Maia if missing. Returns True on success.

    Runs scripts/install_deps.py. Skipped if running under PyInstaller.
    """
    from pathlib import Path
    if getattr(sys, "frozen", False):
        return True
    project_root = Path(__file__).resolve().parent.parent.parent
    installer = project_root / "scripts" / "install_deps.py"
    if not installer.exists():
        if verbose:
            print(f"[v3.0] installer missing: {installer}", file=sys.stderr)
        return False
    args = [sys.executable, str(installer)]
    if force:
        args.append("--force")
    if verbose:
        print("[v3.0] Ensuring dependencies (Stockfish 18, Lc0 v0.32.1, Maia-1)...")
    import subprocess
    try:
        result = subprocess.run(
            args,
            cwd=str(project_root),
            stdout=None if verbose else subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        return result.returncode == 0
    except Exception as e:
        if verbose:
            print(f"[v3.0] auto-install failed: {e}", file=sys.stderr)
        return False


def _quick_check() -> bool:
    """Quick check: Stockfish exists (Lc0/Maia optional)."""
    from pathlib import Path
    project_root = Path(__file__).resolve().parent.parent.parent
    return (project_root / "stockfish.exe").exists()


def _parse_humanizer_args(args: list[str]) -> dict:
    """Parse --personality, --elo, --no-maia, --no-humanizer flags."""
    out: dict = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--personality" and i + 1 < len(args):
            out["personality"] = args[i + 1]
            i += 2
        elif a == "--elo" and i + 1 < len(args):
            try:
                out["target_elo"] = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif a == "--no-maia":
            out["enable_maia"] = False
            i += 1
        elif a == "--no-humanizer":
            out["simulated_think_time"] = False
            i += 1
        else:
            i += 1
    return out


def main() -> None:
    _init_logging()

    args = [a for a in sys.argv[1:]]
    mode = "desktop"

    if "-h" in args or "--help" in args:
        print(__doc__)
        return

    if "--check" in args:
        ok = _quick_check()
        print(f"Stockfish present: {ok}")
        sys.exit(0 if ok else 1)

    if "--install" in args:
        ok = _ensure_dependencies(force=True, verbose=True)
        sys.exit(0 if ok else 1)

    # First-run auto-install: silent if everything is fine, loud if anything is missing
    if not _quick_check():
        _ensure_dependencies(force=False, verbose=True)

    h_args = _parse_humanizer_args(args)
    if h_args:
        from chess_coach.config import load_config, save_config
        cfg = load_config()
        h = cfg.setdefault("humanizer", {})
        for k, v in h_args.items():
            if k in ("enable_maia",):
                cfg[k] = v
            else:
                h[k] = v
        save_config(cfg)
        print(f"[v3.0] Applied: {h_args}")

    remaining = [a.lower() for a in args if not a.startswith("--") and a not in h_args.values()]
    if "web" in remaining or "server" in remaining:
        mode = "web"

    if mode == "desktop":
        from PyQt6.QtWidgets import QApplication
        from chess_coach.main_window import MainWindow

        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    else:
        import uvicorn
        from chess_coach.server import app
        from chess_coach.config import find_free_port, get_local_ip

        port = 8000
        for a in remaining:
            if a.isdigit():
                port = int(a)
                break

        sock, port = find_free_port(port)
        sock.close()
        local_ip = get_local_ip()

        print()
        print("=" * 50)
        print("  Chess Coach v3.0 Web Server is running!")
        print("=" * 50)
        print(f"  PC:  http://localhost:{port}")
        print(f"  Phone:  http://{local_ip}:{port}")
        print("=" * 50)
        print(f"  Phone not working? Make sure:")
        print(f"  1. Phone is on the SAME WiFi as this PC")
        print(f"  2. Windows Firewall allows port {port}")
        print(f"     -> Run this in PowerShell (as admin):")
        print(f'     New-NetFirewallRule -DisplayName "Chess Coach" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow')
        print("=" * 50)
        print()
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
