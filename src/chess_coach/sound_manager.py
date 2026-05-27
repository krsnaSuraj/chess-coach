from __future__ import annotations

import logging
import math
import os
import struct
import wave

from PyQt6.QtCore import QUrl

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtMultimedia import QSoundEffect
    _HAS_SOUND = True
except ImportError:
    QSoundEffect = None  # type: ignore
    _HAS_SOUND = False
    logger.warning("QSoundEffect not available — sounds disabled")

_HERE = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(_HERE, "..", "..", "static", "sounds")
MOVE_WAV = os.path.join(SOUNDS_DIR, "move.wav")


def _generate_move_wav(path: str, duration_ms: int = 60) -> None:
    sample_rate = 22050
    n_samples = int(sample_rate * duration_ms / 1000)
    frequency = 600.0
    amplitude = 0.3
    decay = 0.6

    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        env = max(0.0, 1.0 - (i / n_samples) * decay)
        val = amplitude * env * math.sin(2 * math.pi * frequency * t)
        samples.append(int(val * 32767))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))


class SoundManager:
    def __init__(self) -> None:
        self._enabled = True
        self._move_sound: QSoundEffect | None = None
        self._init_sound()

    def _init_sound(self) -> None:
        if not _HAS_SOUND:
            self._enabled = False
            return
        if not os.path.exists(MOVE_WAV):
            try:
                _generate_move_wav(MOVE_WAV)
            except Exception as e:
                logger.warning("Failed to generate WAV: %s", e)
                self._enabled = False
                return
        try:
            self._move_sound = QSoundEffect()
            self._move_sound.setSource(QUrl.fromLocalFile(MOVE_WAV))
            self._move_sound.setVolume(0.5)
        except Exception as e:
            logger.warning("Failed to init QSoundEffect: %s", e)
            self._enabled = False

    def play_move(self) -> None:
        if not self._enabled or self._move_sound is None:
            return
        self._move_sound.play()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
