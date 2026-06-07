import { describe, it, expect } from 'vitest';
import { GameStore } from '../lib/stores/game.svelte';
import type { HistoryEntry } from '../lib/types';

function entry(ply: number, san: string, uci: string, cls: HistoryEntry['classification']): HistoryEntry {
  return {
    ply, san, uci,
    fen_before: 'a', fen_after: 'b',
    eval_cp: null, classification: cls, cpl: null,
    played_by: 'human'
  };
}

describe('GameStore', () => {
  it('initial state is null', () => {
    const g = new GameStore();
    expect(g.state).toBeNull();
    expect(g.history).toEqual([]);
    expect(g.cursor).toBe(-1);
    expect(g.isLive).toBe(true);
  });

  it('orientation default white', () => {
    const g = new GameStore();
    expect(g.orientation).toBe('white');
  });

  it('stepBack/stepForward navigate cursor within bounds', () => {
    const g = new GameStore();
    g.history = [entry(1, 'e4', 'e2e4', 'GOOD'), entry(2, 'c5', 'c7c5', 'GOOD')];
    g.cursor = g.history.length - 1;
    g.stepBack();
    expect(g.cursor).toBe(0);
    g.stepBack();
    expect(g.cursor).toBe(-1);
    g.stepBack();
    expect(g.cursor).toBe(-1);
    g.stepForward();
    expect(g.cursor).toBe(0);
    g.stepForward();
    expect(g.cursor).toBe(1);
  });

  it('goToStart/End jump to bounds', () => {
    const g = new GameStore();
    g.history = [entry(1, 'e4', 'e2e4', 'GOOD'), entry(2, 'c5', 'c7c5', 'GOOD')];
    g.goToStart();
    expect(g.cursor).toBe(-1);
    g.goToEnd();
    expect(g.cursor).toBe(1);
  });

  it('displayedFen reflects cursor (historical)', () => {
    const g = new GameStore();
    g.state = { ok: true, mode: 'coach', fen: 'live-fen', move: null, coach: null, error: null };
    g.history = [
      entry(1, 'e4', 'e2e4', 'GOOD'),
      entry(2, 'c5', 'c7c5', 'GOOD')
    ];
    g.history[0]!.fen_before = 'live-fen';
    g.history[0]!.fen_after = 'after-e4';
    g.history[1]!.fen_before = 'after-e4';
    g.history[1]!.fen_after = 'after-c5';
    g.cursor = -1;
    expect(g.displayedFen).toBe('live-fen');
    g.cursor = 0;
    expect(g.displayedFen).toBe('after-e4');
    g.cursor = 1;
    expect(g.displayedFen).toBe('after-c5');
  });

  it('classificationAt returns GOOD for unknown ply', () => {
    const g = new GameStore();
    g.history = [entry(1, 'e4', 'e2e4', 'EXCELLENT')];
    expect(g.classificationAt(0)).toBe('EXCELLENT');
    expect(g.classificationAt(5)).toBe('GOOD');
  });

  it('latestEvalCp parses coach eval string', () => {
    const g = new GameStore();
    g.state = {
      ok: true, mode: 'coach', fen: '', move: null, error: null,
      coach: { best_move: 'e2e4', eval: '+1.50', pv: '', thinking: [] }
    };
    expect(g.latestEvalCp).toBe(150);
  });
});
