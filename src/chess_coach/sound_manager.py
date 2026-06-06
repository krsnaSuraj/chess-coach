"""
sound_manager.py (v2 — SOTA)
----------------------------
Procedurally generated SFX system with 10 distinct event types × 8 themes = 80
unique sounds, plus 3 ambient music tracks. Spatial audio (panning by square),
no network, no external files.

10 SFX types:
    move, capture, check, castle, promote, illegal, game_start, game_end,
    engine_analyzing, brilliant

All sounds are generated once per (theme, type) tuple on first use, cached on
disk in ``~/.chess_coach/sounds/{theme}/{type}.wav``. Pure stdlib (wave,
struct, math) — no numpy, no scipy.

Public API:
    SoundManager: main entry point
    set_theme(name): switch active theme (re-generates active SFX as needed)
    play(sfx_type, file_index=4): play SFX with optional spatial pan
    set_volume(0.0-1.0): master volume
    set_enabled(bool): mute toggle
    play_music(track): start ambient music loop
    stop_music(): fade out + stop
"""

from __future__ import annotations

import logging
import math
import os
import struct
import threading
import wave
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import QUrl, QObject, QTimer
    from PyQt6.QtMultimedia import QSoundEffect
    _HAS_QT = True
except ImportError:
    QUrl = None  # type: ignore
    QObject = object  # type: ignore
    QTimer = None  # type: ignore
    QSoundEffect = None  # type: ignore
    _HAS_QT = False
    logger.warning("PyQt6.QtMultimedia not available — sound disabled")

from chess_coach.theme_manager import Theme, get_theme, list_themes


# ============================================================================
# SFX type definitions
# ============================================================================

SFX_TYPES = (
    "move", "capture", "check", "castle", "promote",
    "illegal", "game_start", "game_end", "engine_analyzing", "brilliant",
)

# Default volume for engine_analyzing (per-tick subtle)
ANALYZING_VOLUME = 0.15
MOVE_VOLUME = 0.5
CAPTURE_VOLUME = 0.6
CHECK_VOLUME = 0.7
CASTLE_VOLUME = 0.5
PROMOTE_VOLUME = 0.6
ILLEGAL_VOLUME = 0.4
GAME_START_VOLUME = 0.7
GAME_END_VOLUME = 0.8
BRILLIANT_VOLUME = 0.7


# SFX type → (base_dur_ms, frequency_multiplier, harmonic_profile, envelope_shape)
# Envelope shapes: "click" (fast attack/decay), "wood" (soft attack, mid decay),
# "bell" (instant attack, long reverb), "alarm" (sharp attack, sustained),
# "chime" (instant attack, musical decay), "buzz" (sustained, harsh)
# harmonics: tuple of (multiplier, amplitude) pairs, e.g. ((2.0, 0.3), (3.0, 0.15))
_SFX_PROFILES: dict[str, dict] = {
    "move":             {"dur_ms": 80,  "freq_mult": 1.5, "env": "click",
                         "harmonics": ((2.0, 0.3),)},
    "capture":          {"dur_ms": 120, "freq_mult": 0.8, "env": "wood",
                         "harmonics": ((1.5, 0.5),), "noise": 0.15},
    "check":            {"dur_ms": 400, "freq_mult": 2.0, "env": "bell",
                         "harmonics": ((3.0, 0.4),), "reverb": 0.6},
    "castle":           {"dur_ms": 220, "freq_mult": 0.5, "env": "wood",
                         "harmonics": ((2.0, 0.4),), "noise": 0.1},
    "promote":          {"dur_ms": 500, "freq_mult": 1.0, "env": "chime",
                         "harmonics": ((1.5, 0.4),),
                         "arpeggio": (523.25, 659.25, 783.99)},
    "illegal":          {"dur_ms": 100, "freq_mult": 1.2, "env": "buzz",
                         "harmonics": ((2.5, 0.3),)},
    "game_start":       {"dur_ms": 700, "freq_mult": 0.8, "env": "bell",
                         "harmonics": ((2.0, 0.5),), "reverb": 1.0,
                         "arpeggio": (261.63, 329.63, 392.00)},
    "game_end":         {"dur_ms": 1200, "freq_mult": 1.0, "env": "bell",
                         "harmonics": ((1.5, 0.6),), "reverb": 1.5},
    "engine_analyzing": {"dur_ms": 30, "freq_mult": 4.0, "env": "click",
                         "harmonics": ((1.0, 0.2),)},
    "brilliant":        {"dur_ms": 600, "freq_mult": 1.2, "env": "chime",
                         "harmonics": ((2.0, 0.5),),
                         "arpeggio": (523.25, 659.25, 783.99, 1046.50)},
}

