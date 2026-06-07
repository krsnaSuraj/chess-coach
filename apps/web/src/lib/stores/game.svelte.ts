// =============================================================
//  Game store — wraps the real backend UnifiedResponse.
//  - `state`  = latest server response
//  - `history` = client-side move log (server has no /api/history)
//  - cursor = -1 means "live", >= 0 means viewing a past ply
// =============================================================
import { Chess } from 'chess.js';
import { api } from '$lib/api/client';
import type { HistoryEntry, MoveClass, UnifiedResponse } from '$lib/types';

function classifyFromCpl(cpl: number | null): MoveClass {
  if (cpl == null) return 'BOOK';
  if (cpl <= 10) return 'BEST';
  if (cpl <= 30) return 'EXCELLENT';
  if (cpl <= 60) return 'GOOD';
  if (cpl <= 100) return 'INACCURACY';
  if (cpl <= 200) return 'MISTAKE';
  return 'BLUNDER';
}

function parseCpFromCoachString(s: string | null | undefined): number | null {
  if (!s) return null;
  const t = s.trim();
  if (!t) return null;
  if (t.startsWith('M') || t.startsWith('-M')) return null;
  const n = parseFloat(t);
  return Number.isFinite(n) ? Math.round(n * 100) : null;
}

export class GameStore {
  state = $state<UnifiedResponse | null>(null);
  history = $state<HistoryEntry[]>([]);
  cursor = $state<number>(-1); // -1 = live position
  orientation = $state<'white' | 'black'>('white');
  error = $state<string | null>(null);
  loading = $state(false);
  // Stashed entry popped by undo so a subsequent redo can restore it.
  // Cleared on newGame, on a fresh playMove, and on undo of a redo'd move.
  private _pendingRedo: HistoryEntry | null = null;

  // FEN at the current cursor (live or historical)
  displayedFen = $derived.by(() => {
    if (this.cursor < 0 || !this.state) return this.state?.fen ?? '';
    const h = this.history[this.cursor];
    return h?.fen_after ?? this.state.fen;
  });

  // Current ply (1-based, 0 if no game)
  currentPly = $derived(this.cursor < 0 ? (this.history.length ? this.history[this.history.length - 1]!.ply : 0) : this.history[this.cursor]!.ply);

  isLive = $derived(this.cursor === -1);

  // Latest eval (cp) from the most recent coach block
  latestEvalCp = $derived(parseCpFromCoachString(this.state?.coach?.eval));

  // Latest best move (UCI) from the most recent coach block
  latestBestUci = $derived(this.state?.coach?.best_move ?? null);

  // Latest PV (UCI moves) from the most recent coach block
  latestPvUci = $derived(this.state?.coach?.pv ? this.state.coach.pv.split(' ').filter(Boolean) : []);

  // Latest classification from backend (/api/caps/last-style data isn't pushed
  // to the game state; we derive it from CPL of the last human move).
  latestClassification = $derived.by(() => {
    const last = this.history[this.history.length - 1];
    return last?.classification ?? 'BOOK';
  });

  async refresh() {
    this.loading = true;
    this.error = null;
    try {
      const s = await api.gameState();
      this.state = s;
      this.error = s.error;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loading = false;
    }
  }

  async newGame(humanIsWhite = true) {
    this.history = [];
    this.cursor = -1;
    this._pendingRedo = null;
    const s = await api.startGame(humanIsWhite);
    this.state = s;
    this.error = s.error;
  }

  /**
   * Apply a human move. Sends to backend; on success records:
   *  - the human's move in history (with eval before = latestEvalCp)
   *  - any engine reply move (from state.coach.best_move) as 'engine' entry
   */
  async playMove(uci: string, promotion?: string): Promise<boolean> {
    const beforeState = this.state;
    const fenBefore = beforeState?.fen ?? this.displayedFen;
    if (!fenBefore) return false;

    let san: string;
    let fenAfterHuman: string;
    try {
      const c = new Chess(fenBefore);
      const m = c.move({
        from: uci.slice(0, 2),
        to: uci.slice(2, 4),
        promotion: uci.length === 5 ? (uci[4] as 'q' | 'r' | 'b' | 'n') : (promotion as 'q' | 'r' | 'b' | 'n' | undefined)
      });
      if (!m) return false;
      san = m.san;
      fenAfterHuman = c.fen();
    } catch {
      return false;
    }

    try {
      const res = await api.humanMove(uci, promotion);
      this.error = res.error;
      this.state = res;

      // Compute CPL using eval before (from previous coach block) and the
      // eval in the NEW coach block (which is the position AFTER the human move).
      const evalBefore = this.latestEvalCp ?? 0;
      const newEval = parseCpFromCoachString(res.coach?.eval) ?? 0;
      // For the side that just moved (human), CPL = -delta if delta is bad.
      const delta = evalBefore - newEval; // human gave up `delta` cp
      const cpl = Math.max(0, delta);

      const humanEntry: HistoryEntry = {
        ply: this.history.length + 1,
        san,
        uci,
        fen_before: fenBefore,
        fen_after: fenAfterHuman,
        eval_cp: evalBefore,
        classification: classifyFromCpl(cpl),
        cpl,
        played_by: 'human'
      };
      this.history = [...this.history, humanEntry];
      this._pendingRedo = null;
      this.cursor = -1;
      return true;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
      return false;
    }
  }

  async undo() {
    try {
      const res = await api.undo();
      this.state = res;
      this.error = res.error;
      if (this.history.length > 0) {
        const popped = this.history[this.history.length - 1]!;
        this.history = this.history.slice(0, -1);
        this._pendingRedo = popped;
      } else {
        this._pendingRedo = null;
      }
      this.cursor = -1;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    }
  }

  async redo() {
    try {
      const res = await api.redo();
      this.state = res;
      this.error = res.error;
      if (this._pendingRedo) {
        this.history = [...this.history, this._pendingRedo];
        this._pendingRedo = null;
      }
      this.cursor = -1;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    }
  }

  // Navigation — used by arrow keys
  goToStart() { this.cursor = -1; }
  goToEnd() { this.cursor = this.history.length - 1; }
  stepBack() { if (this.cursor > -1) this.cursor -= 1; }
  stepForward() { if (this.cursor < this.history.length - 1) this.cursor += 1; }

  classificationAt(ply: number): MoveClass {
    return this.history[ply]?.classification ?? 'GOOD';
  }
}
