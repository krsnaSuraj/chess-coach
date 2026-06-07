import { describe, it, expect, beforeEach } from 'vitest';
import { EvalStore } from '../lib/stores/eval.svelte';
import type { WsAnalysisUpdate } from '../lib/types';

function makeUpdate(overrides: Partial<WsAnalysisUpdate> = {}): WsAnalysisUpdate {
  return {
    type: 'analysis_update',
    v: 1,
    ts: Date.now(),
    fen: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    best_move: 'e2e4',
    classification: 'GOOD',
    accuracy: 0.5,
    depth: 10,
    finished: false,
    lines: [],
    ...overrides
  };
}

describe('EvalStore', () => {
  let store: EvalStore;

  beforeEach(() => {
    store = new EvalStore();
    store.start();
  });

  it('starts at 0 with BOOK classification', () => {
    expect(store.targetCp).toBe(0);
    expect(store.classification).toBe('BOOK');
    expect(store.history).toEqual([]);
  });

  it('onWsAnalysisUpdate updates target, depth, classification', () => {
    store.onWsAnalysisUpdate(makeUpdate({
      depth: 18,
      classification: 'EXCELLENT',
      lines: [{ multipv: 1, eval_cp: 120, eval_mate: null, depth: 18, pv: ['e2e4'] }]
    }));
    expect(store.targetCp).toBe(120);
    expect(store.depth).toBe(18);
    expect(store.classification).toBe('EXCELLENT');
    expect(store.history).toHaveLength(1);
  });

  it('fromCoach parses "+0.35" eval string', () => {
    store.fromCoach({ best_move: 'e2e4', eval: '+0.35', pv: 'e2e4 e7e5', thinking: [] }, 1, 'GOOD');
    expect(store.targetCp).toBe(35);
    expect(store.bestUci).toBe('e2e4');
  });

  it('history appends per-ply', () => {
    store.onWsAnalysisUpdate(makeUpdate({ depth: 10, classification: 'GOOD', lines: [{ multipv: 1, eval_cp: 30, eval_mate: null, depth: 10, pv: [] }] }));
    store.onWsAnalysisUpdate(makeUpdate({ depth: 12, classification: 'GOOD', lines: [{ multipv: 1, eval_cp: 50, eval_mate: null, depth: 12, pv: [] }] }));
    expect(store.history.length).toBeGreaterThanOrEqual(1);
  });

  it('reset clears state', () => {
    store.fromCoach({ best_move: 'e2e4', eval: '+1.00', pv: '', thinking: [] }, 1, 'BRILLIANT');
    store.reset();
    expect(store.targetCp).toBe(0);
    expect(store.history).toEqual([]);
  });
});
