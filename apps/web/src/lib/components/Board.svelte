<script lang="ts">
  /**
   * Board.svelte — chessground canvas board wrapper.
   * Owns the chessground instance, syncs to game state via $effect.
   */
  import { onMount, onDestroy } from 'svelte';
  import { Chessground } from 'chessground';
  import { api } from '$lib/api/client';
  import type { SquareKey, ArrowShape } from '$lib/types';
  import { fenToLegalMoves, isPromotion } from '$lib/utils/chess';

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
  // chessground does not export the Api type from its main entry; use ReturnType
  type CGApi = ReturnType<typeof Chessground>;
  let board: CGApi | undefined = $state();

  onMount(() => {
    board = Chessground(element, {
      fen,
      orientation,
      coordinates: showCoordinates,
      movable: {
        free: false,
        color: 'both',
        showDests: true,
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
      drawable: {
        enabled: true,
        visible: true
      }
    });
  });

  onDestroy(() => {
    board?.destroy();
  });

  // Sync FEN, orientation, and shapes whenever the props change
  $effect(() => {
    if (!board) return;
    const legal = fenToLegalMoves(fen);
    const dests = new Map<string, string[]>();
    for (const m of legal) {
      const arr = dests.get(m.from) ?? [];
      arr.push(m.to);
      dests.set(m.from, arr);
    }
    board.set({
      fen,
      orientation,
      coordinates: showCoordinates,
      movable: {
        // chessground internal type wants `Map<Key, Key[]>`; runtime accepts `Map<string, string[]>`
        dests: dests as unknown as Parameters<CGApi['set']>[0]['movable'] extends infer M
          ? M extends { dests?: infer D } ? D : never
          : never,
        showDests: true
      }
    });
  });

  // Last-move highlight (caller passes UCI)
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
    // chessground expects its own DrawShape — pass through
    board.setShapes(shapes as unknown as Parameters<CGApi['setShapes']>[0]);
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
    width: 100%;
    aspect-ratio: 1 / 1;
    max-height: min(80vh, calc(100vw - 32px));
    margin: 0 auto;
    background: var(--bg-2);
    border-radius: 6px;
    overflow: hidden;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
  }
  :global(.board-host .cg-wrap) {
    width: 100% !important;
    height: 100% !important;
  }
  :global(.board-host cg-board) {
    width: 100% !important;
    height: 100% !important;
  }
</style>
