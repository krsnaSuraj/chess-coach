<script lang="ts">
  /**
   * StatusBar.svelte — top status bar: connection, eval, depth, controls.
   */
  import type { WsConnection } from '$lib/stores/ws.svelte';
  import type { EvalStore } from '$lib/stores/eval.svelte';
  import type { SettingsStore } from '$lib/stores/settings.svelte';
  import EngineSelector from './EngineSelector.svelte';
  import ThemeSwitcher from './ThemeSwitcher.svelte';
  import { formatEval, cpToWinProbability, formatPct } from '$lib/utils/tween';

  let {
    ws,
    evalStore,
    settings,
    onNewGame,
    onUndo,
    onRedo,
    onFlip
  }: {
    ws: WsConnection;
    evalStore: EvalStore;
    settings: SettingsStore;
    onNewGame: () => void;
    onUndo: () => void;
    onRedo: () => void;
    onFlip: () => void;
  } = $props();

  let showThemes = $state(false);
</script>

<header class="status-bar" data-testid="status-bar">
  <div class="left">
    <span class="status-dot {ws.state}" title="WebSocket: {ws.state}"></span>
    <span class="conn">{ws.state}</span>
    <span class="sep">·</span>
    <span class="eval" data-testid="status-eval">
      {formatEval(evalStore.targetCp, evalStore.targetMate)}
    </span>
    <span class="sep">·</span>
    <span class="depth">d{evalStore.depth}</span>
    <span class="sep">·</span>
    <span class="winprob" data-testid="status-winprob">
      W {formatPct(evalStore.winProb, 0)}
    </span>
  </div>

  <div class="center">
    <button class="ctrl" onclick={onNewGame} title="New game (Ctrl+N)">New</button>
    <button class="ctrl" onclick={onUndo} title="Undo (Ctrl+Z)">↶ Undo</button>
    <button class="ctrl" onclick={onRedo} title="Redo (Ctrl+Y)">↷ Redo</button>
    <button class="ctrl" onclick={onFlip} title="Flip board (F)">⇅ Flip</button>
  </div>

  <div class="right">
    <EngineSelector {settings} />
    <button class="ctrl" onclick={() => (showThemes = !showThemes)} title="Themes">🎨</button>
  </div>

  {#if showThemes}
    <div class="theme-popover">
      <ThemeSwitcher {settings} />
      <button class="close" onclick={() => (showThemes = false)}>×</button>
    </div>
  {/if}
</header>

<style>
  .status-bar {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    padding: 6px 12px;
    background: var(--bg-1);
    border-bottom: 1px solid var(--bg-2);
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--fg-1);
    position: relative;
    height: 38px;
  }
  .left { display: flex; align-items: center; gap: 6px; }
  .center { display: flex; gap: 4px; justify-content: center; }
  .right { display: flex; gap: 6px; justify-content: flex-end; align-items: center; }
  .status-dot {
    width: 8px; height: 8px; border-radius: 50%; display: inline-block;
  }
  .status-dot.connected { background: var(--ok); box-shadow: 0 0 6px var(--ok); }
  .status-dot.connecting, .status-dot.open { background: var(--warn); animation: pulse 1s infinite; }
  .status-dot.closed, .status-dot.error { background: var(--error); }
  .status-dot.idle { background: var(--fg-2); }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  .sep { color: var(--fg-2); }
  .eval { font-weight: 700; color: var(--fg-0); }
  .depth, .winprob { color: var(--fg-1); }
  .ctrl {
    background: var(--bg-2);
    color: var(--fg-0);
    border: 1px solid var(--bg-3);
    border-radius: 3px;
    padding: 3px 8px;
    cursor: pointer;
    font-size: 11px;
    font-family: var(--font-sans);
    transition: background 80ms;
  }
  .ctrl:hover { background: var(--bg-3); }
  .theme-popover {
    position: absolute;
    top: 100%;
    right: 0;
    background: var(--bg-1);
    border: 1px solid var(--bg-3);
    border-radius: 6px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
    z-index: 80;
    min-width: 280px;
  }
  .close {
    position: absolute;
    top: 4px;
    right: 6px;
    background: transparent;
    border: none;
    color: var(--fg-2);
    font-size: 18px;
    cursor: pointer;
    line-height: 1;
  }
</style>
