"""Chess Coach v3.0 "The Humanizer" — Real-time chess analysis sidekick.

v3.0 adds a 6-layer anti-detection architecture (multi-engine, CAPS, humanizer,
personality, motif, risk) so users can play chess.com without re-banning.

Usage:
  python -m chess_coach                       Desktop GUI mode
  python -m chess_coach web                   Web server mode (http://localhost:8000)
  python -m chess_coach web 8080              Web server on custom port
  python -m chess_coach --personality aggressive --elo 1500
                                               Start with personality + target ELO
  python -m chess_coach --no-maia             Run without Maia (Stockfish only)
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
