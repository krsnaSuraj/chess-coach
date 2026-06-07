<script lang="ts">
  /**
   * PromotionDialog.svelte — overlay for choosing promotion piece.
   * Shows when a pawn reaches the last rank.
   */
  import type { PieceSymbol } from 'chess.js';

  let {
    color = 'white',
    onSelect,
    onCancel
  }: {
    color?: 'white' | 'black';
    onSelect: (piece: 'q' | 'r' | 'b' | 'n') => void;
    onCancel: () => void;
  } = $props();

  const PIECES: Array<{ key: 'q' | 'r' | 'b' | 'n'; symbol: string; label: string }> = [
    { key: 'q', symbol: '♕', label: 'Queen' },
    { key: 'r', symbol: '♖', label: 'Rook' },
    { key: 'b', symbol: '♗', label: 'Bishop' },
    { key: 'n', symbol: '♘', label: 'Knight' }
  ];

  function pick(p: 'q' | 'r' | 'b' | 'n') {
    onSelect(p);
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Escape') onCancel();
    if (e.key === 'q' || e.key === 'Q') pick('q');
    if (e.key === 'r' || e.key === 'R') pick('r');
    if (e.key === 'b' || e.key === 'B') pick('b');
    if (e.key === 'n' || e.key === 'N') pick('n');
  }
</script>

<svelte:window onkeydown={onKey} />

<div class="overlay" role="dialog" aria-modal="true" aria-label="Choose promotion piece">
  <div class="dialog" data-color={color}>
    <h3>Promote pawn to…</h3>
    <div class="pieces">
      {#each PIECES as p (p.key)}
        <button
          class="piece-btn"
          onclick={() => pick(p.key)}
          aria-label={p.label}
        >
          <span class="glyph">{p.symbol}</span>
          <span class="lbl">{p.label}</span>
        </button>
      {/each}
    </div>
    <button class="cancel" onclick={onCancel}>Cancel (Esc)</button>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    backdrop-filter: blur(2px);
  }
  .dialog {
    background: var(--bg-1);
    border: 1px solid var(--bg-3);
    border-radius: 10px;
    padding: 20px 24px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    min-width: 320px;
  }
  h3 {
    margin: 0 0 14px 0;
    font-size: 14px;
    text-align: center;
    color: var(--fg-0);
  }
  .pieces {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }
  .piece-btn {
    background: var(--bg-2);
    border: 1px solid var(--bg-3);
    border-radius: 6px;
    padding: 12px 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    transition: background 100ms, transform 80ms;
  }
  .piece-btn:hover {
    background: var(--bg-3);
    transform: translateY(-2px);
  }
  .glyph {
    font-size: 38px;
    line-height: 1;
  }
  .dialog[data-color='white'] .glyph { color: #f5f5f5; text-shadow: 0 0 4px #000; }
  .dialog[data-color='black'] .glyph { color: #2a2a2a; text-shadow: 0 0 4px #fff; }
  .lbl {
    font-size: 10px;
    color: var(--fg-2);
  }
  .cancel {
    margin-top: 14px;
    width: 100%;
    padding: 6px;
    background: transparent;
    border: 1px solid var(--bg-3);
    border-radius: 4px;
    color: var(--fg-2);
    cursor: pointer;
    font-size: 11px;
  }
  .cancel:hover {
    background: var(--bg-2);
  }
</style>
