"""Continuous PCM output and advisory VAD events, never discard silence."""
from dataclasses import dataclass

import numpy as np
import soxr

from .denoise import RNNoise
from .pcm import VadEvent
from .vad import SileroVadSegmenter


@dataclass(frozen=True)
class AudioChunk:
    pcm: bytes
    events: list[VadEvent]


class AudioPreprocessor:
    """One instance per microphone/session. Input mono PCM16LE, output 16 kHz.

    push accepts transport splits including odd byte boundaries. finish drains
    filters once and closes the stream. VAD offsets refer to output PCM bytes.
    Create, use and close this stateful instance on the same thread.
    """
    def __init__(self, sample_rate: int = 16000, *, denoise: str = "none", vad: bool = True, library: str | None = None):
        if sample_rate not in (16000, 48000):
            raise ValueError('Input must be 16000 or 48000 Hz mono PCM16LE')
        if denoise not in ('none', 'rnnoise', 'deepfilter'):
            raise ValueError('denoise must be none, rnnoise, or deepfilter')
        self.sample_rate = sample_rate
        self.vad = SileroVadSegmenter(16000) if vad else None
        self._noise = RNNoise(library) if denoise == "rnnoise" else None
        self._df = None
        if denoise == "deepfilter":
            try:
                from deepfilternet_rs import DeepFilterNetRealtime
            except ImportError as exc:
                raise RuntimeError('Install xgen-audio-preprocessing[deepfilter] with Python 3.11/3.12') from exc
            from importlib.metadata import version
            if version('deepfilternet-rs') != '0.1.1':
                raise RuntimeError('DeepFilterNet drain compensation requires deepfilternet-rs==0.1.1')
            self._df = DeepFilterNetRealtime(compensate_delay=True, log_level="error")
        internal_rate = 48000 if denoise != "none" else 16000
        self._up = soxr.ResampleStream(sample_rate, internal_rate, 1, dtype='float32', quality='HQ') if sample_rate != internal_rate else None
        self._down = soxr.ResampleStream(48000, 16000, 1, dtype='float32', quality='HQ') if denoise != "none" else None
        self._odd = b''
        self._pending = np.empty(0, dtype=np.float32)
        self._skip = RNNoise.delay_samples if denoise == "rnnoise" else 0
        self._input_samples = 0
        self._output_samples = 0
        self._finished = False

    def _filtered(self, x: np.ndarray, final: bool = False) -> np.ndarray:
        if self._up is not None:
            x = self._up.resample_chunk(x, last=final)
        if self._df is not None:
            y = self._df.process_chunk(x / 32768) if len(x) else np.empty(0, dtype=np.float32)
            if final:
                # v0.1.1 finalize omits the DFN3 delay: (960-480)+2*480.
                tail = self._df.process_chunk(np.zeros(1440, dtype=np.float32))
                y = np.concatenate((y, tail, self._df.finalize()))
            return self._down.resample_chunk(y * 32768, last=final) if len(y) or final else y
        if self._noise is None:
            return x
        x = np.concatenate((self._pending, x))
        if final:
            # Flush the overlap/add delay as well as the incomplete final frame.
            x = np.pad(x, (0, (-len(x)) % 480 + RNNoise.delay_samples))
        usable = len(x) // 480 * 480
        frames = [self._noise.process(x[i:i+480]) for i in range(0, usable, 480)]
        self._pending = x[usable:].copy()
        y = np.concatenate(frames) if frames else np.empty(0, dtype=np.float32)
        skip = min(self._skip, len(y))
        self._skip -= skip
        y = y[skip:]
        # Do not pass empty non-final chunks to libsoxr.
        if len(y) or final:
            return self._down.resample_chunk(y, last=final)
        return y

    def _result(self, y: np.ndarray) -> AudioChunk:
        # Padding used to drain RNNoise must not extend the microphone timeline.
        target = (self._input_samples * 16000 + self.sample_rate // 2) // self.sample_rate
        y = y[:max(0, target - self._output_samples)]
        pcm = np.clip(np.rint(y), -32768, 32767).astype('<i2').tobytes()
        self._output_samples += len(y)
        return AudioChunk(pcm, self.vad.push(pcm) if self.vad is not None else [])

    def push(self, pcm: bytes) -> AudioChunk:
        if self._finished:
            raise RuntimeError('Stream is closed')
        if not isinstance(pcm, bytes):
            raise TypeError('Expected PCM bytes')
        data = self._odd + pcm
        usable = len(data) // 2 * 2
        self._odd = data[usable:]
        if not usable:
            return AudioChunk(b'', [])
        x = np.frombuffer(data[:usable], dtype='<i2').astype(np.float32)
        self._input_samples += len(x)
        return self._result(self._filtered(x))

    def finish(self) -> AudioChunk:
        if self._finished:
            return AudioChunk(b'', [])
        if self._odd:
            raise ValueError('Truncated PCM16 sample: one byte remains')
        try:
            result = self._result(self._filtered(np.empty(0, dtype=np.float32), final=True))
            return AudioChunk(result.pcm, result.events + (self.vad.flush() if self.vad is not None else []))
        finally:
            self.close()

    def close(self):
        """Cancel without draining; use finish for a normal stop."""
        self._finished = True
        if self._noise:
            self._noise.close()
        if self._df is not None:
            self._df.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
