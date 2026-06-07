// =============================================================
//  Chess Coach v3.0.0 SOTA — shared types
//  Mirrors the real Python backend contracts exactly.
//  Backend response shape (src/chess_coach/server.py):
//    UnifiedResponse { ok, mode, fen, move, coach, error }
//  Backend WS envelope (src/chess_coach/ws/protocol.py):
//    WsMessage        { type, v, ts, ...data }
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

/** Hardcoded engine list (frontend-side, no /api/engines endpoint). */
export interface EngineInfo {
  id: string;
  name: string;
  elo: number;
  style: string;
  description: string;
}

/** Single PV line from engine analysis. */
export interface PvLine {
  multipv: number;
  eval_cp: number;
  eval_mate: number | null;
  depth: number;
  pv: string[];
  san?: string[];
}

/** Coach evaluation block returned by /api/game_state and /api/human_move. */
export interface CoachEval {
  best_move: string | null;
  eval: string;            // e.g. "+0.35" or "-M3"
  pv: string;              // space-separated UCI moves
  thinking: string[];
}

/** Real backend response shape — the ONLY thing we get back. */
export interface UnifiedResponse {
  ok: boolean;
  mode: 'idle' | 'coach' | 'review' | 'puzzle';
  fen: string;
  move: string | null;     // last SAN move played (from the engine's reply)
  coach: CoachEval | null;
  error: string | null;
}

/** Per-move history entry — tracked client-side (no /api/history endpoint). */
export interface HistoryEntry {
  ply: number;             // 1-based, matches the actual game
  san: string;             // SAN of the move
  uci: string;             // UCI of the move
  fen_before: string;      // FEN before this move
  fen_after: string;       // FEN after this move
  eval_cp: number | null;  // eval BEFORE the move (relative to side-to-move)
  classification: MoveClass;
  cpl: number | null;      // centipawn loss
  played_by: 'human' | 'engine';
  comment?: string;
  nag?: number;
}

/** WebSocket envelope as broadcast by the Python backend. */
export interface WsEnvelope {
  type: string;            // "analysis_update" | "game_state" | "toast" | "sound" | "eval" | "puzzle" | "threat" | "hello" | "ping" | "pong"
  v: number;               // protocol version
  ts: number;              // millisecond timestamp
}

/** Analysis-update payload (subset of WsEnvelope.data when type === 'analysis_update'). */
export interface WsAnalysisUpdate extends WsEnvelope {
  type: 'analysis_update';
  fen: string;
  best_move: string;
  classification: string;
  accuracy: number;
  depth: number;
  finished: boolean;
  lines: PvLine[];
}

/** Chessboard square key, e.g. "e4". Matches chessground's Key type. */
export type SquareKey =
  `${'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h'}${1 | 2 | 3 | 4 | 5 | 6 | 7 | 8}`;

/** Arrow shape for chessground (best move, alt move, etc.) */
export interface ArrowShape {
  orig: SquareKey;
  dest: SquareKey;
  brush: 'green' | 'red' | 'blue' | 'yellow';
}

// ---- Coach endpoints ----
export interface CoachAccuracy {
  accuracy_pct: number;
  rating_estimate: number;
  white_acpl: number;
  black_acpl: number;
}
export interface CriticalMoment {
  fen: string;
  move_played: string;
  side_just_moved: string;
  prev_eval_cp: number;
  eval_cp: number;
  swing: number;
}
export interface CriticalMoments {
  summary: { total: number; critical: number; brilliant: number; blunders: number };
  moments: CriticalMoment[];
}
export interface CoachPlan {
  plan: string;
  ideas: string[];
  threats: string[];
}
export interface BlunderReport {
  why: string;
  better_moves: Array<{ uci: string; san: string; eval_cp: number }>;
  eval_loss: number;
}
export interface CoachPatterns {
  fen: string;
  patterns: Array<{ name: string; occurrences: number; example_fen: string }>;
}

// ---- Puzzles ----
export interface PuzzlesResponse {
  count: number;
  puzzles: Array<{ id: string; themes: string[]; rating: number }>;
}
export interface PuzzleDetail {
  id: string;
  fen: string;
  moves: string[];
  themes: string[];
  rating: number;
}

// ---- Engine match ----
export interface EngineMatchStart {
  ok: boolean;
  config: {
    personality: string;
    personality_name: string;
    target_elo: number;
    color: string;
  };
}
export interface PersonalitiesResponse {
  personalities: Array<{ id: string; name: string; icon: string; description: string }>;
}

// ---- Humanizer ----
export interface HumanizerConfig {
  personality: string;
  target_elo: number;
  simulated_think_time: boolean;
  enable_maia: boolean;
}

// ---- CAPS / motifs / risk / ELO ----
export interface CapsLast {
  move: string;
  classification: string;
  label: string;
  color: string;
  expected_points_lost: number;
  phase: string;
}
export interface MotifsPosition {
  fen: string;
  motifs: Array<{ type: string; description: string; squares: string[] }>;
}
export interface RiskGame {
  score: number;
  level: string;
  label: string;
  recommendation: string;
  contributions: Record<string, number>;
}
export interface EloEstimate {
  mean_elo: number;
  ci_low: number;
  ci_high: number;
  samples: number;
}
