<script lang="ts">
  /**
   * MoveList.svelte — vertical list of MovePills, paired by move number.
   * Wires to GameStore for state, exposes navigation callbacks.
   * Arrow keys are handled at +page.svelte (parent) for global access.
   */
  import MovePill from './MovePill.svelte';
  import type { GameStore } from '$lib/stores/game.svelte';
  import type { HistoryEntry } from '$lib/types';

  let { game }: { game: GameStore } = $props();

  // Group history into rows: each row = (moveNumber, white, black)
  let rows = $derived.by(() => {
    const h: HistoryEntry[] = game.history;
    const out: Array<{ n: number; w?: HistoryEntry; b?: HistoryEntry }> = [];
    for (const e of h) {
      const idx = e.ply - 1; // 0-based index in history array
      const moveNumber = Math.floor(idx / 2) + 1;
      const isWhite = idx % 2 === 0;
      let row = out[moveNumber - 1];
      if (!row) {
        row = { n: moveNumber };
        out[moveNumber - 1] = row;
      }
      if (isWhite) row.w = e;
      else row.b = e;
    }
    return out;
  });

  function clickPly(ply: number) {
    // clicking a pill sets cursor to that ply
    if (game.cursor === ply) {
      // toggle back to live
      game.cursor = -1;
    } else {
      game.cursor = ply;
    }
  }

  let currentPly = $derived(game.cursor);
</script>

<div class="move-list" data-testid="move-list">
  {#if rows.length === 0}
    <div class="empty">No moves yet. Make your first move.</div>
  {/if}
  {#each rows as row (row.n)}
    <div class="row">
      <span class="num">{row.n}.</span>
      {#if row.w}
        <MovePill
          moveNumber={row.n}
          san={row.w.san}
          cls={row.w.classification}
          isCurrent={currentPly === row.w.ply - 1}
          onclick={() => clickPly(row.w!.ply - 1)}
        />
      {/if}
      {#if row.b}
        <MovePill
          moveNumber={row.n}
          san={row.b.san}
          cls={row.b.classification}
          isCurrent={currentPly === row.b.ply - 1}
          onclick={() => clickPly(row.b!.ply - 1)}
        />
      {/if}
    </div>
  {/each}
</div>

<style>
  .move-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 8px;
    overflow-y: auto;
    flex: 1 1 0;
    min-height: 0;
    background: var(--bg-1);
    border-radius: 6px;
  }
  .empty {
    color: var(--fg-2);
    font-style: italic;
    text-align: center;
    padding: 16px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
  }
  .num {
    color: var(--fg-2);
    font-size: 11px;
    font-family: var(--font-mono);
    min-width: 24px;
    text-align: right;
  }
</style>
