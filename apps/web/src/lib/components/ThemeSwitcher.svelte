<script lang="ts">
  /**
   * ThemeSwitcher.svelte — 10 themes, persisted via SettingsStore.
   */
  import { THEMES, type SettingsStore, type ThemeName } from '$lib/stores/settings.svelte';

  let { settings }: { settings: SettingsStore } = $props();

  const SWATCH: Record<ThemeName, { bg: string; fg: string; accent: string }> = {
    midnight: { bg: '#1a1d23', fg: '#e8eaed', accent: '#769656' },
    forest: { bg: '#0d1b16', fg: '#e6f3ec', accent: '#4caf50' },
    sunset: { bg: '#1a0f1a', fg: '#fde2e2', accent: '#ff6b6b' },
    marble: { bg: '#f0e9d6', fg: '#2b2b2b', accent: '#6c4f2b' },
    lichess: { bg: '#1a1a1a', fg: '#bababa', accent: '#629924' },
    blue_glass: { bg: '#0a1929', fg: '#e0f0ff', accent: '#5da6ff' },
    cyber_neon: { bg: '#050511', fg: '#e0e6ff', accent: '#00f0ff' },
    sepia: { bg: '#f4ecd8', fg: '#3b2a14', accent: '#8b4513' },
    paper: { bg: '#fafaf7', fg: '#1a1a1a', accent: '#4a7ab0' },
    high_contrast: { bg: '#000000', fg: '#ffffff', accent: '#ffff00' }
  };

  function pick(t: ThemeName) {
    settings.update('theme', t);
  }
</script>

<div class="theme-switcher" data-testid="theme-switcher">
  <h3>Theme</h3>
  <div class="grid">
    {#each THEMES as t (t)}
      <button
        class="swatch"
        class:active={settings.data.theme === t}
        style="background: {SWATCH[t].bg}; color: {SWATCH[t].fg}; --swatch-accent: {SWATCH[t].accent};"
        onclick={() => pick(t)}
        aria-label="Theme {t}"
        data-theme-name={t}
      >
        <span class="dot" style="background: {SWATCH[t].accent}"></span>
        <span class="label">{t.replace('_', ' ')}</span>
      </button>
    {/each}
  </div>
</div>

<style>
  .theme-switcher {
    padding: 10px 12px;
  }
  h3 {
    margin: 0 0 8px 0;
    font-size: 13px;
    font-weight: 700;
    color: var(--fg-0);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px;
  }
  .swatch {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    border-radius: 4px;
    border: 2px solid transparent;
    cursor: pointer;
    font-size: 11px;
    text-transform: capitalize;
    font-family: var(--font-sans);
    transition: transform 80ms, border-color 120ms;
  }
  .swatch:hover {
    transform: translateY(-1px);
  }
  .swatch.active {
    border-color: var(--swatch-accent);
  }
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .label {
    flex: 1;
    text-align: left;
  }
</style>
