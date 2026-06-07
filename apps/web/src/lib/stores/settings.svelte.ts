// =============================================================
//  Settings store — theme, sound, engine, etc.
//  Persisted to localStorage on every change.
//  Engine list is hardcoded (no /api/engines endpoint).
// =============================================================
import { api, HARDCODED_ENGINES } from '$lib/api/client';
import type { EngineInfo, HumanizerConfig } from '$lib/types';

const STORAGE_KEY = 'chess_coach_settings_v3';

export type ThemeName =
  | 'midnight'
  | 'forest'
  | 'sunset'
  | 'marble'
  | 'lichess'
  | 'blue_glass'
  | 'cyber_neon'
  | 'sepia'
  | 'paper'
  | 'high_contrast';

export const THEMES: ThemeName[] = [
  'midnight', 'forest', 'sunset', 'marble', 'lichess',
  'blue_glass', 'cyber_neon', 'sepia', 'paper', 'high_contrast'
];

export interface PersistedSettings {
  theme: ThemeName;
  soundEnabled: boolean;
  soundVolume: number;
  showCoordinates: boolean;
  showLegalMoves: 'dots' | 'arrows' | 'none';
  showArrows: boolean;
  showEvalBar: boolean;
  showWinProb: boolean;
  showAccuracyGraph: boolean;
  animationSpeed: number;
  engine: string;
  personality: 'aggressive' | 'positional' | 'tactical' | 'defensive' | 'balanced';
  targetElo: number;
  humanMode: boolean;
}

export const DEFAULTS: PersistedSettings = {
  theme: 'midnight',
  soundEnabled: true,
  soundVolume: 0.7,
  showCoordinates: true,
  showLegalMoves: 'dots',
  showArrows: true,
  showEvalBar: true,
  showWinProb: true,
  showAccuracyGraph: true,
  animationSpeed: 1.0,
  engine: 'stockfish',
  personality: 'balanced',
  targetElo: 1500,
  humanMode: false
};

function loadFromStorage(): PersistedSettings {
  if (typeof localStorage === 'undefined') return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function saveToStorage(s: PersistedSettings) {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* quota exceeded — ignore */
  }
}

export class SettingsStore {
  data = $state<PersistedSettings>(DEFAULTS);
  engines = $state<EngineInfo[]>(HARDCODED_ENGINES);
  humanizer = $state<HumanizerConfig | null>(null);

  constructor() {
    this.data = loadFromStorage();
  }

  async load() {
    try {
      const cfg = await api.humanizerConfig();
      this.humanizer = cfg;
      // Sync our local settings with the server's humanizer target
      if (typeof cfg.target_elo === 'number') {
        this.data = { ...this.data, targetElo: cfg.target_elo };
      }
      if (typeof cfg.personality === 'string') {
        this.data = { ...this.data, personality: cfg.personality as PersistedSettings['personality'] };
      }
    } catch {
      /* offline — keep local */
    }
  }

  update<K extends keyof PersistedSettings>(key: K, value: PersistedSettings[K]) {
    this.data = { ...this.data, [key]: value };
    saveToStorage(this.data);
    if (key === 'theme' && typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', String(value));
    }
  }

  applyTheme() {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', this.data.theme);
    }
  }

  /**
   * Switch active engine (local-only).
   * Backend has no per-engine "set" endpoint — the engine choice is
   * stored locally and the backend serves the configured default.
   */
  async switchEngine(name: string) {
    this.update('engine', name);
  }
}
