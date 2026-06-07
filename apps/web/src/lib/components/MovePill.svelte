<script lang="ts">
  /**
   * MovePill.svelte — Lichess-style move classification pill.
   * 11 MoveClass values mapped to distinct colors.
   */
  import type { MoveClass } from '$lib/types';

  let {
    moveNumber,
    san,
    cls,
    isCurrent = false,
    onclick
  }: {
    moveNumber: number;
    san: string;
    cls: MoveClass;
    isCurrent?: boolean;
    onclick?: () => void;
  } = $props();

  const COLOR: Record<MoveClass, string> = {
    BOOK: 'var(--book)',
    BRILLIANT: 'var(--brilliant)',
    GREAT: 'var(--great)',
    BEST: 'var(--best)',
    EXCELLENT: 'var(--excellent)',
    GOOD: 'var(--good)',
    INACCURACY: 'var(--inaccuracy)',
    MISTAKE: 'var(--mistake)',
    BLUNDER: 'var(--blunder)',
    MISS: 'var(--miss)',
    FORCED: 'var(--forced)'
  };

  let symbol = $derived.by(() => {
    switch (cls) {
      case 'BRILLIANT':
        return '!!';
      case 'GREAT':
        return '!';
      case 'BLUNDER':
        return '??';
      case 'MISTAKE':
        return '?';
      case 'INACCURACY':
        return '?!';
      case 'MISS':
        return '✕';
      case 'FORCED':
        return '□';
      default:
        return '';
    }
  });
</script>

<button
  class="move-pill"
  class:current={isCurrent}
  style="--pill-color: {COLOR[cls]}"
  onclick={onclick}
  data-cls={cls}
  aria-label="Move {moveNumber}: {san} ({cls})"
>
  <span class="num">{moveNumber}.</span>
  <span class="san">{san}</span>
  {#if symbol}
    <span class="sym">{symbol}</span>
  {/if}
</button>

<style>
  .move-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 7px;
    border-radius: 4px;
    border: 1px solid var(--pill-color);
    background: color-mix(in srgb, var(--pill-color) 15%, transparent);
    color: var(--fg-0);
    cursor: pointer;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.3;
    transition: background 120ms, transform 80ms;
  }
  .move-pill:hover {
    background: color-mix(in srgb, var(--pill-color) 30%, transparent);
  }
  .move-pill.current {
    outline: 2px solid var(--accent-2);
    outline-offset: 1px;
    font-weight: 700;
  }
  .num {
    color: var(--fg-2);
    font-size: 10px;
    font-weight: 600;
  }
  .san {
    font-weight: 600;
  }
  .sym {
    color: var(--pill-color);
    font-weight: 700;
    margin-left: 1px;
  }
</style>