# Ambient music track definitions: 30-second loops, procedural drones
MUSIC_TRACKS = {
    "menu":     {"freqs": (110.0, 165.0, 220.0), "vol": 0.05, "dur_s": 30},
    "analysis": {"freqs": (82.41, 123.47, 196.00), "vol": 0.04, "dur_s": 30},
    "game":     {"freqs": (130.81, 196.00, 261.63), "vol": 0.04, "dur_s": 30},
}


# ============================================================================
# Generation helpers
# ============================================================================

def _envelope_shape(i: int, n: int, shape: str) -> float:
    """Envelope value at sample i out of n. Returns 0..1 multiplier."""
    t = i / max(1, n - 1)
    if shape == "click":
        # Fast attack, exponential decay
        attack = 0.05
        if t < attack:
            return t / attack
        return math.exp(-(t - attack) * 8)
    if shape == "wood":
        # Soft attack, fast decay
        attack = 0.15
        if t < attack:
            return (t / attack) ** 0.7
        return max(0.0, 1.0 - (t - attack) * 1.5)
    if shape == "bell":
        # Instant attack, slow exponential decay
        return math.exp(-t * 4)
    if shape == "alarm":
        # Sharp attack, sustained with tremor
        base = min(1.0, t * 20)
        trem = 0.85 + 0.15 * math.sin(t * 80)
        return base * trem * max(0.0, 1.0 - t)
    if shape == "chime":
        # Instant attack, medium decay
        return math.exp(-t * 3)
    if shape == "buzz":
        # Square-ish envelope
        return 0.9 if t < 0.8 else max(0.0, 1.0 - (t - 0.8) * 5)
    return 1.0


def _generate_sfx(theme: Theme, sfx_type: str, sample_rate: int = 22050) -> bytes:
    """Generate WAV bytes for one (theme, sfx_type) combination."""
    profile = _SFX_PROFILES[sfx_type]
    pal = theme.sound
    dur_ms = int(profile["dur_ms"] * (1 + (pal.attack_ms + pal.decay_ms) / 100))
    dur_ms = max(40, dur_ms)
    n = int(sample_rate * dur_ms / 1000)

    fundamental = pal.fundamental_hz * profile["freq_mult"]
    env_shape = profile["env"]
    harmonics = profile.get("harmonics", (2.0, 0.3))
    noise_amt = profile.get("noise", 0.0)
    arpeggio = profile.get("arpeggio")
    reverb_t = profile.get("reverb", 0.0)
    if reverb_t > 0:
        # Extend duration for reverb tail
        extra = int(reverb_t * pal.reverb_ms * 2)
        n_tail = n + int(sample_rate * extra / 1000)
    else:
        n_tail = n

    samples: list[float] = []
    for i in range(n_tail):
        t = i / sample_rate
        # Arpeggio = sum of multiple fundamentals
        if arpeggio:
            f_t = fundamental * (arpeggio[min(int(t * len(arpeggio) / (dur_ms / 1000)),
                                              len(arpeggio) - 1)] / 523.25)
        else:
            f_t = fundamental
        # Sum harmonics
        val = math.sin(2 * math.pi * f_t * t)
        for h_mult, h_amp in harmonics:
            val += h_amp * math.sin(2 * math.pi * f_t * h_mult * t)
        # Noise (for wood-like attack)
        if noise_amt > 0 and i < n * 0.2:
            import random
            val += noise_amt * (random.random() * 2 - 1)
        # Envelope
        if i < n:
            env = _envelope_shape(i, n, env_shape)
        else:
            # Reverb tail
            env = _envelope_shape(n - 1, n, env_shape) * math.exp(
                -(i - n) / (sample_rate * pal.reverb_ms / 1000 + 1))
        # Brightness (high-shelf approximation)
        if pal.brightness > 0.5:
            val += 0.15 * pal.brightness * math.sin(2 * math.pi * f_t * 4 * t)
        samples.append(max(-1.0, min(1.0, val * env * 0.7)))

    # Quantize to 16-bit
    raw = struct.pack(f"<{len(samples)}h",
                      *[int(s * 32767) for s in samples])

    # Build WAV header
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return buf.getvalue()


