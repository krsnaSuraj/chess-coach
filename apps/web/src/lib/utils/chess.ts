// =============================================================
//  Chess helpers — wraps chess.js for legal-move generation
//  chessground has NO chess logic of its own; we use chess.js.
// =============================================================
import { Chess } from 'chess.js';

export interface SquareName {
  from: string;       // e.g. "e2"
  to: string;         // e.g. "e4"
  promotion?: 'q' | 'r' | 'b' | 'n';
}

export function fenToLegalMoves(fen: string): SquareName[] {
  try {
    const c = new Chess(fen);
    return c.moves({ verbose: true }).map((m) => ({
      from: m.from,
      to: m.to,
      promotion: m.promotion as 'q' | 'r' | 'b' | 'n' | undefined
    }));
  } catch {
    return [];
  }
}

export function isPromotion(fen: string, from: string, to: string): boolean {
  try {
    const c = new Chess(fen);
    const moves = c.moves({ verbose: true });
    const m = moves.find((x) => x.from === from && x.to === to);
    return !!m && m.promotion != null;
  } catch {
    return false;
  }
}

export function applyMoveToFen(fen: string, uci: string): string {
  try {
    const c = new Chess(fen);
    const from = uci.slice(0, 2);
    const to = uci.slice(2, 4);
    const promotion = uci.length === 5 ? (uci[4] as 'q' | 'r' | 'b' | 'n') : undefined;
    const result = c.move({ from, to, promotion });
    return result ? c.fen() : fen;
  } catch {
    return fen;
  }
}

export function uciToSan(fen: string, uci: string): string {
  try {
    const c = new Chess(fen);
    const from = uci.slice(0, 2);
    const to = uci.slice(2, 4);
    const promotion = uci.length === 5 ? (uci[4] as 'q' | 'r' | 'b' | 'n') : undefined;
    const m = c.move({ from, to, promotion });
    return m ? m.san : uci;
  } catch {
    return uci;
  }
}
