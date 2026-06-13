<script lang="ts">
  /**
   * Main page — wires all 10 SOTA features end-to-end.
   * - Board (chessground) + drag-drop + arrow overlay
   * - EvalBar with 200ms tween
   * - WebSocket live eval streaming (analysis_update envelopes)
   * - MoveList with arrow-key navigation
   * - MovePills with 11-class classification
   * - AccuracyGraph (Canvas)
   * - OpeningExplorer (lightweight, no Lichess DB)
   * - ThemeSwitcher (10 themes)
   * - PromotionDialog
   * - EngineSelector (7 engines)
   */
  import { onMount, onDestroy } from 'svelte';
  import { Chess } from 'chess.js';
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
  import SideSelect from '$lib/components/SideSelect.svelte';
  import OpponentEntry from '$lib/components/OpponentEntry.svelte';
  import type { WsAnalysisUpdate, WsEnvelope } from '$lib/types';

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
    evalStore.reset();
    evalStore.fromCoach(game.state?.coach ?? null, 0, 'BOOK');
    ws.start('/ws');
    evalStore.start();
  });

  onDestroy(() => {
    ws.stop();
    evalStore.stop();
  });

  // Subscribe to WS messages — feed EvalStore
  $effect(() => {
    const off = ws.onMessage((msg: WsEnvelope) => {
      if (msg.type === 'analysis_update') {
        const upd = msg as WsAnalysisUpdate;
        evalStore.onWsAnalysisUpdate(upd);
        if (upd.classification === 'BLUNDER') lastSoundKind = 'capture';
        else if (upd.classification === 'MISTAKE') lastSoundKind = 'move';
        else if (upd.classification === 'BRILLIANT') lastSoundKind = 'promote';
        else if (upd.classification === 'GREAT') lastSoundKind = 'castle';
        else lastSoundKind = 'move';
      }
    });
    return off;
  });

  // Coach mode handlers
  function handleSideSelect(event: CustomEvent<{side: string; rating: number; classical: number; aggression: number}>) {
    const { side, rating, classical, aggression } = event.detail;
    ws.send({ type: 'set_side', side, rating, classical, aggression });
  }

  function handleOpponentMove(event: CustomEvent<{uci: string}>) {
    const { uci } = event.detail;
    ws.send({ type: 'opponent_move', uci });
    game.enterOpponentMove();
  }

  // Handle coach WS messages
  $effect(() => {
    const off = ws.onMessage((msg: WsEnvelope) => {
      if (msg.type === 'side_selected') {
        game.setSide((msg as any).side);
      } else if (msg.type === 'best_move') {
        game.receiveBestMove();
      } else if (msg.type === 'risk_assessment') {
        game.updateRisk((msg as any).score, (msg as any).level);
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
  let altUci = $derived(evalStore.multipv[1]?.pv?.[0] ? (evalStore.multipv[1]!.pv[0] + (evalStore.multipv[1]!.pv[1] ?? '')) : null);

  // Board callbacks
  async function handleMove(uci: string) {
    if (promotionFromTo) return;
    const beforeFen = game.state?.fen ?? '';
    const ok = await game.playMove(uci);
    if (!ok) { lastSoundKind = 'move'; return; }
    evalStore.fromCoach(game.state?.coach ?? null, game.history.length, game.latestClassification);
    // Detect capture/check from the move SAN
    try {
      const last = game.history[game.history.length - 1];
      if (last?.san.includes('x')) lastSoundKind = 'capture';
      else if (last?.san.includes('+') || last?.san.includes('#')) lastSoundKind = 'check';
      else lastSoundKind = 'move';
    } catch { lastSoundKind = 'move'; }
    void beforeFen;
    game.cursor = -1;
  }

  function handlePromotionRequest(from: string, to: string) {
    promotionFromTo = { from, to };
  }
  async function handlePromotion(piece: 'q' | 'r' | 'b' | 'n') {
    if (!promotionFromTo) return;
    const uci = promotionFromTo.from + promotionFromTo.to + piece;
    promotionFromTo = null;
    lastSoundKind = 'promote';
    await game.playMove(uci, piece);
    evalStore.fromCoach(game.state?.coach ?? null, game.history.length, game.latestClassification);
  }
  function handlePromotionCancel() { promotionFromTo = null; }

  async function handleNewGame() {
    await game.newGame(true);
    evalStore.reset();
    evalStore.fromCoach(game.state?.coach ?? null, 0, 'BOOK');
  }
  async function handleUndo() {
    await game.undo();
    evalStore.fromCoach(game.state?.coach ?? null, game.history.length, game.latestClassification);
  }
  async function handleRedo() {
    await game.redo();
    evalStore.fromCoach(game.state?.coach ?? null, game.history.length, game.latestClassification);
  }
  function handleFlip() {
    game.orientation = game.orientation === 'white' ? 'black' : 'white';
  }

  // Live position summary derived from the FEN (no rich state on backend)
  let liveSummary = $derived.by(() => {
    const fen = game.displayedFen;
    if (!fen) return { kind: 'idle', label: 'No game' };
    try {
      const c = new Chess(fen);
      if (c.isCheckmate()) return { kind: 'mate', label: 'Checkmate' };
      if (c.isStalemate()) return { kind: 'stale', label: 'Stalemate' };
      if (c.isCheck()) return { kind: 'check', label: 'Check' };
      if (c.isGameOver()) return { kind: 'over', label: 'Game over' };
      return { kind: 'live', label: `${c.turn() === 'w' ? 'White' : 'Black'} to move` };
    } catch {
      return { kind: 'err', label: 'Bad FEN' };
    }
  });

  // -------- Global keyboard shortcuts --------
  function onKey(e: KeyboardEvent) {
    const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    switch (e.key) {
      case 'ArrowLeft':  e.preventDefault(); game.stepBack(); break;
      case 'ArrowRight': e.preventDefault(); game.stepForward(); break;
      case 'Home':       e.preventDefault(); game.goToStart(); break;
      case 'End':        e.preventDefault(); game.goToEnd(); break;
      case 'f': case 'F':
        e.preventDefault();
        game.orientation = game.orientation === 'white' ? 'black' : 'white';
        break;
      case 'n': case 'N':
        if (e.shiftKey) { e.preventDefault(); handleNewGame(); }
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
  {#if !game.selectedSide}
    <SideSelect on:select={handleSideSelect} />
  {/if}

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
    <aside class="side-panel">
      <section class="moves-section">
        <h3>Moves</h3>
        <MoveList {game} />
      </section>
      <section class="explorer-section">
        <OpeningExplorer {game} />
      </section>
    </aside>
  </div>

  {#if game.selectedSide && !game.isUserTurn}
    <OpponentEntry on:move={handleOpponentMove} />
  {/if}

  {#if game.selectedSide}
    <div class="risk-indicator" class:risky={game.riskLevel !== 'SAFE'}>
      Risk: {game.riskLevel} ({game.riskScore})
    </div>
  {/if}

  <div class="bottom">
    <AccuracyGraph {evalStore} visible={settings.data.showAccuracyGraph} />
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
      {:else if liveSummary.kind === 'mate'}
        ☠ {liveSummary.label}
      {:else if liveSummary.kind === 'stale'}
        ½ Draw — stalemate
      {:else if liveSummary.kind === 'check'}
        ✓ {liveSummary.label}
      {:else}
        ▶ {liveSummary.label}
      {/if}
    </span>
  </footer>

  {#if promotionFromTo}
    <PromotionDialog
      color={(() => {
        try {
          return new Chess(game.displayedFen).turn() === 'w' ? 'white' : 'black';
        } catch { return 'white'; }
      })()}
      onSelect={handlePromotion}
      onCancel={handlePromotionCancel}
    />
  {/if}

  <SoundManager {settings} kind={lastSoundKind} />
</main>

<style>
  .app {
    display: grid;
    grid-template-rows: 38px 1fr 160px 32px;
    height: 100vh;
    width: 100vw;
    background: var(--bg-0);
    color: var(--fg-0);
    overflow: hidden;
  }
  .board-zone {
    display: grid;
    grid-template-columns: 50px 1fr 300px;
    gap: 10px;
    padding: 10px;
    overflow: hidden;
    align-items: stretch;
    min-height: 0;
  }
  .board-wrap {
    display: grid;
    place-items: center;
    min-width: 0;
    min-height: 0;
  }
  .side-panel {
    display: grid;
    grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
    gap: 8px;
    min-height: 0;
    overflow: hidden;
  }
  .moves-section, .explorer-section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
  .moves-section h3 {
    margin: 0 0 4px 0;
    font-size: 11px;
    text-transform: uppercase;
    color: var(--fg-2);
    font-weight: 700;
    letter-spacing: 0.05em;
  }
  .bottom {
    padding: 0 10px 8px 10px;
    overflow: hidden;
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
  .risk-indicator {
    text-align: center;
    padding: 0.5rem;
    margin: 1rem;
    background: rgba(76, 175, 80, 0.15);
    border-radius: 4px;
    font-size: 0.875rem;
    color: #4caf50;
  }
  .risk-indicator.risky {
    background: rgba(244, 67, 54, 0.15);
    color: #f44336;
  }

  /* responsive: hide right panel on narrow screens, keep moves+explorer stack */
  @media (max-width: 900px) {
    .app { grid-template-rows: 38px 1fr 140px 32px; }
    .board-zone { grid-template-columns: 36px 1fr; }
    .side-panel { display: none; }
  }
  @media (max-width: 600px) {
    .board-zone { grid-template-columns: 24px 1fr; }
  }
</style>
