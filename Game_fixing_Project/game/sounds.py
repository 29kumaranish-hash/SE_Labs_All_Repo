import math
import random
from array import array

import pygame


def _envelope(i, n, attack=0.004, decay=6.0, rate=44100):
    """Quick fade-in (no click), then exponential fade-out."""
    t = i / rate
    a = min(1.0, t / attack) if attack > 0 else 1.0
    return a * math.exp(-decay * i / n)


def _tone(freq, ms, rate, volume=0.5, decay=6.0, end_freq=None, harmonic=0.0, noise=0.0):
    """Synthesize one note as a list of floats in [-1, 1].

    freq -> end_freq gives a pitch sweep; harmonic adds an octave overtone;
    noise adds a little random hiss (used for the thud of a bounce).
    """
    n = int(rate * ms / 1000)
    end_freq = freq if end_freq is None else end_freq
    samples = []
    phase = 0.0
    for i in range(n):
        f = freq + (end_freq - freq) * (i / n)
        phase += 2 * math.pi * f / rate
        v = math.sin(phase) + harmonic * math.sin(2 * phase)
        if noise:
            v += noise * random.uniform(-1, 1)
        samples.append(v * volume * _envelope(i, n, decay=decay, rate=rate))
    return samples


def _to_sound(samples, channels):
    """Convert float samples to a 16-bit pygame Sound (mono or stereo)."""
    peak = max(1.0, max(abs(s) for s in samples))   # never clip
    data = array("h")
    for s in samples:
        v = int(max(-1.0, min(1.0, s / peak)) * 32767)
        for _ in range(channels):
            data.append(v)
    return pygame.mixer.Sound(buffer=data.tobytes())


class SoundManager:
    """Builds the game's sound effects in code (no audio files needed).

    If audio cannot be started (no sound device, unsupported format, ...) the
    manager disables itself and every play_* call quietly does nothing, so
    the game always still runs.
    """

    BOUNCE_MIN_IMPACT = 1.2   # px/frame into the wall; softer touches are silent
    BOUNCE_COOLDOWN_MS = 90   # stops a rattle when the marble rests on a wall

    def __init__(self):
        self.enabled = False
        self.bounce = self.win = self.timeout = None
        self._last_bounce = -10_000
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            rate, fmt, channels = pygame.mixer.get_init()
            if fmt != -16:
                return  # only 16-bit signed output is handled
            self.bounce = _to_sound(self._make_bounce(rate), channels)
            self.win = _to_sound(self._make_win(rate), channels)
            self.timeout = _to_sound(self._make_timeout(rate), channels)
            self.enabled = True
        except Exception:
            self.enabled = False

    # ---- the three effects ---------------------------------------------
    @staticmethod
    def _make_bounce(rate):
        # short low "thunk": pitch drops quickly, with a touch of noise
        return _tone(230, 110, rate, volume=0.9, decay=7.0, end_freq=90, noise=0.12)

    @staticmethod
    def _make_win(rate):
        # rising C-E-G-C arpeggio
        out = []
        for freq, ms in ((523.25, 110), (659.25, 110), (783.99, 110), (1046.5, 380)):
            out += _tone(freq, ms, rate, volume=0.6, decay=3.5, harmonic=0.25)
        return out

    @staticmethod
    def _make_timeout(rate):
        # falling, buzzy notes ending on a low tone
        out = []
        for freq, end, ms in ((392.0, 370.0, 170), (311.1, 290.0, 170), (233.1, 210.0, 170), (155.6, 110.0, 500)):
            out += _tone(freq, ms, rate, volume=0.6, decay=2.5, end_freq=end, harmonic=0.5)
        return out

    # ---- playback ------------------------------------------------------
    def play_bounce(self, impact_speed):
        """Play the bounce thunk, louder for harder hits."""
        if not self.enabled or impact_speed < self.BOUNCE_MIN_IMPACT:
            return
        now = pygame.time.get_ticks()
        if now - self._last_bounce < self.BOUNCE_COOLDOWN_MS:
            return
        self._last_bounce = now
        self.bounce.set_volume(0.25 + 0.75 * min(1.0, impact_speed / 8.0))
        self.bounce.play()

    def play_win(self):
        if self.enabled:
            self.win.play()

    def play_timeout(self):
        if self.enabled:
            self.timeout.play()
