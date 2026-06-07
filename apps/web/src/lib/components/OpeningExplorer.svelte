<script lang="ts">
  /**
   * OpeningExplorer.svelte — Lichess opening explorer inline.
   * Shows top master games for the current FEN.
   */
  import { api } from '$lib/api/client';
  import type { GameStore } from '$lib/stores/game.svelte';
  import type { ExplorerResult } from '$lib/types';

  let { game }: { game: GameStore } = $props();

  let result = $state<ExplorerResult | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);

  async function load() {
    const fen = game.displayedFen;
    if (!fen) return;
    loading = true;
    error = null;
    try {
      result = await api.openingExplorer(fen);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void game.displayedFen;
    load();
  });

  function totalGames(line: { white: number; black: number; draws: number }): number {
    return line.white + line.black + line.draws;
  }
  function winRatePct(line: { white: number; black: number; draws: number }): string {
    const t = totalGames(line);
    if (t === 0) return '—';
    return ((line.white / t) * 100).toFixed(0) + '%';
  }
</script>

<div class="opening-explorer" data-testid="opening-explorer">
  <header>
    <h3>Opening Explorer</h3>
    {#if result?.opening}
      <span class="opening-tag">{result.opening.eco} · {result.opening.name}</span>
    {/if}
  </header>

  {#if loading}
    <div class="status">Loading…</div>
  {:else if error}
    <div class="status err">Error: {error}</div>
  {:else if !result || result.moves.length === 0}
    <div class="status">No opening book data for this position.</div>
  {:else}
    <table class="moves">
      <thead>
        <tr>
          <th>Move</th>
          <th>Games</th>
          <th>Avg</th>
          <th>White %</th>
        </tr>
      </thead>
      <tbody>
        {#each result.moves as m}
          <tr>
            <td><strong>{m.san}</strong></td>
            <td>{m.total.toLocaleString()}</td>
            <td>{Math.round(m.average_rating)}</td>
            <td>
              <div class="bar-wrap">
                <div
                  class="bar"
                  style="width: {winRatePct(m)}"
                ></div>
                <span>{winRatePct(m)}</span>
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
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
  header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 8px;
  }
  h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: var(--fg-0);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .opening-tag {
    color: var(--fg-2);
    font-size: 11px;
    font-family: var(--font-mono);
  }
  .status {
    color: var(--fg-2);
    font-style: italic;
    padding: 8px 0;
  }
  .status.err {
    color: var(--error);
  }
  table.moves {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  th, td {
    text-align: left;
    padding: 4px 6px;
    border-bottom: 1px solid var(--bg-2);
  }
  th {
    color: var(--fg-2);
    font-size: 10px;
    text-transform: uppercase;
    font-weight: 600;
  }
  .bar-wrap {
    display: flex;
    align-items: center;
    gap: 6px;
    position: relative;
  }
  .bar {
    height: 8px;
    background: var(--accent);
    border-radius: 2px;
    max-width: 60%;
  }
  .bar-wrap span {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--fg-1);
  }
</style>
