<script lang="ts">
  /**
   * OpeningExplorer.svelte — show the opening tag from the FEN if
   * chess.js can identify it, otherwise show "no book data".
   * Backend has no /api/opening_explorer; this is a graceful fallback.
   */
  import { Chess } from 'chess.js';
  import type { GameStore } from '$lib/stores/game.svelte';

  let { game }: { game: GameStore } = $props();

  let openingTag = $state<string | null>(null);
  let error = $state<string | null>(null);

  // Tiny static opening hint derived from FEN (move counts and side-to-move
  // are not a substitute for Lichess's DB but give the user something to look at).
  $effect(() => {
    const fen = game.displayedFen;
    if (!fen) { openingTag = null; return; }
    try {
      const c = new Chess(fen);
      const halfMoves = Math.floor(c.history().length / 2) + 1;
      const turn = c.turn() === 'w' ? 'White' : 'Black';
      openingTag = `Move ${halfMoves} · ${turn} to play`;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      openingTag = null;
    }
  });
</script>

<div class="opening-explorer" data-testid="opening-explorer">
  <header>
    <h3>Opening Explorer</h3>
  </header>

  {#if error}
    <div class="status err">Error: {error}</div>
  {:else if openingTag}
    <div class="status">
      <strong>{openingTag}</strong>
      <p class="hint">Lichess opening database is not bundled in this build. Use the eval bar to study the position.</p>
    </div>
  {:else}
    <div class="status">Make a move to see position metadata.</div>
  {/if}
</div>

<style>
  .opening-explorer {
    background: var(--bg-1);
    border-radius: 6px;
    padding: 10px 12px;
    height: 100%;
    overflow-y: auto;
  }
  header { margin-bottom: 8px; }
  h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: var(--fg-0);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .status {
    color: var(--fg-1);
    padding: 8px 0;
    font-size: 12px;
  }
  .status strong { color: var(--fg-0); font-family: var(--font-mono); }
  .hint { color: var(--fg-2); font-style: italic; font-size: 11px; margin: 4px 0 0 0; }
  .status.err { color: var(--error); }
</style>
