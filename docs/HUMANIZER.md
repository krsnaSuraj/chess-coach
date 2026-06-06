# Chess Coach v3.0 "The Humanizer"

> Anti-detection architecture for Stockfish + Maia in real games.
> Goal: make the AI suggest **human-like** moves so the user can play chess.com
> without re-banning.

## Why "Humanizer"?

chess.com's anti-cheat (per Dr. Kenneth Regan's IPR system) flags accounts whose
moves correlate too strongly with the **top engine line**. A user that always
plays SF's #1 move, with constant time usage, zero blunders, and uniform accuracy
across all phases, will be flagged. v3.0 layers 6 defenses to break each signal
while still keeping you competitive.

## The 6 Anti-Detection Layers

```
                   +-----------------------------+
                   |   Humanizer move selector   |   <-- what you actually play
                   +--------------+--------------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
   +----------v------+  +--------v--------+  +-------v-------+
   | Layer 1: Maia   |  | Layer 2: Persona|  | Layer 3: CAPS |
   | (human policy)  |  | (style biases)  |  | (eval gates)  |
   +-----------------+  +-----------------+  +---------------+
              |                   |                   |
              +-------------------+-------------------+
                                  |
                   +--------------v--------------+
                   |   Layer 4: Oscillation &    |
                   |   time-pressure penalties  |
                   +-------------+--------------+
                                 |
              +------------------+------------------+
              |                  |                  |
   +----------v------+  +--------v--------+  +-------v-------+
   | Layer 5: Opponent|  | Layer 6: Risk   |  | Workflow      |
   | modeler (Elo)    |  | (7-signal score)|  | Guard         |
   +-----------------+  +-----------------+  +---------------+
```

### Layer 1 — Maia Policy (Lc0)

We run **Lc0 v0.32.1** with a **Maia-1 v1.0** per-ELO weight file (`maia-1500.pb.gz`
for a 1500 ELO target). Maia is a transformer trained on human Lichess games,
so it natively produces **human** move distributions. We use this distribution
as the prior for the move selector.

**Why Maia-1 over Maia-2?** Maia-1 has a discrete weight per ELO band (1100,
1200, ..., 1900) — perfect for our `target_elo` knob. Maia-2 is a unified model
that requires a more complex inference setup.

**Graceful fallback:** if `lc0/lc0.exe` or the weight file is missing, Maia is
silently disabled and we fall back to Stockfish-only.

### Layer 2 — Personality Bias

5 profiles weight moves by style:

| Personality    | Capture | Check | King-attack | Recapture | ECO preference |
|----------------|---------|-------|-------------|-----------|----------------|
| AGGRESSIVE     | +0.6    | +0.5  | +0.4        | +0.3      | B20, B22       |
| POSITIONAL     | +0.2    | -0.1  | -0.2        | -0.1      | A15, D30       |
| TACTICAL       | +0.3    | +0.4  | +0.1        | +0.5      | B12, B90       |
| DEFENSIVE      | -0.2    | -0.3  | -0.4        | -0.2      | B12, C00       |
| BALANCED       | 0       | 0     | 0           | 0         | (any)          |

Each profile multiplies the Maia probability, then we sample (with temperature
scaling under time pressure).

### Layer 3 — CAPS V2 Classifier

We use the **chess.com CAPS V2 Expected Points Model** to gate which moves are
even considered:

| Class     | Expected-Points Lost | Color  |
|-----------|----------------------|--------|
| Brilliant | sacrifice + best/good + check | blue |
| Great     | sacrifice + best/good | cyan |
| Best      | 0.00                 | green  |
| Excellent | 0.00-0.02            | green  |
| Good      | 0.02-0.05            | light green |
| Inaccuracy| 0.05-0.10            | yellow |
| Mistake   | 0.10-0.20            | orange |
| Blunder   | 0.20-1.00            | red    |

Moves classified as MISTAKE or BLUNDER are **excluded** from the candidate set
unless no better move exists.

