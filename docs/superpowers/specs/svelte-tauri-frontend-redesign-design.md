# Chess Coach v3.0.0 — Svelte 5 + chessground Frontend Rebuild

> **Status**: Approved (brainstorming complete)
> **Scope**: Replace vanilla-JS web UI + PyQt6 desktop GUI with a single Svelte 5 + chessground codebase
> **Out of scope (this version)**: Replacing the Python backend

## Problem statement

The current v3.0.0 release contains 100% SOTA **backend** logic (Stockfish + 5 SOTA engines + Maia-2, classify_v2, eval/CPL/Glicko2, Lichess API, tablebase, variants, tournament, coach, PGN, openings), 903 Python tests passing, 34 test files. The **frontend** does not match this engineering quality:

- **Web UI**: vanilla HTML + plain JS, no component model, no reactivity primitives, no virtual DOM. The `static/` directory holds 7 hand-written files. WebSocket path was broken until a recent fix.
- **Desktop GUI**: 921-line PyQt6 monolith `main_window.py` plus a 221-line `coach_dashboard.py` of plain `QLabel`/`QProgressBar`/`QFrame` widgets. Visually dated, no animations, no charts, no drag-drop, no arrow overlays.
- **Arrow-key navigation**: not implemented. Only `Ctrl+Z`/`Ctrl+Y` for undo/redo exist. Left/Right for stepping through game history is missing on both web and desktop.
- **"SOTA" is currently a label, not a feature set**: the status bar shows engine names, but the UI does not deliver the Lichess-grade experiences (move-classification pills, smooth eval-bar tween, accuracy graph, opening explorer, arrow overlay, theme system, engine selector) that SOTA implies.

## Goals

1. Replace the web UI with a Svelte 5 + SvelteKit 2 + chessground + shadcn-svelte + Tailwind v4 stack that looks and behaves like Lichess.
2. Replace the PyQt6 desktop GUI with the same Svelte 5 codebase running under Tauri 2 (Rust shell) — and ship the web build as the immediate primary target while the Rust toolchain is being installed.
3. Implement all 10 SOTA UX features end-to-end so they actually work, not just appear in a status string.
4. Keep the entire Python backend (783K LOC, 903 tests, 24 REST endpoints, `/ws` WebSocket, 6 SOTA engines, classify_v2, eval, lichess, tablebase, variants, tournament, coach) **completely untouched** — the frontend consumes the existing API.
5. All 903 Python tests must stay green throughout.
6. Stay on version 3.0.0. No version bump.

## Non-goals

