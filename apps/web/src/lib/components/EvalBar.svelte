<script lang="ts">
  /**
   * EvalBar.svelte — vertical eval bar with smooth 200 ms tween.
   * Uses EvalStore.displayedCp / .targetCp as inputs.
   */
  import { cpToBar, formatEvalUnsigned } from '$lib/utils/tween';
  import type { EvalStore } from '$lib/stores/eval.svelte';

  let {
    evalStore,
    orientation = 'white',
    visible = true
  }: {
    evalStore: EvalStore;
    orientation?: 'white' | 'black';
    visible?: boolean;
  } = $props();

  let ratio = $derived(cpToBar(evalStore.displayedCp));
  // top-down: when orientation is 'white', top is white, bottom is black
  let whiteHeight = $derived(
    orientation === 'white' ? ratio * 100 : (1 - ratio) * 100
  );
  let blackHeight = $derived(100 - whiteHeight);

  // Displayed label: the side that has the advantage
  let label = $derived(formatEvalUnsigned(evalStore.displayedCp));
  let isMate = $derived(evalStore.targetMate != null && evalStore.targetMate !== 0);

  // animate height via CSS transition (defined in app.css under .eval-bar-fill)
  let whiteStyle = $derived(`height: ${whiteHeight}%`);
  let blackStyle = $derived(`height: ${blackHeight}%`);

  let labelTop = $derived(orientation === 'white' ? `${whiteHeight}%` : `${blackHeight}%`);
  let labelColor = $derived(
    orientation === 'white'
      ? whiteHeight > 50
        ? 'var(--bg-0)'
        : 'var(--fg-0)'
      : blackHeight > 50
        ? 'var(--bg-0)'
        : 'var(--fg-0)'
  );
</script>

{#if visible}
  <div class="eval-bar" aria-label="Evaluation bar" data-testid="eval-bar">
    <div class="eval-bar-fill white" style={whiteStyle}></div>
    <div class="eval-bar-fill black" style={blackStyle}></div>
    {#if isMate}
      <div class="eval-label" style="top: {labelTop}; color: {labelColor}">
        M{Math.abs(evalStore.targetMate ?? 0)}
      </div>
    {:else}
      <div class="eval-label" style="top: {labelTop}; color: {labelColor}">
        {label}
      </div>
    {/if}
  </div>
{/if}

<style>
  .eval-bar {
    position: relative;
    width: 50px;
    height: 100%;
    background: var(--bg-3);
    border-radius: 4px;
    overflow: hidden;
    user-select: none;
  }
  .eval-bar-fill {
    position: absolute;
    left: 0;
    right: 0;
    transition: height 200ms cubic-bezier(0.33, 1, 0.68, 1);
  }
  .eval-bar-fill.white {
    top: 0;
    background: linear-gradient(180deg, #f5f5f5, #d6d6d6);
  }
  .eval-bar-fill.black {
    bottom: 0;
    background: linear-gradient(0deg, #1a1a1a, #3a3a3a);
  }
  .eval-label {
    position: absolute;
    left: 50%;
    transform: translate(-50%, -50%);
    font-size: 11px;
    font-weight: 700;
    font-family: var(--font-mono);
    line-height: 1;
    pointer-events: none;
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7);
    z-index: 2;
    white-space: nowrap;
  }
</style>
