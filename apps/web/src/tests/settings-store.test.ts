import { describe, it, expect } from 'vitest';
import { SettingsStore, THEMES, DEFAULTS } from '../lib/stores/settings.svelte';

describe('SettingsStore', () => {
  it('has 10 themes', () => {
    expect(THEMES).toHaveLength(10);
    expect(THEMES).toContain('midnight');
    expect(THEMES).toContain('high_contrast');
  });

  it('starts with default theme = midnight', () => {
    const s = new SettingsStore();
    expect(s.data.theme).toBe(DEFAULTS.theme);
    expect(s.data.theme).toBe('midnight');
  });

  it('update() changes a value', () => {
    const s = new SettingsStore();
    s.update('theme', 'forest');
    expect(s.data.theme).toBe('forest');
    s.update('soundEnabled', false);
    expect(s.data.soundEnabled).toBe(false);
  });

  it('update() preserves unrelated fields', () => {
    const s = new SettingsStore();
    const before = s.data.soundVolume;
    s.update('theme', 'sunset');
    expect(s.data.soundVolume).toBe(before);
  });
});
