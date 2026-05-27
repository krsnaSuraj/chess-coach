"""Chess Coach — Real-time chess analysis sidekick.

Usage:
  python -m chess_coach          Desktop GUI mode
  python -m chess_coach web      Web server mode (http://localhost:8000)
  python -m chess_coach web 8080 Web server on custom port
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

    if "web" in args or "server" in args or "--web" in args:
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
        for a in args:
            if a.isdigit():
                port = int(a)
                break

        sock, port = find_free_port(port)
        sock.close()
        local_ip = get_local_ip()

        print()
        print("=" * 50)
        print("  Chess Coach Web Server is running!")
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
