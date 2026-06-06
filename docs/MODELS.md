# Models — Lc0 + Maia

> v3.0 optionally uses a neural network (Lc0 + Maia weights) to model
> human move priors. This document covers installation, licensing, and
> trade-offs.

## What's included by default

* **Stockfish 18** — classical alpha-beta engine, top-1 move accuracy
  on par with SFNNUE. Bundled as `stockfish.exe` at the project root.
  No additional download required.

## What's optional (v3.0)

* **Lc0 v0.32.1** (Leela Chess Zero) — neural network engine.
* **Maia-1 v1.0** per-ELO weight files (`maia-1100.pb.gz` ... `maia-1900.pb.gz`).

## Why these specific versions?

| Component | Version | Why                                           |
|-----------|---------|-----------------------------------------------|
| Lc0       | v0.32.1 | Latest stable release (Nov 2025)              |
| Maia-1    | v1.0    | Per-ELO weights, simple Lc0 integration       |
| Maia-2    | NOT used | Unified model, more complex inference setup  |
| Maia-3    | Future  | Chessformer (ICML 2026), not yet released     |

## Auto-download

On first launch with `enable_maia: true` in `config.yaml`, the app will:

1. Download Lc0 v0.32.1 zip to `lc0/lc0.zip` and extract `lc0.exe`
2. Download `maia-{target_elo}.pb.gz` (e.g. `maia-1500.pb.gz`) to `lc0/weights/`

Total download: ~50 MB for Lc0 + ~25 MB for a single Maia weight.

Set `humanizer.maia.auto_download: false` to skip this and use Stockfish only.

## Manual download

```bash
# Lc0 v0.32.1 (Windows CPU)
curl -L -o lc0/lc0.zip https://github.com/LeelaChessZero/lc0/releases/download/v0.32.1/lc0-v0.32.1-windows-cpu-dnnl.zip
# Extract
Expand-Archive lc0/lc0.zip lc0/

# Maia-1 weights (one per ELO)
curl -L -o lc0/weights/maia-1500.pb.gz https://github.com/CSSLab/maia-chess/releases/download/v1.0/maia-1500.pb.gz
```

## Licensing

| Component | License          | Notes                                     |
|-----------|------------------|-------------------------------------------|
| Lc0       | GPL-3.0          | Free for personal/commercial use          |
| Maia-1    | MIT              | CSSLab, requires attribution              |
| Maia-2    | MIT              | Same                                       |
| Stockfish | GPL-3.0          | Same                                      |

**Implication for v3.0:** the Maia integration is a **derived work** only
because we use Lc0 as a subprocess (not linked). This is the same approach
as any UCI wrapper, so GPL-3.0 linking concerns do not apply to us.

## Performance

* **Stockfish 18** at depth 18 on a modern CPU: ~0.5s/move.
* **Lc0 v0.32.1** with `nodes 1`: ~50ms/move. Used only for move distribution
  (the policy head), not for search.
* **Maia weight loading**: ~3s cold start, then hot in OS file cache.

## Memory

* Lc0 process: ~200 MB resident
* Maia weight: ~25 MB on disk, ~80 MB in RAM
* Stockfish: ~50 MB

## When NOT to use Maia

* If your machine has < 4 GB RAM free
* If you have already been flagged on chess.com (use Stockfish-only with
  high-`oscillation_penalty` instead)
* If you don't want a 75 MB download (Stockfish-only is fully self-contained)

## Fallback behavior

```python
# maia_engine.py
try:
    engine = MaiaEngine(MaiaConfig(lc0_path="lc0/lc0.exe", ...))
    if not engine.start():
        logger.info("Maia unavailable; using Stockfish only")
        engine = None
except FileNotFoundError:
    engine = None
```

The rest of the humanizer pipeline (CAPS, personality, oscillation, time
pressure, risk) works fine without Maia — you just get uniform priors
instead of human-policy priors.
