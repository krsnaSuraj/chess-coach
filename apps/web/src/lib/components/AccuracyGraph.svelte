<script lang="ts">
  /**
   * AccuracyGraph.svelte — canvas-based accuracy/CPL over time.
   * Lichess-style line graph, smooth curve, classification markers.
   */
  import { onMount } from 'svelte';
  import type { EvalStore } from '$lib/stores/eval.svelte';

  let {
    evalStore,
    visible = true,
    height = 144
  }: {
    evalStore: EvalStore;
    visible?: boolean;
    height?: number;
  } = $props();

  let canvas = $state<HTMLCanvasElement | undefined>(undefined);
  let container = $state<HTMLDivElement | undefined>(undefined);

  function draw() {
    if (!canvas || !container || !visible) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    // Background grid (every 0.5 pawn = 50cp)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
    ctx.lineWidth = 1;
    ctx.font = '10px var(--font-mono)';
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    for (let cp = -1000; cp <= 1000; cp += 250) {
      const y = h / 2 - (cp / 1000) * (h / 2 - 10);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    const hist = evalStore.history;
    if (hist.length < 2) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.textAlign = 'center';
      ctx.fillText('Make moves to see the eval graph', w / 2, h / 2);
      return;
    }

    // Map cp to y
    const cpToY = (cp: number) => h / 2 - Math.atan(cp / 220) / Math.PI * (h - 20) - 10;
    const plyToX = (ply: number) => ((ply - hist[0]!.ply) / Math.max(1, hist.length - 1)) * (w - 10) + 5;

    // Fill area under the curve (white-relative)
    ctx.beginPath();
    ctx.moveTo(plyToX(hist[0]!.ply), h);
    for (const p of hist) {
      ctx.lineTo(plyToX(p.ply), cpToY(p.cp));
    }
    ctx.lineTo(plyToX(hist.at(-1)!.ply), h);
    ctx.closePath();
    ctx.fillStyle = 'rgba(118, 150, 86, 0.18)';
    ctx.fill();

    // Line itself
    ctx.beginPath();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = '#769656';
    for (let i = 0; i < hist.length; i++) {
      const p = hist[i]!;
      const x = plyToX(p.ply);
      const y = cpToY(p.cp);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Classification markers
    const COLOR: Record<string, string> = {
      BRILLIANT: '#26c281',
      GREAT: '#5c9dff',
      BEST: '#769656',
      EXCELLENT: '#96bc4b',
      GOOD: '#b8b8b8',
      INACCURACY: '#f0b232',
      MISTAKE: '#e58a2d',
      BLUNDER: '#e84646',
      MISS: '#b8456c',
      FORCED: '#6c757d',
      BOOK: '#9c8e6c'
    };
    for (const p of hist) {
      const x = plyToX(p.ply);
      const y = cpToY(p.cp);
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = COLOR[p.cls] ?? '#ffffff';
      ctx.fill();
    }
  }

  $effect(() => {
    void evalStore.history;
    draw();
  });

  onMount(() => {
    draw();
    if (!container) return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(container);
    return () => ro.disconnect();
  });
</script>

{#if visible}
  <div class="accuracy-graph" bind:this={container} style="height: {height}px" data-testid="accuracy-graph">
    <canvas bind:this={canvas}></canvas>
  </div>
{/if}

<style>
  .accuracy-graph {
    width: 100%;
    background: var(--bg-1);
    border-radius: 6px;
    padding: 6px;
    box-sizing: border-box;
  }
  canvas {
    display: block;
  }
</style>
