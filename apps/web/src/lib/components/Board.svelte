<script lang="ts">
  /**
   * Board.svelte — chessground canvas board wrapper.
   * Owns the chessground instance, syncs to game state via $effect.
   * Uses a ResizeObserver to force chessground to redraw when the
   * host element's size changes (initial render, theme switch, etc.).
   */
  import { onMount, onDestroy } from 'svelte';
  import { Chessground } from 'chessground';
  import type { SquareKey, ArrowShape } from '$lib/types';
  import { fenToLegalMoves, isPromotion } from '$lib/utils/chess';

  /** chessground v9 Key: 'a0' sentinel + every a1..h8 file/rank. */
  type CGKey = 'a0' | SquareKey;

  let {
    fen,
    orientation = 'white',
    showCoordinates = true,
    showArrows = true,
    lastMoveUci = null,
    bestMoveUci = null,
    altMoveUci = null,
    onMove,
    onPromotionRequest
  }: {
    fen: string;
    orientation?: 'white' | 'black';
    showCoordinates?: boolean;
    showArrows?: boolean;
    lastMoveUci?: string | null;
    bestMoveUci?: string | null;
    altMoveUci?: string | null;
    onMove?: (uci: string) => void;
    onPromotionRequest?: (from: string, to: string) => void;
  } = $props();

  let element: HTMLDivElement;
  type CGApi = ReturnType<typeof Chessground>;
  let board: CGApi | undefined = $state();
  let ro: ResizeObserver | null = null;

  function computeDests(f: string): Map<CGKey, CGKey[]> {
    const legal = fenToLegalMoves(f);
    const dests = new Map<CGKey, CGKey[]>();
    for (const m of legal) {
      const arr = dests.get(m.from as CGKey) ?? [];
      arr.push(m.to as CGKey);
      dests.set(m.from as CGKey, arr);
    }
    return dests;
  }

  onMount(() => {
    if (element.clientWidth === 0 || element.clientHeight === 0) {
      element.style.minHeight = '480px';
    }
    const dests = computeDests(fen);
    const api = Chessground(element, {
      fen,
      orientation,
      coordinates: showCoordinates,
      movable: {
        free: false,
        color: 'both',
        showDests: true,
        dests,
        events: {
          after: (orig, dest, _metadata) => {
            const uci = orig + dest;
            if (isPromotion(fen, orig, dest)) {
              onPromotionRequest?.(orig, dest);
            } else {
              onMove?.(uci);
            }
          }
        }
      },
      drawable: { enabled: true, visible: true }
    });
    board = api;

    // chessground caches the board rect on init via a memo. If the host
    // element's size wasn't finalised when onMount fired (e.g. parent
    // flex/grid layout still computing), the memo is stale and pieces
    // stay at translate(0,0). Defer a forced redraw to after layout.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const a = board as unknown as { redrawAll?: () => void } | undefined;
        if (a?.redrawAll) a.redrawAll();
      });
    });

    // Watch the host for size changes — chessground caches its
    // own dimensions on init, so a layout change needs a redraw.
    ro = new ResizeObserver(() => {
      const a = board as unknown as { redrawAll?: () => void } | undefined;
      if (a?.redrawAll) a.redrawAll();
      else board?.set({});
    });
    ro.observe(element);
  });

  onDestroy(() => {
    ro?.disconnect();
    board?.destroy();
  });

  // Sync FEN, orientation, and shapes whenever the props change
  $effect(() => {
    if (!board) return;
    const dests = computeDests(fen);
    board.set({
      fen,
      orientation,
      coordinates: showCoordinates,
      movable: { dests, showDests: true }
    });
  });

  let lastMoveUciDerived = $derived.by(() => {
    if (!lastMoveUci) return undefined;
    return lastMoveUci.replace(/[+#?!]+$/g, '');
  });

  $effect(() => {
    if (!board) return;
    const shapes: ArrowShape[] = [];
    if (showArrows) {
      if (bestMoveUci && bestMoveUci.length >= 4) {
        shapes.push({
          orig: bestMoveUci.slice(0, 2) as SquareKey,
          dest: bestMoveUci.slice(2, 4) as SquareKey,
          brush: 'green'
        });
      }
      if (altMoveUci && altMoveUci.length >= 4) {
        shapes.push({
          orig: altMoveUci.slice(0, 2) as SquareKey,
          dest: altMoveUci.slice(2, 4) as SquareKey,
          brush: 'red'
        });
      }
    }
    board.setShapes(shapes as never);
  });

  $effect(() => {
    if (!board || !lastMoveUciDerived || lastMoveUciDerived.length < 4) return;
    board.set({
      lastMove: [
        lastMoveUciDerived.slice(0, 2) as SquareKey,
        lastMoveUciDerived.slice(2, 4) as SquareKey
      ]
    });
  });
</script>

<div class="board-host" bind:this={element} data-testid="chess-board"></div>

<style>
  .board-host {
    /* Make it a square that fills its grid cell up to a sensible cap.
       Use viewport-relative units so resizing always produces a square.
       Layout: status(38) + board-zone(1fr) + graph(160) + hud(32).
       board-zone padding 10+10; eval bar lives in its own 50px column. */
    width: min(100%, calc(100vh - 250px));
    aspect-ratio: 1 / 1;
    max-width: 720px;
    max-height: 720px;
    margin: 0 auto;
    background: var(--bg-2);
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
    min-height: 320px;
    position: relative;
  }
  /* chessground's base.css sizes cg-container/cg-board via JS, but
     needs the host (.cg-wrap) to be a sized, positioned ancestor. */
  :global(.board-host.cg-wrap) {
    width: 100% !important;
    height: 100% !important;
  }
</style>