### Layer 4 — Oscillation & Time Pressure

* **Oscillation penalty:** if the same piece is moving back and forth (e.g.
  Ng5-f3-g5), we down-weight the oscillating move.
* **Time pressure:** under 30s on the clock, the softmax temperature is
  increased so the distribution flattens (humans play more erratically low on
  time). Below 10s we also add a small random jitter to the chosen move.
* **Think time simulation:** the recommended move is held for a sample from the
  ELO-calibrated `ThinkProfile` distribution before being shown — so the UI
  doesn't reveal the move the instant we get it.

### Layer 5 — Opponent Modeler

`OpponentModel` tracks each opponent across games:

* **BayesianELOEstimator:** prior N(1500, 400²), updated with Gaussian likelihood
  on observed ACPLs. Returns mean ELO + 95% confidence interval.
* **Style classification:** PRECISE / TACTICAL / POSITIONAL / AGGRESSIVE /
  DEFENSIVE / NOISY / UNKNOWN, derived from the move's CPL and capture/check
  frequency.

The estimated opponent ELO becomes the **target_elo** for Layer 1+2 — playing
at the opponent's level is the strongest humanizing signal.

### Layer 6 — Anti-Cheat Risk Score

`update_risk_from_history` computes a 0-100 risk score from 7 weighted signals,
inspired by Dr. Regan's published IPR weights:

| Signal                | Weight | What it catches                    |
|-----------------------|--------|------------------------------------|
| top1_match            | 30%    | Always playing the engine's #1 move|
| cpl                   | 25%    | Centipawn loss vs ELO target       |
| time_variance         | 15%    | Bot-clock uniformity               |
| style_consistency     | 10%    | No style variation across game     |
| tactical_accuracy     | 10%    | Suspiciously high tactic solve rate|
| blunder_frequency     | 5%     | Zero blunders = bot                |
| phase_variance        | 5%     | Identical accuracy in all phases   |

| Level    | Score     | Recommendation                       |
|----------|-----------|--------------------------------------|
| SAFE     | 0-30      | Continue normally                    |
| LOW      | 30-50     | Optional: enable 2nd personality     |
| MODERATE | 50-70     | Switch to defensive + raise think time|
| HIGH     | 70-85     | Stop suggesting engine top-1         |
| CRITICAL | 85-100    | Halt all suggestions this game       |

## Configuration

```yaml
humanizer:
  personality: balanced    # one of: aggressive, positional, tactical, defensive, balanced
  target_elo: 1500         # 800-2400
  simulated_think_time: true
  maia:
    auto_download: true
    default_elo: 1500
    nodes: 1
  weights:
    maia: 0.5               # weight of Maia prior in selector
    personality: 0.3
    engine: 0.2
  blend:
    oscillation_penalty: 0.5
    time_pressure_temp: 1.5
```

## CLI Flags

```bash
python -m chess_coach --personality tactical --elo 1700
python -m chess_coach --no-maia              # Stockfish-only
python -m chess_coach --no-humanizer         # raw engine output
```

## Web UI

The browser UI shows 4 v3.0 cards below the board:

- **CAPS** — color-coded classification of the last move
- **MOTIFS** — tactical patterns detected in the current position
- **RISK** — anti-cheat risk level (SAFE/LOW/MODERATE/HIGH/CRITICAL)
- **ELO** — Bayesian ELO estimate of the opponent

API: `/api/caps/last`, `/api/motifs/position`, `/api/risk/game`, `/api/elo/estimate`

## What This Does NOT Do

* v3.0 is **not** a hidden overlay. It suggests moves; the user still has to
  play them. We do not inject moves into the browser or simulate input.
* It does not use a VPN or external clicker.
* It does not pretend to "not cheat" — it just makes cheating more human-like.

## See also

* `ARCHITECTURE_V3.md` — module-by-module technical walkthrough
* `MODELS.md` — Lc0 + Maia download and licensing info
* `../README.md` — quickstart
