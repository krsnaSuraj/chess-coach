// =============================================================
//  Chess Coach v3.0.0 SOTA — shared types
//  Mirrors the Python backend's data contracts.
// =============================================================

/** 11-class move classification, matches classify_v2.MoveClass */
export type MoveClass =
  | 'BOOK'
  | 'BRILLIANT'
  | 'GREAT'
  | 'BEST'
  | 'EXCELLENT'
  | 'GOOD'
  | 'INACCURACY'
  | 'MISTAKE'
  | 'BLUNDER'
  | 'MISS'
  | 'FORCED';

/** UCI engine info, matches engines/base.py EngineInfo */
export interface EngineInfo {
  name: string;
  version: string;
  author: string;
  elo_ceiling: number;
  elo_floor: number;
  type: 'classic' | 'neural' | 'hybrid';
  requires: string;
  url: string;
  option_presets: Record<string, unknown>;
}

/** Principal variation line from MultiPV */
export interface PvLine {
  multipv: number;
  eval_cp: number;          // centipawns
  eval_mate: number | null; // mate-in-N if forced
  depth: number;
  pv: string[];             // UCI moves
  san?: string[];           // SAN moves
}

/** Full game state from /api/game_state */
export interface GameState {
  fen: string;
  turn: 'white' | 'black';
  is_check: boolean;
  is_checkmate: boolean;
  is_stalemate: boolean;
  is_game_over: boolean;
  move_history: string[];          // SAN moves
  legal_moves: string[];           // UCI moves
  ply: number;
  result: string | null;
  opening: {
    eco: string;
    name: string;
  } | null;
  classification: MoveClass[];
  accuracy: {
    white: number;
    black: number;
  } | null;
}

/** WebSocket eval message */
export interface WsEvalMessage {
  type: 'eval' | 'fen' | 'pong' | 'error';
  fen?: string;
  eval_cp?: number;
  eval_mate?: number | null;
  depth?: number;
  multipv?: PvLine[];
  pv?: string[];
  classification?: MoveClass;
  best_move_san?: string;
  best_move_uci?: string;
  nodes?: number;
  nps?: number;
  time_ms?: number;
  message?: string;
}

/** Opening explorer result from /api/opening_explorer */
export interface ExplorerLine {
  uci: string;
  san: string;
  white: number;
  black: number;
  draws: number;
  total: number;
  average_rating: number;
}

export interface ExplorerResult {
  fen: string;
  moves: ExplorerLine[];
  top_games: Array<{
    id: string;
    white: { name: string; rating: number };
    black: { name: string; rating: number };
    winner: 'white' | 'black' | 'draw';
    speed: string;
    date: string;
  }>;
  opening?: { eco: string; name: string };
}

/** Tablebase result from /api/tablebase */
export interface TablebaseResult {
  fen: string;
  dtm: number | null;
  dtz: number | null;
  category: 'win' | 'loss' | 'draw' | 'unknown';
  best_move: string | null;
  best_move_san: string | null;
}

/** Per-move history entry for move list display */
export interface HistoryEntry {
  ply: number;
  san: string;
  uci: string;
  fen_before: string;
  fen_after: string;
  eval_cp: number | null;
  classification: MoveClass;
  cpl: number | null;
  comment?: string;
  nag?: number;
}

/** Chessboard square key, e.g. "e4". Matches chessground's Key type. */
export type SquareKey = `${'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h'}${1 | 2 | 3 | 4 | 5 | 6 | 7 | 8}`;

/** Arrow shape for chessground (best move, alt move, etc.) */
export interface ArrowShape {
  orig: SquareKey;
  dest: SquareKey;
  brush: 'green' | 'red' | 'blue' | 'yellow';
}
