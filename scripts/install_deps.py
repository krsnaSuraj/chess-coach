"""One-shot auto-installer for Chess Coach v3.0 dependencies.

Downloads and verifies:
  - Stockfish 18 (Windows build) — required for any analysis
  - Lc0 v0.32.1 (CPU build) — optional, for Maia policy
  - Maia-1 v1.0 weight files (1100, 1500, 1900) — optional

Idempotent: re-running is safe. Each component is downloaded only if missing
or broken, then verified with a quick `--version` / UCI ping.

Usage:
    python scripts/install_deps.py                # install everything
    python scripts/install_deps.py --stockfish-only
    python scripts/install_deps.py --no-stockfish # skip Stockfish
    python scripts/install_deps.py --no-maia      # skip Lc0+Maia
    python scripts/install_deps.py --maia-elos 1100 1500 1900
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STOCKFISH_PATH = PROJECT_ROOT / "stockfish.exe"
LC0_DIR = PROJECT_ROOT / "lc0"
LC0_EXE = LC0_DIR / "lc0.exe"
LC0_ZIP = LC0_DIR / "lc0.zip"
LC0_WEIGHTS_DIR = LC0_DIR / "weights"

# Stable URLs (Nov 2025)
STOCKFISH_URL = (
    "https://github.com/official-stockfish/Stockfish/releases/download/"
    "sf_18/stockfish-windows-x86-64-avx2.zip"
)
LC0_URL = (
    "https://github.com/LeelaChessZero/lc0/releases/download/"
    "v0.32.1/lc0-v0.32.1-windows-cpu-dnnl.zip"
)
MAIA_WEIGHTS_URL = (
    "https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-{elo}.pb.gz"
)


def _print(msg: str) -> None:
    print(msg, flush=True)


def _download(url: str, dest: Path, label: str, timeout: int = 300) -> bool:
    """Download a URL to `dest` with progress logging. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 1024:
        _print(f"  [skip] {label} already at {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    _print(f"  [get ] {label}")
    _print(f"         {url}")
    _print(f"         -> {dest}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "chess-coach-v3-installer"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            chunk_size = 64 * 1024
            downloaded = 0
            start = time.time()
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and downloaded % (chunk_size * 20) == 0:
                        pct = 100 * downloaded / total
                        speed = downloaded / max(1, time.time() - start) / 1024
                        _print(f"         {pct:5.1f}%  {downloaded:,}/{total:,} bytes  ({speed:.0f} KB/s)")
        elapsed = time.time() - start
        size_mb = dest.stat().st_size / 1024 / 1024
        _print(f"  [done] {label} ({size_mb:.1f} MB in {elapsed:.1f}s)")
        return True
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        _print(f"  [FAIL] {label}: {e}")
        if dest.exists():
            dest.unlink()
        return False


def _extract_zip(zip_path: Path, dest_dir: Path, label: str) -> bool:
    """Extract a .zip into `dest_dir`."""
    import zipfile
    _print(f"  [unzp] {label}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        zip_path.unlink()
        _print(f"  [done] extracted to {dest_dir}")
        return True
    except (zipfile.BadZipFile, OSError) as e:
        _print(f"  [FAIL] extract: {e}")
        return False


def _verify_exe(path: Path, version_arg: str, expected_substring: str) -> bool:
    """Run `path version_arg` and check the output contains `expected_substring`."""
    if not path.exists():
        return False
    try:
        result = subprocess.run(
            [str(path), version_arg],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        out = (result.stdout or "") + (result.stderr or "")
        ok = expected_substring.lower() in out.lower()
        _print(f"  [vrfy] {path.name} → {'OK' if ok else 'MISMATCH'}: {out.splitlines()[0] if out else '(no output)'}")
        return ok
    except (subprocess.SubprocessError, OSError) as e:
        _print(f"  [vrfy] {path.name} → FAIL: {e}")
        return False


def _verify_gzip(path: Path) -> bool:
    """Verify a .gz file is a valid gzip archive and contains a non-trivial payload."""
    if not path.exists():
        return False
    try:
        with gzip.open(path, "rb") as gz:
            head = gz.read(8)
        size = path.stat().st_size
        ok = len(head) == 8 and size > 100_000
        _print(f"  [vrfy] {path.name} → {'OK' if ok else 'MISMATCH'} ({size:,} bytes gzip)")
        return ok
    except (OSError, gzip.BadGzipFile) as e:
        _print(f"  [vrfy] {path.name} → FAIL: {e}")
        return False


def install_stockfish(force: bool = False) -> bool:
    """Download + verify Stockfish. Idempotent unless `force=True`."""
    _print("\n[1/3] Stockfish 18")
    if STOCKFISH_PATH.exists() and not force:
        _print(f"  [skip] stockfish.exe already at {STOCKFISH_PATH}")
    else:
        tmp_zip = PROJECT_ROOT / "_stockfish_tmp.zip"
        if not _download(STOCKFISH_URL, tmp_zip, "Stockfish 18 (Windows AVX2)"):
            return False
        if not _extract_zip(tmp_zip, PROJECT_ROOT, "Stockfish"):
            return False
    return _verify_exe(STOCKFISH_PATH, "--help", "stockfish")


def install_lc0(force: bool = False) -> bool:
    """Download + extract + verify Lc0. Idempotent unless `force=True`."""
    _print("\n[2/3] Lc0 v0.32.1 (CPU DNNL)")
    LC0_DIR.mkdir(parents=True, exist_ok=True)
    if LC0_EXE.exists() and not force:
        _print(f"  [skip] lc0.exe already at {LC0_EXE}")
    else:
        if not _download(LC0_URL, LC0_ZIP, "Lc0 v0.32.1 (Windows CPU DNNL)"):
            return False
        if not _extract_zip(LC0_ZIP, LC0_DIR, "Lc0"):
            return False
    # Remove any default Lc0 network that came in the zip — we want Maia only
    default_net = LC0_DIR / "791556.pb.gz"
    if default_net.exists():
        default_net.unlink()
        _print("  [clnr] removed default 791556.pb.gz (using Maia instead)")
    return _verify_exe(LC0_EXE, "--help", "v0.32.1")


def install_maia(elos: list[int] | None = None, force: bool = False) -> bool:
    """Download + verify Maia weight files. Default: 1100, 1500, 1900."""
    _print("\n[3/3] Maia-1 v1.0 weights")
    LC0_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    elos = elos or [1100, 1500, 1900]
    all_ok = True
    for elo in elos:
        url = MAIA_WEIGHTS_URL.format(elo=elo)
        dest = LC0_WEIGHTS_DIR / f"maia-{elo}.pb.gz"
        if not _download(url, dest, f"Maia-{elo}.pb.gz"):
            all_ok = False
            continue
        if not _verify_gzip(dest):
            all_ok = False
    return all_ok


def install_all(args: argparse.Namespace) -> int:
    _print("=" * 60)
    _print("  Chess Coach v3.0 — One-Shot Dependency Installer")
    _print("=" * 60)
    _print(f"  Project:  {PROJECT_ROOT}")
    _print(f"  Python:   {sys.version.split()[0]}")
    _print(f"  Platform: {sys.platform}")

    results: dict[str, bool] = {}

    if not args.no_stockfish:
        results["stockfish"] = install_stockfish(force=args.force)
    else:
        _print("\n[1/3] Stockfish — SKIPPED (--no-stockfish)")
        results["stockfish"] = True

    if not args.no_maia:
        results["lc0"] = install_lc0(force=args.force)
        results["maia"] = install_maia(args.maia_elos, force=args.force)
    else:
        _print("\n[2/3] Lc0   — SKIPPED (--no-maia)")
        _print("[3/3] Maia  — SKIPPED (--no-maia)")
        results["lc0"] = True
        results["maia"] = True

    if args.stockfish_only:
        _print("\n[Mode] stockfish-only — skipping Lc0+Maia")
        results["lc0"] = True
        results["maia"] = True

    _print("\n" + "=" * 60)
    if all(results.values()):
        _print("  ✅ All components installed and verified.")
        _print("  Run: python -m chess_coach")
        return 0
    else:
        _print("  ⚠️  Some components failed:")
        for k, v in results.items():
            _print(f"     {'✓' if v else '✗'} {k}")
        _print("  The app will still run with the components that succeeded.")
        return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Chess Coach v3.0 dependency installer")
    p.add_argument("--stockfish-only", action="store_true",
                   help="Install only Stockfish, skip Lc0+Maia")
    p.add_argument("--no-stockfish", action="store_true",
                   help="Skip Stockfish (use existing or fall back to Maia-only)")
    p.add_argument("--no-maia", action="store_true",
                   help="Skip Lc0 + Maia (Stockfish-only mode)")
    p.add_argument("--maia-elos", nargs="+", type=int, default=None,
                   help="Maia ELO bands to download (default: 1100 1500 1900)")
    p.add_argument("--force", action="store_true",
                   help="Re-download even if file already exists")
    args = p.parse_args()
    return install_all(args)


if __name__ == "__main__":
    sys.exit(main())
