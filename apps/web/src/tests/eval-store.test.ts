import { describe, it, expect, beforeEach } from 'vitest';
import { EvalStore } from '../lib/stores/eval.svelte';

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

  it('onWs updates target, depth, multipv, classification', () => {
    store.onWs(
      {
        type: 'eval',
        eval_cp: 120,
        eval_mate: null,
        depth: 18,
        multipv: [{ multipv: 1, eval_cp: 120, eval_mate: null, depth: 18, pv: ['e2e4'] }],
        classification: 'EXCELLENT'
      },
      1
    );
    expect(store.targetCp).toBe(120);
    expect(store.depth).toBe(18);
    expect(store.classification).toBe('EXCELLENT');
    expect(store.history).toHaveLength(1);
  });

  it('history appends per-ply', () => {
    store.onWs({ type: 'eval', eval_cp: 30, depth: 10, classification: 'GOOD' }, 1);
    store.onWs({ type: 'eval', eval_cp: 50, depth: 12, classification: 'GOOD' }, 2);
    expect(store.history).toHaveLength(2);
  });

  it('history does not duplicate on same ply', () => {
    store.onWs({ type: 'eval', eval_cp: 30, depth: 10, classification: 'GOOD' }, 1);
    store.onWs({ type: 'eval', eval_cp: 35, depth: 11, classification: 'GOOD' }, 1);
    expect(store.history).toHaveLength(1);
    expect(store.history[0]?.cp).toBe(35);
  });

  it('reset clears state', () => {
    store.onWs({ type: 'eval', eval_cp: 100, depth: 10, classification: 'BRILLIANT' }, 1);
    store.reset();
    expect(store.targetCp).toBe(0);
    expect(store.history).toEqual([]);
  });
});
