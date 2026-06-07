<script lang="ts">
  /**
   * Main page — wires all 10 SOTA features end-to-end.
   * - Board (chessground) + drag-drop + arrow overlay
   * - EvalBar with 200ms tween
   * - WebSocket live eval streaming
   * - MoveList with arrow-key navigation (Left/Right/Home/End)
   * - MovePills with 11-class classification
   * - AccuracyGraph (Canvas)
   * - OpeningExplorer (Lichess DB)
   * - ThemeSwitcher (10 themes)
   * - PromotionDialog
   * - EngineSelector (7 engines)
   */
  import { onMount, onDestroy } from 'svelte';
  import Board from '$lib/components/Board.svelte';
  import EvalBar from '$lib/components/EvalBar.svelte';
  import MoveList from '$lib/components/MoveList.svelte';
  import StatusBar from '$lib/components/StatusBar.svelte';
  import AccuracyGraph from '$lib/components/AccuracyGraph.svelte';
  import OpeningExplorer from '$lib/components/OpeningExplorer.svelte';
  import PromotionDialog from '$lib/components/PromotionDialog.svelte';
  import SoundManager from '$lib/components/SoundManager.svelte';
  import { GameStore } from '$lib/stores/game.svelte';
  import { EvalStore } from '$lib/stores/eval.svelte';
  import { WsConnection } from '$lib/stores/ws.svelte';
  import { SettingsStore } from '$lib/stores/settings.svelte';
  import type { WsEvalMessage } from '$lib/types';

  const game = new GameStore();
  const evalStore = new EvalStore();
  const ws = new WsConnection();
  const settings = new SettingsStore();

  // Promotion dialog state
  let promotionFromTo = $state<{ from: string; to: string } | null>(null);
  let lastSoundKind = $state<'move' | 'capture' | 'check' | 'castle' | 'promote' | 'gameover'>('move');

  // Refresh game state on mount
  onMount(async () => {
    await settings.load();
    settings.applyTheme();
    await game.refresh();
    if (game.cursor < 0 && game.history.length > 0) game.cursor = game.history.length - 1;
    ws.start('/ws');
    evalStore.start();
  });

  onDestroy(() => {
    ws.stop();
    evalStore.stop();
  });

  // Subscribe to WS messages — update eval store + sound cues
  $effect(() => {
    const off = ws.onMessage((msg: WsEvalMessage) => {
      if (msg.type === 'eval') {
        const ply = game.state?.ply ?? 0;
        evalStore.onWs(msg, ply);
        if (msg.classification === 'BLUNDER') lastSoundKind = 'capture';
        else if (msg.classification === 'MISTAKE') lastSoundKind = 'move';
        else if (msg.classification === 'BRILLIANT') lastSoundKind = 'promote';
        else if (msg.classification === 'GREAT') lastSoundKind = 'castle';
        else lastSoundKind = 'move';
      }
    });
    return off;
  });

  // Board props
  let lastMoveUci = $derived.by(() => {
    if (game.cursor < 0) {
      return game.history.at(-1)?.uci ?? null;
    }
    return game.history[game.cursor]?.uci ?? null;
  });
  let bestUci = $derived(evalStore.bestUci);
  let altUci = $derived(evalStore.multipv[1]?.pv?.[0] ? evalStore.multipv[1]!.pv[0] + (evalStore.multipv[1]!.pv[1] ?? '') : null);

  // Board callbacks
  function handleMove(uci: string) {
    if (promotionFromTo) return; // ignore if dialog open
    game.playMove(uci);
    lastSoundKind = 'move';
    game.cursor = -1; // go to live
  }
  function handlePromotionRequest(from: string, to: string) {
    promotionFromTo = { from, to };
  }
  function handlePromotion(piece: 'q' | 'r' | 'b' | 'n') {
    if (!promotionFromTo) return;
    const uci = promotionFromTo.from + promotionFromTo.to + piece;
    promotionFromTo = null;
    lastSoundKind = 'promote';
    game.playMove(uci);
  }
  function handlePromotionCancel() {
    promotionFromTo = null;
  }

  function handleNewGame() {
    game.newGame();
    evalStore.reset();
  }
  function handleUndo() {
    game.undo();
  }
  function handleRedo() {
    game.redo();
  }
  function handleFlip() {
    settings.update('showCoordinates', settings.data.showCoordinates); // no-op, but keeps reactivity
    // orientation is in GameStore; flip there
    game.orientation = game.orientation === 'white' ? 'black' : 'white';
  }

  // -------- Global keyboard shortcuts --------
  // This is SOTA feature #1: arrow keys navigate game history.
  function onKey(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        game.stepBack();
        break;
      case 'ArrowRight':
        e.preventDefault();
        game.stepForward();
        break;
      case 'Home':
        e.preventDefault();
        game.goToStart();
        break;
      case 'End':
        e.preventDefault();
        game.goToEnd();
        break;
      case 'f':
      case 'F':
        e.preventDefault();
        game.orientation = game.orientation === 'white' ? 'black' : 'white';
        break;
      case 'n':
      case 'N':
        if (e.shiftKey) {
          e.preventDefault();
          handleNewGame();
        }
        break;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
</script>

<svelte:head>
  <title>Chess Coach v3.0.0 SOTA</title>
</svelte:head>

<main class="app" data-theme={settings.data.theme}>
  <StatusBar
    {ws}
    {evalStore}
    {settings}
    onNewGame={handleNewGame}
    onUndo={handleUndo}
    onRedo={handleRedo}
    onFlip={handleFlip}
  />

  <div class="board-zone">
    <EvalBar
      {evalStore}
      orientation={game.orientation}
      visible={settings.data.showEvalBar}
    />
    <div class="board-wrap">
      <Board
        fen={game.displayedFen}
        orientation={game.orientation}
        showCoordinates={settings.data.showCoordinates}
        showArrows={settings.data.showArrows}
        lastMoveUci={lastMoveUci}
        bestMoveUci={bestUci}
        altMoveUci={altUci}
        onMove={handleMove}
        onPromotionRequest={handlePromotionRequest}
      />
    </div>
  </div>

  <div class="bottom">
    <div class="moves-col">
      <h3>Moves</h3>
      <MoveList {game} />
    </div>
    <div class="graph-col">
      <AccuracyGraph {evalStore} visible={settings.data.showAccuracyGraph} />
    </div>
    <div class="explorer-col">
      <OpeningExplorer {game} />
    </div>
  </div>

  <footer class="hud">
    <span class="cls" data-testid="classification">
      Class: <strong>{evalStore.classification}</strong>
    </span>
    <span class="hint">
      ← → navigate · Home/End jump · F flip · Ctrl+Z undo · Shift+N new
    </span>
    <span class="status" data-testid="game-status">
      {#if game.error}
        <span style="color: var(--error)">⚠ {game.error}</span>
      {:else if game.state?.is_checkmate}
        ☠ Checkmate — {game.state.result ?? '*'}
      {:else if game.state?.is_stalemate}
        ½ Draw — stalemate
      {:else if game.state?.is_check}
        ✓ Check
      {:else}
        ▶ Live
      {/if}
    </span>
  </footer>

  {#if promotionFromTo}
    <PromotionDialog
      color={game.state?.turn === 'white' ? 'white' : 'black'}
      onSelect={handlePromotion}
      onCancel={handlePromotionCancel}
    />
  {/if}

  <SoundManager {settings} kind={lastSoundKind} />
</main>

<style>
  .app {
    display: grid;
    grid-template-rows: 38px 1fr auto 32px;
    height: 100vh;
    width: 100vw;
    background: var(--bg-0);
    color: var(--fg-0);
    overflow: hidden;
  }
  .board-zone {
    display: grid;
    grid-template-columns: 28px 1fr;
    gap: 12px;
    padding: 12px;
    overflow: hidden;
    align-items: stretch;
    max-height: calc(100vh - 38px - 180px - 32px);
  }
  .board-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .bottom {
    display: grid;
    grid-template-columns: 1fr 1fr 1.2fr;
    gap: 8px;
    padding: 8px 12px;
    max-height: 180px;
    overflow: hidden;
  }
  .moves-col h3 {
    margin: 0 0 4px 0;
    font-size: 11px;
    text-transform: uppercase;
    color: var(--fg-2);
    font-weight: 700;
    letter-spacing: 0.05em;
  }
  .moves-col {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .graph-col, .explorer-col {
    min-height: 0;
  }
  .hud {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 12px;
    background: var(--bg-1);
    border-top: 1px solid var(--bg-2);
    font-size: 11px;
    color: var(--fg-2);
    font-family: var(--font-mono);
  }
  .cls strong {
    color: var(--fg-0);
    text-transform: uppercase;
  }
  .hint { color: var(--fg-2); }
  .status { color: var(--fg-1); }
</style>
