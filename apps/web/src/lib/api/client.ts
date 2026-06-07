// =============================================================
//  Chess Coach v3.0.0 SOTA — REST API client
//  Single source of truth, mapped to real backend endpoints
//  in src/chess_coach/server.py. Every URL here is verified
//  to exist; nothing is fabricated.
// =============================================================
import type {
  UnifiedResponse,
  CoachAccuracy,
  CriticalMoments,
  CoachPlan,
  BlunderReport,
  CoachPatterns,
  HumanizerConfig,
  CapsLast,
  MotifsPosition,
  RiskGame,
  EloEstimate,
  PuzzlesResponse,
  PuzzleDetail,
  EngineMatchStart,
  PersonalitiesResponse,
  EngineInfo
} from '$lib/types';

const BASE = '';

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'content-type': 'application/json' },
    ...init
  });
  if (!r.ok) {
    const text = await r.text().catch(() => '');
    throw new Error(`API ${r.status} ${path}: ${text || r.statusText}`);
  }
  return (await r.json()) as T;
}

export const api = {
  // Health
  health: () => json<{ status: string; engine_running: boolean }>('/api/health'),

  // Game flow — real endpoints
  gameState: () => json<UnifiedResponse>('/api/game_state'),
  startGame: (humanIsWhite: boolean) =>
    json<UnifiedResponse>('/api/start_game', {
      method: 'POST',
      body: JSON.stringify({ human_is_white: humanIsWhite })
    }),
  humanMove: (moveUci: string, promotion?: string) =>
    json<UnifiedResponse>('/api/human_move', {
      method: 'POST',
      body: JSON.stringify({ move_uci: moveUci, promotion: promotion ?? null })
    }),
  undo: () => json<UnifiedResponse>('/api/undo', { method: 'POST' }),
  redo: () => json<UnifiedResponse>('/api/redo', { method: 'POST' }),

  // Coach
  coachAccuracy: (evalHistory: { before: number; after: number; side: string }[]) =>
    json<CoachAccuracy>('/api/coach/accuracy', {
      method: 'POST',
      body: JSON.stringify({ eval_history: evalHistory })
    }),
  coachCriticalMoments: (minSwing = 100) =>
    json<CriticalMoments>(`/api/coach/critical_moments?min_swing=${minSwing}`),
  coachPlan: (fen: string, pv: string[]) =>
    json<CoachPlan>('/api/coach/plan', {
      method: 'POST',
      body: JSON.stringify({ fen, pv })
    }),
  coachBlunder: (req: {
    fen_before: string;
    move_uci: string;
    eval_before_cp: number;
    eval_after_cp: number;
    best_move_uci?: string;
    best_eval_cp?: number;
    time_remaining_s?: number;
  }) => json<BlunderReport>('/api/coach/blunder', {
    method: 'POST',
    body: JSON.stringify(req)
  }),
  coachPatterns: () => json<CoachPatterns>('/api/coach/patterns'),

  // Puzzles
  puzzles: (theme?: string) =>
    json<PuzzlesResponse>(theme ? `/api/puzzles?theme=${encodeURIComponent(theme)}` : '/api/puzzles'),
  randomPuzzle: (theme?: string) =>
    json<PuzzleDetail>(theme ? `/api/puzzles/random?theme=${encodeURIComponent(theme)}` : '/api/puzzles/random'),
  puzzleById: (id: string) =>
    json<PuzzleDetail>(`/api/puzzles/${encodeURIComponent(id)}`),

  // Engine match
  engineMatchStart: (req: { personality: string; target_elo: number; color: string }) =>
    json<EngineMatchStart>('/api/engine_match/start', {
      method: 'POST',
      body: JSON.stringify(req)
    }),
  engineMatchPersonalities: () => json<PersonalitiesResponse>('/api/engine_match/personalities'),

  // PGN export — body shape matches PGNExportRequest in server.py
  exportPgn: (req: {
    moves: Array<{
      ply: number;
      san: string;
      fen_after?: string;
      eval_cp?: number;
      cpl?: number;
      accuracy_pct?: number;
      classification?: string;
      commentary?: string;
    }>;
    white?: string;
    black?: string;
    event?: string;
    eco?: string;
    opening?: string;
    time_control?: string;
    result?: string;
    overall_accuracy?: number;
    critical_moments_count?: number;
    rating_estimate?: number;
  }) => json<{ pgn: string; size: number }>('/api/export/pgn', {
    method: 'POST',
    body: JSON.stringify(req)
  }),

  // Humanizer
  humanizerConfig: () => json<HumanizerConfig>('/api/humanizer/config'),
  saveHumanizerConfig: (cfg: Partial<HumanizerConfig>) =>
    json<HumanizerConfig>('/api/humanizer/config', {
      method: 'POST',
      body: JSON.stringify(cfg)
    }),

  // CAPS / motifs / risk / ELO
  capsLast: () => json<CapsLast>('/api/caps/last'),
  motifsPosition: () => json<MotifsPosition>('/api/motifs/position'),
  riskGame: () => json<RiskGame>('/api/risk/game'),
  eloEstimate: () => json<EloEstimate>('/api/elo/estimate')
};

/** Hardcoded engine roster — no /api/engines endpoint exists. */
export const HARDCODED_ENGINES: EngineInfo[] = [
  { id: 'berserk',    name: 'Berserk',     elo: 3550, style: 'Tactical',   description: 'Blitz monster, very aggressive' },
  { id: 'caissa',     name: 'Caissa',      elo: 3500, style: 'Balanced',   description: 'Balanced strategic engine' },
  { id: 'crystal',    name: 'Crystal',     elo: 3490, style: 'Positional', description: 'Crystal-clear positional play' },
  { id: 'patricia',   name: 'Patricia',    elo: 3520, style: 'Endgame',    description: 'Endgame specialist' },
  { id: 'shashchess', name: 'ShashChess',  elo: 3540, style: 'NNUE',       description: 'Modern NNUE architecture' },
  { id: 'stockfish',  name: 'Stockfish 18',elo: 3500, style: 'Reference',  description: 'Gold standard reference' },
  { id: 'maia2',      name: 'Maia-2',      elo: 2400, style: 'Human-like', description: 'Human-like play modeling' }
];
