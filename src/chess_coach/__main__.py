"""Chess Coach v0.1.1 — Real-time chess analysis sidekick.

Usage:
  python -m chess_coach                 Desktop GUI mode
  python -m chess_coach web             Web server, LAN (http://localhost:8000)
  python -m chess_coach web 8012        Web server on custom port
  python -m chess_coach web --local     Web server, localhost only (no LAN)
  python -m chess_coach --version       Print version
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


def main() -> None:
    _init_logging()

    args = [a.lower() for a in sys.argv[1:]]
    mode = "desktop"

    if "-h" in args or "--help" in args:
        print(__doc__)
        return

    if "-v" in args or "--version" in args:
        try:
            from chess_coach import __version__
        except Exception:
            __version__ = "unknown"
        print(f"chess-coach {__version__}")
        return

    if "web" in args or "server" in args or "--web" in args:
        mode = "web"

    if mode == "desktop":
        from PyQt6.QtWidgets import QApplication
        from chess_coach.main_window import MainWindow

        qt_app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(qt_app.exec())
    else:
        import uvicorn
        from chess_coach.server import app
        from chess_coach.config import find_free_port, get_local_ip

        port = 8000
        for a in args:
            if a.isdigit():
                port = int(a)
                break
        if not 1 <= port <= 65535:
            print(f"Invalid port {port!r} — must be 1..65535, using 8000")
            port = 8000
        local_only = "--local" in args or "localhost" in args
        host = "127.0.0.1" if local_only else "0.0.0.0"

        try:
            sock, port = find_free_port(port)
        except OSError as e:
            print(f"Could not bind port {port}: {e}")
            return
        sock.close()
        local_ip = get_local_ip()

        print()
        print("=" * 50)
        print("  Chess Coach Web Server is running!")
        print("=" * 50)
        print(f"  PC:  http://localhost:{port}")
        if local_only:
            print("  (localhost only — LAN/phone disabled)")
        else:
            print(f"  Phone:  http://{local_ip}:{port}")
        print("=" * 50)
        if not local_only:
            print("  Phone not working? Make sure:")
            print("  1. Phone is on the SAME WiFi as this PC")
            print(f"  2. Firewall allows port {port} (Windows admin PS:")
            print(
                f'     New-NetFirewallRule -DisplayName "Chess Coach" -Direction Inbound -Protocol TCP -LocalPort {port} -Action Allow'
            )
            print("     Linux: sudo ufw allow {}/tcp".format(port))
            print("=" * 50)
            print()
        uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
