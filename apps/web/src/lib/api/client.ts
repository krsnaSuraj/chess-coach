// =============================================================
//  Chess Coach v3.0.0 SOTA — REST API client
//  Single source of truth for backend calls.
// =============================================================
import type {
  GameState,
  ExplorerResult,
  TablebaseResult,
  HistoryEntry,
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
  gameState: () => json<GameState>('/api/game_state'),

  move: (uci: string) =>
    json<GameState>('/api/move', { method: 'POST', body: JSON.stringify({ move: uci }) }),

  undo: () => json<GameState>('/api/undo', { method: 'POST' }),
  redo: () => json<GameState>('/api/redo', { method: 'POST' }),

  newGame: () => json<GameState>('/api/new_game', { method: 'POST' }),
  loadFen: (fen: string) =>
    json<GameState>('/api/load_fen', { method: 'POST', body: JSON.stringify({ fen }) }),
  loadOpening: (eco: string) =>
    json<GameState>('/api/load_opening', { method: 'POST', body: JSON.stringify({ eco }) }),

  loadPgn: (pgn: string) =>
    json<GameState>('/api/load_pgn', { method: 'POST', body: JSON.stringify({ pgn }) }),
  exportPgn: () => json<{ pgn: string }>('/api/export_pgn', { method: 'POST' }),

  settings: () => json<Record<string, unknown>>('/api/settings'),
  saveSettings: (s: Record<string, unknown>) =>
    json<Record<string, unknown>>('/api/settings', {
      method: 'POST',
      body: JSON.stringify(s)
    }),

  analysis: () => json<{ running: boolean }>('/api/analysis'),
  startAnalysis: () => json<{ running: true }>('/api/analysis/start', { method: 'POST' }),
  stopAnalysis: () => json<{ running: false }>('/api/analysis/stop', { method: 'POST' }),

  openingExplorer: (fen: string) =>
    json<ExplorerResult>(`/api/opening_explorer?fen=${encodeURIComponent(fen)}`),

  tablebase: (fen: string) =>
    json<TablebaseResult>(`/api/tablebase?fen=${encodeURIComponent(fen)}`),

  cloudEval: (fen: string) =>
    json<{ eval_cp: number; depth: number; pv: string[] }>(
      `/api/cloud_eval?fen=${encodeURIComponent(fen)}`
    ),

  history: () => json<{ history: HistoryEntry[] }>('/api/history'),

  engines: () => json<{ engines: EngineInfo[] }>('/api/engines'),
  switchEngine: (name: string) =>
    json<{ current: string }>('/api/engine', {
      method: 'POST',
      body: JSON.stringify({ engine: name })
    }),

  sound: (name: string) =>
    fetch(`${BASE}/api/sound`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ sound: name })
    })
};
