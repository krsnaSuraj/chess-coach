<script lang="ts">
  /**
   * EngineSelector.svelte — dropdown to switch active engine.
   * 7 engines: Stockfish, Berserk, Caissa, Crystal, Patricia, ShashChess, Maia-2.
   */
  import type { SettingsStore } from '$lib/stores/settings.svelte';
  import type { EngineInfo } from '$lib/types';

  let { settings }: { settings: SettingsStore } = $props();

  let open = $state(false);

  function pick(name: string) {
    settings.switchEngine(name);
    open = false;
  }

  function currentEngine(): EngineInfo | undefined {
    return settings.engines.find((e) => e.name === settings.data.engine);
  }

  function badgeFor(t: EngineInfo['type']): string {
    if (t === 'neural') return '🧠';
    if (t === 'hybrid') return '⚡';
    return '♟';
  }
</script>

<div class="engine-selector" data-testid="engine-selector">
  <button class="trigger" onclick={() => (open = !open)} aria-haspopup="listbox" aria-expanded={open}>
    <span class="badge">{currentEngine() ? badgeFor(currentEngine()!.type) : '♟'}</span>
    <span class="name">{settings.data.engine}</span>
    <span class="caret">▾</span>
  </button>
  {#if open}
    <ul class="menu" role="listbox">
      {#each settings.engines as e (e.name)}
        <li
          class="item"
          class:active={settings.data.engine === e.name}
          onclick={() => pick(e.name)}
          onkeydown={(k) => {
            if (k.key === 'Enter' || k.key === ' ') {
              k.preventDefault();
              pick(e.name);
            }
          }}
          role="option"
          aria-selected={settings.data.engine === e.name}
          tabindex={0}
        >
          <span class="badge">{badgeFor(e.type)}</span>
          <span class="iname">{e.name}</span>
          <span class="iver">v{e.version}</span>
          <span class="ielo">≤ {e.elo_ceiling}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .engine-selector {
    position: relative;
    display: inline-block;
  }
  .trigger {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--bg-1);
    color: var(--fg-0);
    border: 1px solid var(--bg-3);
    border-radius: 4px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--font-mono);
  }
  .trigger:hover {
    background: var(--bg-2);
  }
  .badge { font-size: 14px; }
  .caret { font-size: 10px; color: var(--fg-2); }
  .menu {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 4px;
    background: var(--bg-1);
    border: 1px solid var(--bg-3);
    border-radius: 6px;
    list-style: none;
    padding: 4px 0;
    min-width: 220px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    z-index: 50;
  }
  .item {
    display: grid;
    grid-template-columns: 20px 1fr auto auto;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 11px;
    transition: background 80ms;
  }
  .item:hover {
    background: var(--bg-2);
  }
  .item.active {
    background: color-mix(in srgb, var(--accent) 20%, transparent);
    color: var(--fg-0);
  }
  .iname { font-family: var(--font-mono); font-weight: 600; }
  .iver, .ielo {
    font-size: 10px;
    color: var(--fg-2);
    font-family: var(--font-mono);
  }
</style>
