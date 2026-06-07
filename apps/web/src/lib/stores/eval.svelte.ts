// =============================================================
//  Eval store — drives the tweened bar, PV display, history graph.
//  Two data paths:
//   1. WS analysis_update envelopes (real-time, when broadcasting)
//   2. REST /api/human_move coach block (after each move)
// =============================================================
import { easeOutCubic, lerp, clamp } from '$lib/utils/tween';
import type { CoachEval, MoveClass, PvLine, WsAnalysisUpdate } from '$lib/types';

export class EvalStore {
  // live target values
  targetCp = $state(0);
  targetMate = $state<number | null>(null);
  depth = $state(0);
  multipv = $state<PvLine[]>([]);
  bestSan = $state('');
  bestUci = $state('');
  classification = $state<MoveClass>('BOOK');
  nodes = $state(0);
  nps = $state(0);
  timeMs = $state(0);

  // tweened values
  displayedCp = $state(0);
  winProb = $state(0.5);

  // history (for the accuracy graph)
  history = $state<Array<{ ply: number; cp: number; cls: MoveClass }>>([]);

  // internal
  #tweenFrom = 0;
  #tweenStart = 0;
  #raf = 0;
  #active = false;

  start() { this.#active = true; this.#tick(); }
  stop() { this.#active = false; if (this.#raf) cancelAnimationFrame(this.#raf); }

  reset() {
    this.targetCp = 0; this.displayedCp = 0;
    this.targetMate = null;
    this.depth = 0; this.multipv = []; this.bestSan = ''; this.bestUci = '';
    this.classification = 'BOOK';
    this.nodes = 0; this.nps = 0; this.timeMs = 0;
    this.history = [];
    this.#tweenFrom = 0;
    this.#tweenStart = performance.now();
  }

  /** Feed a REST coach block (from /api/human_move response). */
  fromCoach(coach: CoachEval | null, ply: number, cls: MoveClass = 'GOOD') {
    if (!coach) return;
    const cp = this.#parseCp(coach.eval);
    this.#tweenFrom = this.displayedCp;
    this.#tweenStart = performance.now();
    this.targetCp = cp;
    this.targetMate = null;
    this.bestUci = coach.best_move ?? '';
    this.classification = cls;
    this.depth = this.depth;
    this.#appendHistory(ply, cp, cls);
  }

  /** Feed a WS analysis_update envelope. */
  onWsAnalysisUpdate(msg: WsAnalysisUpdate) {
    if (msg.type !== 'analysis_update') return;
    // Reconstruct PV lines from message.lines if provided
    const lines: PvLine[] = (msg.lines ?? []).map((l) => ({
      multipv: l.multipv,
      eval_cp: l.eval_cp,
      eval_mate: l.eval_mate ?? null,
      depth: l.depth,
      pv: l.pv ?? [],
      san: l.san ?? []
    }));
    this.#tweenFrom = this.displayedCp;
    this.#tweenStart = performance.now();
    this.targetCp = lines[0]?.eval_cp ?? 0;
    this.targetMate = lines[0]?.eval_mate ?? null;
    this.depth = msg.depth ?? 0;
    this.multipv = lines;
    this.bestUci = msg.best_move ?? '';
    this.classification = (msg.classification as MoveClass) ?? 'GOOD';
    this.#appendHistory(lines[0]?.multipv ?? 0, this.targetCp, this.classification);
  }

  #appendHistory(ply: number, cp: number, cls: MoveClass) {
    const last = this.history.at(-1);
    if (last && last.ply === ply) {
      this.history = [...this.history.slice(0, -1), { ply, cp, cls }];
    } else {
      this.history = [...this.history, { ply, cp, cls }];
    }
  }

  #parseCp(s: string | null | undefined): number {
    if (!s) return 0;
    const t = s.trim();
    if (t.startsWith('M') || t.startsWith('-M')) return 0;
    const n = parseFloat(t);
    return Number.isFinite(n) ? Math.round(n * 100) : 0;
  }

  #tick = () => {
    if (!this.#active) return;
    const now = performance.now();
    const t = clamp((now - this.#tweenStart) / 200, 0, 1);
    this.displayedCp = lerp(this.#tweenFrom, this.targetCp, easeOutCubic(t));
    this.winProb = 0.5 + 0.5 * (2 / (1 + Math.exp(-0.004 * this.displayedCp)) - 1);
    this.#raf = requestAnimationFrame(this.#tick);
  };
}
