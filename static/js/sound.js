/* ============================================================================
   sound.js — Web Audio mirror of Python sound_manager v2.
   10 SFX types, 8 themes, spatial pan. Pure Web Audio API, no deps.
   ============================================================================ */

(function () {
  'use strict';

  // Mirror of Python SFX_PROFILES (simplified for browser)
  const SFX_PROFILES = {
    move:             { dur: 0.08,  freq: 800,  env: 'click' },
    capture:          { dur: 0.12,  freq: 400,  env: 'wood' },
    check:            { dur: 0.4,   freq: 1200, env: 'bell' },
    castle:           { dur: 0.22,  freq: 300,  env: 'wood' },
    promote:          { dur: 0.5,   freq: 600,  env: 'chime' },
    illegal:          { dur: 0.1,   freq: 720,  env: 'buzz' },
    game_start:       { dur: 0.7,   freq: 480,  env: 'bell' },
    game_end:         { dur: 1.2,   freq: 600,  env: 'bell' },
    engine_analyzing: { dur: 0.03,  freq: 2400, env: 'click' },
    brilliant:        { dur: 0.6,   freq: 720,  env: 'chime' },
  };

  // Theme sound palettes (envelope + brightness per theme)
  const THEME_SOUND = {
    midnight:    { attack: 0.002, decay: 0.08,  brightness: 0.6 },
    forest:      { attack: 0.008, decay: 0.12,  brightness: 0.3 },
    sunset:      { attack: 0.01,  decay: 0.14,  brightness: 0.4 },
    marble:      { attack: 0.003, decay: 0.07,  brightness: 0.7 },
    lichess:     { attack: 0.004, decay: 0.08,  brightness: 0.5 },
    blue_glass:  { attack: 0.001, decay: 0.06,  brightness: 0.8 },
    cyber_neon:  { attack: 0.001, decay: 0.04,  brightness: 0.9 },
    sepia:       { attack: 0.012, decay: 0.16,  brightness: 0.2 },
  };

  class SoundEngine {
    constructor() {
      this.ctx = null;
      this.enabled = true;
      this.volume = 0.5;
      this.theme = 'midnight';
      this._ambient = null;
    }

    _ensureCtx() {
      if (!this.ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC) this.ctx = new AC();
      }
      return this.ctx;
    }

    setEnabled(b) { this.enabled = !!b; }
    setVolume(v) { this.volume = Math.max(0, Math.min(1, v)); }
    setTheme(name) { this.theme = name; }

    // Spatial pan: fileIndex 0..7 (a..h)
    play(sfx, fileIndex = 4) {
      if (!this.enabled) return;
      const ctx = this._ensureCtx();
      if (!ctx) return;
      const profile = SFX_PROFILES[sfx] || SFX_PROFILES.move;
      const pal = THEME_SOUND[this.theme] || THEME_SOUND.midnight;
      const now = ctx.currentTime;
      const dur = profile.dur;
      // Main oscillator
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const pan = ctx.createStereoPanner ? ctx.createStereoPanner() : null;
      osc.type = profile.env === 'buzz' ? 'sawtooth' : 'sine';
      osc.frequency.setValueAtTime(profile.freq, now);
      // Envelope
      const attack = pal.attack;
      const decay = pal.decay;
      const peak = this.volume * 0.5;
      gain.gain.setValueAtTime(0, now);
      gain.gain.linearRampToValueAtTime(peak, now + attack);
      gain.gain.exponentialRampToValueAtTime(0.001, now + dur);
      // Chain
      osc.connect(gain);
      if (pan) {
        const panVal = (fileIndex - 3.5) / 3.5;
        pan.pan.setValueAtTime(panVal, now);
        gain.connect(pan);
        pan.connect(ctx.destination);
      } else {
        gain.connect(ctx.destination);
      }
      osc.start(now);
      osc.stop(now + dur + 0.05);
    }

    // Procedural ambient drone
    playMusic(track) {
      this.stopMusic();
      const ctx = this._ensureCtx();
      if (!ctx) return;
      const freqs = track === 'analysis' ? [82.41, 123.47, 196.00]
                  : track === 'game'     ? [130.81, 196.00, 261.63]
                                         : [110.0, 165.0, 220.0];
      const master = ctx.createGain();
      master.gain.value = this.volume * 0.08;
      master.connect(ctx.destination);
      this._ambient = freqs.map(f => {
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = f;
        const g = ctx.createGain();
        g.gain.value = 0.3;
        osc.connect(g);
        g.connect(master);
        osc.start();
        return { osc, g };
      });
    }

    stopMusic() {
      if (this._ambient) {
        for (const a of this._ambient) {
          try { a.osc.stop(); } catch (e) {}
        }
        this._ambient = null;
      }
    }
  }

  window.SoundEngine = SoundEngine;
})();
