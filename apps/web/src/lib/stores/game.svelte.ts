// =============================================================
//  Game store — game state, move history, navigation
// =============================================================
import type { GameState, HistoryEntry, MoveClass } from '$lib/types';
import { api } from '$lib/api/client';

export class GameStore {
  state = $state<GameState | null>(null);
  history = $state<HistoryEntry[]>([]);
  cursor = $state<number>(-1); // -1 = live position
  orientation = $state<'white' | 'black'>('white');
  error = $state<string | null>(null);
  loading = $state(false);
  isLive = $derived(this.cursor === -1);

  // fen for board at current cursor (live or historical)
  displayedFen = $derived.by(() => {
    if (this.cursor < 0 || !this.state) return this.state?.fen ?? '';
    const h = this.history[this.cursor];
    return h?.fen_after ?? this.state.fen;
  });

  // index 0-based for move list
  currentPly = $derived(this.cursor < 0 ? (this.state?.ply ?? 0) : this.cursor);

  async refresh() {
    this.loading = true;
    this.error = null;
    try {
      const [gs, hist] = await Promise.all([api.gameState(), api.history()]);
      this.state = gs;
      this.history = hist.history;
      if (this.cursor === -1) this.cursor = this.history.length - 1;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    } finally {
      this.loading = false;
    }
  }

  async newGame() {
    await api.newGame();
    this.cursor = -1;
    await this.refresh();
  }

  async playMove(uci: string) {
    try {
      const gs = await api.move(uci);
      this.state = gs;
      this.history = (await api.history()).history;
      this.cursor = this.history.length - 1;
    } catch (e) {
      this.error = e instanceof Error ? e.message : String(e);
    }
  }

  async undo() {
    await api.undo();
    await this.refresh();
  }

  async redo() {
    await api.redo();
    await this.refresh();
  }

  async loadFen(fen: string) {
    await api.loadFen(fen);
    this.cursor = -1;
    await this.refresh();
  }

  async loadPgn(pgn: string) {
    await api.loadPgn(pgn);
    this.cursor = -1;
    await this.refresh();
  }

  async exportPgn() {
    return await api.exportPgn();
  }

  // Navigation — used by arrow keys
  goToStart() {
    this.cursor = -1;
  }
  goToEnd() {
    this.cursor = this.history.length - 1;
  }
  stepBack() {
    if (this.cursor > -1) this.cursor -= 1;
  }
  stepForward() {
    if (this.cursor < this.history.length - 1) this.cursor += 1;
  }

  // Classification helpers
  classificationAt(ply: number): MoveClass {
    return this.history[ply]?.classification ?? 'GOOD';
  }
}
