// =============================================================
//  Eval store — receives live eval from WS, drives the
//  tweened bar, the move classification, and the PV display.
// =============================================================
import { easeOutCubic, lerp, clamp } from '$lib/utils/tween';
import type { MoveClass, PvLine, WsEvalMessage } from '$lib/types';

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

  start() {
    this.#active = true;
    this.#tick();
  }

  stop() {
    this.#active = false;
    if (this.#raf) cancelAnimationFrame(this.#raf);
  }

  reset(fen?: string) {
    this.targetCp = 0;
    this.displayedCp = 0;
    this.targetMate = null;
    this.depth = 0;
    this.multipv = [];
    this.bestSan = '';
    this.bestUci = '';
    this.classification = 'BOOK';
    this.nodes = 0;
    this.nps = 0;
    this.timeMs = 0;
    this.history = [];
    this.#tweenFrom = 0;
    this.#tweenStart = performance.now();
  }

  onWs(msg: WsEvalMessage, ply: number) {
    if (msg.type !== 'eval') return;
    this.#tweenFrom = this.displayedCp;
    this.#tweenStart = performance.now();
    this.targetCp = msg.eval_cp ?? 0;
    this.targetMate = msg.eval_mate ?? null;
    this.depth = msg.depth ?? 0;
    this.multipv = msg.multipv ?? [];
    this.bestSan = msg.best_move_san ?? '';
    this.bestUci = msg.best_move_uci ?? '';
    this.classification = msg.classification ?? 'GOOD';
    this.nodes = msg.nodes ?? 0;
    this.nps = msg.nps ?? 0;
    this.timeMs = msg.time_ms ?? 0;

    // Append to history (one entry per ply; same-ply updates the latest entry)
    const last = this.history.at(-1);
    if (last && last.ply === ply) {
      this.history = [
        ...this.history.slice(0, -1),
        { ply, cp: this.targetCp, cls: this.classification }
      ];
    } else {
      this.history = [
        ...this.history,
        { ply, cp: this.targetCp, cls: this.classification }
      ];
    }
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