- Replacing the Python backend with TypeScript.
- Mobile apps (Tauri supports them; defer).
- Lichess OAuth round-trip UI polish (we already have it; minimal port only).
- Study-mode UI (the engine exists; the UI is a future task).
- Removing legacy code. Old `static/` and `main_window.py` are preserved under `_legacy/` for a 30-day safety window.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend (Svelte 5 + TS + SvelteKit 2)                       │
│  ┌─ chessground (Lichess's canvas board)                     │
│  ├─ shadcn-svelte + Tailwind v4 (UI primitives)              │
│  ├─ Svelte 5 runes ($state, $derived, $effect)               │
│  └─ @tauri-apps/api  (desktop bridge, phase 4 only)          │
└──────────┬───────────────────────────────────────────────────┘
           │  WS /ws  (eval, 200 ms throttled)
           │  REST    (game state, moves, settings, lichess, ...)
┌──────────▼───────────────────────────────────────────────────┐
│ Backend (Python FastAPI)  — UNCHANGED                        │
│  783K LOC · 903 tests · 24 endpoints · 6 engines · Maia-2    │
└──────────────────────────────────────────────────────────────┘
```

### Layout

```
chess-coach/
├── apps/
│   ├── web/                  SvelteKit 2 static build (today)
│   └── desktop/              Tauri 2 + SvelteKit (phase 4)
├── packages/
│   └── ui/                   Shared Svelte 5 components
├── src/chess_coach/          Python (unchanged)
├── tests/                    Python tests (unchanged)
├── _legacy/
│   ├── static/               old vanilla-JS web (preserved)
│   └── main_window.py        old PyQt6 GUI (preserved, but the
│                             import is no longer wired)
├── docs/
│   └── superpowers/
│       └── specs/            this file
└── stockfish.exe             UCI engine
```

## SOTA features (all 10 must work end-to-end)

| # | Feature | Component | Backend | Frontend technique |
|---|---------|-----------|---------|---------------------|
| 1 | Arrow-key nav (Left/Right/Home/End) | `MoveList.svelte` | `move_history` field on `GameState` | `keydown` handler + `$effect` |
| 2 | Move classification pills (11 classes) | `MovePill.svelte` | `classify_v2.classify()` | Tailwind class map by MoveClass |
| 3 | Eval bar tween (200 ms easeOutCubic) | `EvalBar.svelte` | `eval` field on WS msg | `requestAnimationFrame` |
| 4 | Arrow overlay (best + alt + blunder) | `Board.svelte` | engine MultiPV | chessground native `setShapes` |
| 5 | Live WS eval streaming | `eval.svelte.ts` | `/ws` | Svelte 5 class with `$state` |
| 6 | Accuracy graph (CPL over time) | `AccuracyGraph.svelte` | `eval.cpl()` | Canvas 2D |
| 7 | Opening explorer (Lichess DB) | `OpeningExplorer.svelte` | `lichess.explorer` | Table + sparkline |
| 8 | Theme system (10 themes) | `ThemeSwitcher.svelte` | — | CSS variables |
| 9 | Promotion dialog (smooth) | `PromotionDialog.svelte` | — | shadcn-svelte Dialog |
| 10 | Engine selector (7 engines) | `EngineSelector.svelte` | `engines/base.py` | shadcn-svelte Select |

## State management — Svelte 5 runes

```ts
// stores/eval.svelte.ts
class EvalStore {
  current = $state(0)              // displayed eval (lerped)
  target  = $state(0)              // target eval (from WS)
  pv      = $state<string[]>([])
  multipv = $state<PvLine[]>([])
  cls     = $state<MoveClass>('BOOK')

  private t0 = 0
  private from = 0

  onWs(msg: WsEvalMessage) {
    this.target = msg.eval
    this.pv     = msg.pv
    this.multipv = msg.multipv
    this.cls    = msg.classification
    this.t0     = performance.now()
    this.from   = this.current
  }

  // one animation loop per store instance
  start() {
    const tick = (now: number) => {
      const t = Math.min(1, (now - this.t0) / 200)
      this.current = lerp(this.from, this.target, easeOutCubic(t))
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }
}
```

## Backend contract (no change)

The existing FastAPI backend already serves every endpoint the new frontend needs:

- `GET  /`                                  index
- `GET  /api/game_state`                    current state
- `POST /api/move`                          make a move
- `POST /api/undo` · `POST /api/redo`
- `POST /api/new_game` · `POST /api/load_pgn` · `POST /api/export_pgn`
- `POST /api/load_fen` · `POST /api/load_opening`
- `GET  /api/settings` · `POST /api/settings`
- `GET  /api/analysis` · `POST /api/analysis/start` · `POST /api/analysis/stop`
- `GET  /api/opening_explorer?fen=...`
- `GET  /api/tablebase?fen=...`
- `GET  /api/cloud_eval?fen=...`
- `POST /api/lichess/...` (10 endpoints)
- `WS   /ws`                                live eval stream

## Testing strategy

| Layer | Tool | Target |
|-------|------|--------|
| Python (unchanged) | `pytest` | 903 tests stay green |
| Svelte components | `vitest` + `@testing-library/svelte` | Stores, utilities, components |
| Svelte runes | `vitest` | State transitions, derived values |
| WebSocket flow | `vitest` + mock WS | Eval store updates |
| E2E web | `playwright` | Full game flow + WS connectivity |
| E2E desktop | `tauri webdriver` (phase 4) | Native window |

## Migration phases

**Phase 1 — SvelteKit 2 + Svelte 5 + chessground + WS eval (MVP)**
- Replace `static/` → SvelteKit app
- Board + eval bar + arrow keys
- Connect to existing `/ws` and `/api/game_state`
- All 903 Python tests stay green
- Vitest skeleton + Playwright skeleton

**Phase 2 — UI polish + shadcn-svelte**
- Move classification pills
- Promotion dialog
- Theme system (10 themes)
- Engine selector
- Toast / sound integration

**Phase 3 — Advanced SOTA**
- Arrow overlay (chessground native)
- Accuracy graph
- Opening explorer inline
- Game review playback

**Phase 4 — Tauri 2 desktop shell**
- `apps/desktop/` wraps `apps/web/` via `@tauri-apps/api`
- 5 MB Windows / macOS / Linux binary
- Same Svelte codebase
- Native menu bar (File / Engine / Coach / Tournament / Lichess / Variants / Help)

**Phase 5 — Cutover**
- Old `static/` + `main_window.py` moved to `_legacy/`
- New Svelte becomes default
- All 903 + new Vitest + new Playwright tests green
- README + ARCHITECTURE.md updated to reference the new entrypoints

## Risks + mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Tauri build on Windows | Medium | Phase 4 only; Rust install deferred; web build is the primary deliverable now |
| `chessground` v8/v9 API drift | Low | Pin a known-good version in `package.json` + lockfile |
| WebSocket msg volume | Medium | Throttle to 200 ms; debounce UI updates with `requestAnimationFrame` |
| Python regressions | **HIGH** | Keep all 903 tests green throughout; add a CI matrix that runs them on every frontend change |
| Lichess explorer rate limit | Low | Existing SQLite cache at `lichess/cache.py` is reused unchanged |
| No-dates constraint | Low | The spec filename intentionally omits a date |

## Definition of done

- All 903 Python tests pass.
- New Vitest + Playwright suites pass.
- Manual smoke: open `http://localhost:5173`, board renders, WS connects, eval bar tween is smooth, Left/Right navigates the game history, classification pills appear, theme switch works, engine selector lists 7 engines, promotion dialog appears on promotion, opening explorer returns data, accuracy graph renders.
- Tauri desktop binary (phase 4) builds and runs.
- README + ARCHITECTURE.md updated.
- One commit on the v3.0-humanizer branch; main branch still behind (no push without explicit user instruction).

## Open questions

- None. User has explicitly delegated architecture choices with the message "khud choose karo deep research karke".
