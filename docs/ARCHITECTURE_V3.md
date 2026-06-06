# Architecture v3.0

> Module-by-module technical reference for Chess Coach v3.0 "The Humanizer".

## High-level Data Flow

```
       +-----------+        +-----------+        +-----------+
       |   Board   |  push  |  humanizer|  select|  Move out |
       |  (user)   +------->|  .select_ +------->|  (display)|
       +-----------+        |   move    |        +-----------+
                            +-----+-----+
                                  |
            +---------------------+---------------------+
            |                     |                     |
    +-------v-------+    +---------v--------+   +-------v-------+
    | multi_engine  |    |   personality   |   |     caps      |
    |   _handler    |    |   .bias_move    |   |  .classify    |
    +-------+-------+    +-----------------+   +---------------+
            |
   +--------+--------+
   |                 |
+-v----+      +------v------+
| SF   |      |  Maia (Lc0) |
|depth |      |  nodes=1    |
+-v----+      +------v------+
   |                 |
   +--------+--------+
            |
            v
       +----+----+      +------------+
       | elo_    |      | motif_     |     +----------+
       | calib   |      | detector   |     | opponent_|
       +---------+      +------------+     |  modeler |
                                          +----+-----+
                                               |
                                          +----v----+
                                          |  risk   |
                                          |  score  |
                                          +---------+
```

## Module Index

| Module                    | LOC | Purpose                                  |
|---------------------------|-----|------------------------------------------|
| `chess_coach/elo_calibrator.py` | ~280 | ELO → engine depth, think time, ACPL target, Bayesian ELO estimator |
| `chess_coach/personality.py`    | ~350 | 5 style profiles with move-bias dicts   |
| `chess_coach/maia_engine.py`    | ~230 | Lc0 subprocess wrapper + auto-download  |
| `chess_coach/caps.py`           | ~280 | CAPS V2 Expected Points classifier      |
| `chess_coach/motif_detector.py` | ~280 | 8 tactical pattern detectors            |
| `chess_coach/opponent_modeler.py` | ~160 | Bayesian opponent ELO + style classifier |
| `chess_coach/anti_cheat_risk.py`  | ~190 | 7-signal risk score (chess.com weights)  |
| `chess_coach/humanizer.py`        | ~240 | Move selection + think-time simulation   |
| `chess_coach/multi_engine_handler.py` | ~210 | Parallel SF + Maia orchestration         |
| `chess_coach/engine_handler.py`   | ~140 | Backward-compat thin facade              |

## Key Algorithms

### 1. ELO Calibration

10 ELO bands from 800 to 2400. Each band defines:

* **EngineProfile**: `depth`, `movetime_ms`, `multipv`, `skill_level`, `hash_mb`
* **ThinkProfile**: `min_seconds`, `max_seconds`, `mean_seconds`, `critical_boost`, `complexity_factor`
* **ACPLTarget**: `opening`, `middlegame`, `endgame`, `overall`

For ELOs between bands, we **interpolate** linearly.

The `BayesianELOEstimator` is a stateful object:

```
prior:    N(μ=1500, σ=400)
update:   likelihood = N(cpl | target_elo, σ=max(8, target×0.25))
posterior: N(μ', σ')  via Bayes rule on candidate grid
```

### 2. CAPS V2 Classification

```python
epl = max(0, wp_before - wp_after)
if epl == 0.0:                → BEST
elif epl < 0.02:              → EXCELLENT
elif epl < 0.05:              → GOOD
elif epl < 0.10:              → INACCURACY
elif epl < 0.20:              → MISTAKE
else:                         → BLUNDER

# Brilliant / Great heuristic:
if is_sacrifice and class in (BEST, EXCELLENT, GOOD) and gives_check:
    → BRILLIANT (or GREAT if not check)
```

### 3. Humanizer Move Selection

```
P(move) = softmax(
    maia_weight × log(maia_prob[move])
  + personality_weight × (bias[move] - 1.0) / 0.6
  + engine_weight × engine_factor[move]
) × oscillation_penalty[move]

move = argmax(P) if not time_pressure
     ~ sample(P, temperature=base × time_pressure_factor) otherwise
```

`engine_factor[move]` is `1.0` for top-1, `0.5` for top-2, `0.25` for top-3, etc.

### 4. Multi-Engine Orchestration

`MultiEngineHandler` runs SF and Maia in **parallel QThreads**:

```
+-- StockfishAnalysisThread --+
|  spawns: chess.engine.popen_uci(SF)
|  waits for analysis_update signal
+-----------------------------+

+-- MaiaAnalysisThread --+
|  spawns: subprocess lc0 --weights=maia.pb.gz
|  parses "info string" with move probabilities
+------------------------+

Both threads share a queue of pending boards (versioned to ignore stale).
```

If Maia fails to spawn, `maia_available = False` and the handler degrades to
Stockfish-only silently.

### 5. Risk Score (chess.com-derived weights)

```
risk = 0.30 × top1_risk
     + 0.25 × cpl_risk
     + 0.15 × time_variance_risk
     + 0.10 × style_consistency_risk
     + 0.10 × tactical_accuracy_risk
     + 0.05 × blunder_freq_risk
     + 0.05 × phase_variance_risk
```

Each `*_risk` function returns 0-100 based on observed-vs-expected.

## State Management

All UI state is owned by `MainWindow` (desktop) or `GameController` (web).
The 6 humanizer modules are **stateless** — they take a `Board`, history, and
config, and return a decision. This makes them trivially testable and lets
us run them offline.

## Threading Model

```
Main thread (UI):
  - PyQt6 event loop OR FastAPI request loop
  - calls Humanizer/Hooks synchronously

SF thread (QThread):
  - long-lived, fed analysis requests

Maia thread (QThread):
  - long-lived, fed policy requests

Communication: Qt signals (analysis_update, maia_update, error_occurred)
```

## Configuration

`config.yaml` is loaded once at startup into a `Config` dataclass. The
`HumanizerConfig` is a sub-dataclass. Changes via the GUI dialog call
`save_config()` which writes back to YAML atomically.

## Failure Modes & Graceful Degradation

| Failure                          | Behavior                                |
|----------------------------------|-----------------------------------------|
| `lc0/lc0.exe` missing            | Maia disabled, SF-only                  |
| `lc0/weights/maia-1500.pb.gz` missing | auto-downloaded; if fail, Maia disabled |
| Stockfish crash                  | Engine handler restarts up to 3 times   |
| Network down                     | `SyncService` queues, retries on back   |
| WebSocket disconnect             | Client auto-reconnects with backoff     |

## Testing

199 tests across 13 files (was 68 in v2.0):

```
tests/test_elo_calibrator.py            18 tests
tests/test_personality.py               15 tests
tests/test_maia_engine.py               17 tests
tests/test_caps.py                      21 tests
tests/test_motif_detector.py            12 tests
tests/test_opponent_modeler.py           9 tests
tests/test_anti_cheat_risk.py           17 tests
tests/test_humanizer.py                 13 tests
tests/test_multi_engine_handler.py       7 tests
+ v2.0 tests (auth, eco, pgn, game_controller, etc.) 70 tests
```

Run: `python -m pytest -v` from the project root.
