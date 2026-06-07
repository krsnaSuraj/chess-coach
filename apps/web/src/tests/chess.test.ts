import { describe, it, expect } from 'vitest';
import { fenToLegalMoves, applyMoveToFen, uciToSan, isPromotion } from '../lib/utils/chess';

describe('chess utils', () => {
  it('initial FEN has 20 legal moves', () => {
    const moves = fenToLegalMoves('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
    expect(moves.length).toBe(20);
  });
  it('applyMoveToFen advances position', () => {
    const next = applyMoveToFen(
      'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      'e2e4'
    );
    // After e2e4, pawn is on e4, turn passes to black
    expect(next).toContain('4P3');
    expect(next).toContain(' b ');
  });
  it('uciToSan produces SAN for e2e4', () => {
    expect(
      uciToSan('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', 'e2e4')
    ).toBe('e4');
  });
  it('isPromotion returns true on rank-8 push', () => {
    // white pawn on a7, no piece on a8
    const fen = 'k7/4P3/8/8/8/8/8/4K3 w - - 0 1';
    expect(isPromotion(fen, 'e7', 'e8')).toBe(true);
    // also false on a normal move
    const start = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
    expect(isPromotion(start, 'e2', 'e4')).toBe(false);
  });
});
