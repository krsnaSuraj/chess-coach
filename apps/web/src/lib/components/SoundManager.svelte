<script lang="ts">
  /**
   * SoundManager.svelte — plays move/capture/check sounds.
   * Optional: when soundEnabled, fires off a simple beep via WebAudio API.
   */
  import { api } from '$lib/api/client';
  import type { SettingsStore } from '$lib/stores/settings.svelte';

  let { settings, kind }: { settings: SettingsStore; kind: 'move' | 'capture' | 'check' | 'castle' | 'promote' | 'gameover' } = $props();

  let lastFired = 0;

  function fire() {
    if (!settings.data.soundEnabled) return;
    // Throttle: max 5 sounds/sec
    const now = performance.now();
    if (now - lastFired < 200) return;
    lastFired = now;
    try {
      const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g);
      g.connect(ctx.destination);
      g.gain.value = settings.data.soundVolume * 0.2;
      const map = { move: 320, capture: 220, check: 540, castle: 280, promote: 480, gameover: 180 };
      o.frequency.value = map[kind];
      o.type = 'triangle';
      o.start();
      o.stop(ctx.currentTime + 0.06);
    } catch {
      /* ignore */
    }
    // Optionally also tell the backend so it can play its own sound
    api.sound(kind).catch(() => {});
  }

  $effect(() => {
    void kind;
    fire();
  });
</script>
