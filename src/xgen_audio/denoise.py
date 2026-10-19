"""RNNoise C ABI. Each stream owns its native state; PCM scale is int16 units."""
import ctypes as ct
import ctypes.util
import os
from pathlib import Path

import numpy as np


class RNNoise:
    frame_size = 480
    delay_samples = 480

    def __init__(self, library: str | None = None):
        path = library or os.environ.get('XGEN_RNNOISE_LIBRARY') or ctypes.util.find_library('rnnoise')
        if not path:
            raise RuntimeError('RNNoise library missing: run scripts/build_rnnoise.py and set XGEN_RNNOISE_LIBRARY')
        self._lib = ct.CDLL(str(Path(path).expanduser()) if '/' in path else path)
        self._lib.rnnoise_create.argtypes = [ct.c_void_p]
        self._lib.rnnoise_create.restype = ct.c_void_p
        self._lib.rnnoise_destroy.argtypes = [ct.c_void_p]
        self._lib.rnnoise_destroy.restype = None
        self._lib.rnnoise_get_frame_size.restype = ct.c_int
        if self._lib.rnnoise_get_frame_size() != self.frame_size:
            raise RuntimeError('Unsupported RNNoise frame size')
        ptr = ct.POINTER(ct.c_float)
        self._lib.rnnoise_process_frame.argtypes = [ct.c_void_p, ptr, ptr]
        self._lib.rnnoise_process_frame.restype = ct.c_float
        self._state = self._lib.rnnoise_create(None)
        if not self._state:
            raise MemoryError('Cannot allocate RNNoise state')

    def process(self, samples: np.ndarray) -> np.ndarray:
        if not self._state:
            raise RuntimeError('RNNoise is closed')
        if samples.shape != (480,) or not np.isfinite(samples).all():
            raise ValueError('Expected 480 finite float samples at 48 kHz')
        x = np.ascontiguousarray(samples, dtype=np.float32)
        y = np.empty_like(x)
        self._lib.rnnoise_process_frame(self._state, y.ctypes.data_as(ct.POINTER(ct.c_float)), x.ctypes.data_as(ct.POINTER(ct.c_float)))
        return y

    def close(self):
        if getattr(self, '_state', None):
            self._lib.rnnoise_destroy(self._state)
            self._state = None

    def __del__(self):
        self.close()
