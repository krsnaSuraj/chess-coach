<script lang="ts">
  /**
   * SoundManager.svelte — plays move/capture/check sounds via WebAudio.
   * No /api/sound endpoint exists; sounds are purely client-side.
   */
  import type { SettingsStore } from '$lib/stores/settings.svelte';

  let { settings, kind }: {
    settings: SettingsStore;
    kind: 'move' | 'capture' | 'check' | 'castle' | 'promote' | 'gameover';
  } = $props();

  let lastFired = 0;

  function fire() {
    if (!settings.data.soundEnabled) return;
    const now = performance.now();
    if (now - lastFired < 200) return;
    lastFired = now;
    try {
      const AC = (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext);
      const ctx = new AC();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g);
      g.connect(ctx.destination);
      g.gain.value = settings.data.soundVolume * 0.2;
      const map: Record<typeof kind, number> = {
        move: 320, capture: 220, check: 540, castle: 280, promote: 480, gameover: 180
      };
      o.frequency.value = map[kind];
      o.type = 'triangle';
      o.start();
      o.stop(ctx.currentTime + 0.06);
    } catch {
      /* ignore */
    }
  }

  $effect(() => {
    void kind;
    fire();
  });
</script>