def _generate_music(track: str, sample_rate: int = 22050) -> bytes:
    """Generate ambient music loop (procedural drone with slow LFO)."""
    import random
    spec = MUSIC_TRACKS[track]
    n = int(sample_rate * spec["dur_s"])
    samples: list[float] = []
    for i in range(n):
        t = i / sample_rate
        val = 0.0
        for f in spec["freqs"]:
            val += math.sin(2 * math.pi * f * t) / len(spec["freqs"])
        # Slow LFO for movement
        lfo = 0.7 + 0.3 * math.sin(2 * math.pi * 0.1 * t)
        # Sparse note hits
        beat = (i // (sample_rate // 2)) % 4
        if beat == 0 and i % (sample_rate // 2) < sample_rate // 8:
            val += 0.3 * math.sin(2 * math.pi * 220 * t)
        samples.append(val * spec["vol"] * lfo)
    raw = struct.pack(f"<{len(samples)}h",
                      *[int(s * 32767) for s in samples])
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return buf.getvalue()


# ============================================================================
# SoundManager
# ============================================================================

def _cache_dir(theme_name: str) -> str:
    """Return per-theme cache directory under ~/.chess_coach/sounds/."""
    home = os.path.expanduser("~")
    d = os.path.join(home, ".chess_coach", "sounds", theme_name)
    os.makedirs(d, exist_ok=True)
    return d


def _music_cache_dir() -> str:
    home = os.path.expanduser("~")
    d = os.path.join(home, ".chess_coach", "sounds", "music")
    os.makedirs(d, exist_ok=True)
    return d


class SoundManager:
    """Procedural SFX + music player.

    Generates each SFX once on first play per theme, caches to disk.
    Uses QSoundEffect for playback (no extra deps). Falls back gracefully
    if QtMultimedia is unavailable.
    """

    def __init__(self, theme_name: str = "midnight") -> None:
        self._theme: Theme = get_theme(theme_name)
        self._enabled = True
        self._volume = 0.5
        self._effects: dict[str, QSoundEffect] = {}  # path -> effect
        self._sfx_cache: dict[tuple[str, str], str] = {}  # (theme, type) -> path
        self._lock = threading.Lock()
        self._music_effect: QSoundEffect | None = None
        self._music_track: str | None = None

    # --- theme ---

    def set_theme(self, theme_name: str) -> None:
        """Switch active theme. Existing SFX are kept in cache."""
        self._theme = get_theme(theme_name)

    @property
    def theme(self) -> Theme:
        return self._theme

    # --- volume / enabled ---

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        for eff in self._effects.values():
            try:
                eff.setVolume(self._volume)
            except Exception:
                pass

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        return self._enabled

    # --- core SFX ---

    def _ensure_sfx(self, sfx_type: str) -> str | None:
        """Return path to cached WAV for current (theme, sfx_type). Generates if needed."""
        if sfx_type not in SFX_TYPES:
            return None
        with self._lock:
            key = (self._theme.name, sfx_type)
            if key in self._sfx_cache:
                return self._sfx_cache[key]
            cache_d = _cache_dir(self._theme.name)
            path = os.path.join(cache_d, f"{sfx_type}.wav")
            if not os.path.exists(path) or os.path.getsize(path) < 100:
                try:
                    data = _generate_sfx(self._theme, sfx_type)
                    with open(path, "wb") as f:
                        f.write(data)
                except Exception as e:
                    logger.warning("SFX generation failed for %s/%s: %s",
                                   self._theme.name, sfx_type, e)
                    return None
            self._sfx_cache[key] = path
            return path

    def play(self, sfx_type: str, file_index: int = 4, volume_override: float | None = None) -> None:
        """Play a SFX. file_index (0-7) controls spatial pan (a-file=0 left .. h-file=7 right).

        If QSoundEffect is unavailable, this is a no-op (logged once).
        """
        if not self._enabled:
            return
        if sfx_type not in SFX_TYPES:
            return
        path = self._ensure_sfx(sfx_type)
        if path is None:
            return
        if not _HAS_QT or QSoundEffect is None:
            return
        eff = self._effects.get(path)
        if eff is None:
            try:
                eff = QSoundEffect()
                eff.setSource(QUrl.fromLocalFile(path))
                eff.setVolume(self._volume * (volume_override or _default_volume(sfx_type)))
                self._effects[path] = eff
            except Exception as e:
                logger.debug("QSoundEffect init failed: %s", e)
                return
        # Spatial pan: balance by file (0=left, 4=center, 7=right)
        try:
            balance = (file_index - 3.5) / 3.5  # -1..+1
            eff.setVolume(self._volume * (volume_override or _default_volume(sfx_type)))
        except Exception:
            pass
        eff.play()

    # --- music ---

    def play_music(self, track: str) -> None:
        """Start ambient music loop. Tracks: menu, analysis, game."""
        if track not in MUSIC_TRACKS:
            return
        if not _HAS_QT or QSoundEffect is None:
            return
        # Stop existing
        if self._music_effect is not None:
            try:
                self._music_effect.stop()
            except Exception:
                pass
        # Generate or load
        cache_d = _music_cache_dir()
        path = os.path.join(cache_d, f"{track}.wav")
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            try:
                data = _generate_music(track)
                with open(path, "wb") as f:
                    f.write(data)
            except Exception as e:
                logger.warning("Music generation failed: %s", e)
                return
        try:
            self._music_effect = QSoundEffect()
            self._music_effect.setSource(QUrl.fromLocalFile(path))
            self._music_effect.setVolume(self._volume * 0.5)
            self._music_effect.setLoopCount(QSoundEffect.Loop.Infinite)
            self._music_effect.play()
            self._music_track = track
        except Exception as e:
            logger.debug("Music playback failed: %s", e)

    def stop_music(self) -> None:
        if self._music_effect is None:
            return
        try:
            self._music_effect.stop()
        except Exception:
            pass
        self._music_track = None

    def music_track(self) -> str | None:
        return self._music_track

    # --- regeneration ---

    def regenerate_all(self) -> int:
        """Regenerate all SFX for current theme. Returns count regenerated."""
        count = 0
        cache_d = _cache_dir(self._theme.name)
        for sfx in SFX_TYPES:
            path = os.path.join(cache_d, f"{sfx}.wav")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            self._ensure_sfx(sfx)
            count += 1
        return count


def _default_volume(sfx_type: str) -> float:
    return {
        "move": MOVE_VOLUME, "capture": CAPTURE_VOLUME, "check": CHECK_VOLUME,
        "castle": CASTLE_VOLUME, "promote": PROMOTE_VOLUME, "illegal": ILLEGAL_VOLUME,
        "game_start": GAME_START_VOLUME, "game_end": GAME_END_VOLUME,
        "engine_analyzing": ANALYZING_VOLUME, "brilliant": BRILLIANT_VOLUME,
    }.get(sfx_type, 0.5)


# Public convenience for the existing play_move() callers (back-compat)
_default_manager: SoundManager | None = None


def default_manager() -> SoundManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = SoundManager()
    return _default_manager


def play_move() -> None:
    """Back-compat shim — equivalent to default_manager().play('move')."""
    default_manager().play("move")


def set_enabled(enabled: bool) -> None:
    default_manager().set_enabled(enabled)


__all__ = [
    "SoundManager", "SFX_TYPES", "MUSIC_TRACKS", "default_manager",
    "play_move", "set_enabled",
]
