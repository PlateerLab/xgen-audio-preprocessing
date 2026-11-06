"""Streaming rational resampler (numpy only, zero group delay, chunk-invariant)."""
from math import gcd

import numpy as np


class Resampler:
    """Polyphase windowed-sinc resampler: in_rate -> out_rate, one mono stream.

    Output sample m sits at input time m*in/out (no delay), so total output is
    ceil(total_in*out/in). Needs ~half a filter of look-ahead, which `last=True`
    supplies with zeros. Kaiser(beta=9) FIR, cutoff 0.94 of the lower Nyquist.
    # ponytail: fixed 48-lobe filter; raise `lobes` if passband/stopband need tightening.
    """

    def __init__(self, in_rate: int, out_rate: int, lobes: int = 48):
        g = gcd(in_rate, out_rate)
        self._up, self._down = out_rate // g, in_rate // g
        up, down = self._up, self._down
        half = lobes * max(up, down)
        t = np.arange(-half, half + 1) / max(up, down)
        h = np.sinc(0.94 * t) * np.kaiser(2 * half + 1, 9.0) * 0.94 * up / max(up, down)
        self._half = half
        self._len = -(-(2 * half + 1) // up)
        padded = np.zeros(self._len * up)
        padded[:2 * half + 1] = h
        self._phases = padded.reshape(self._len, up).T.copy()  # [phase, tap] = h[phase + tap*up]
        self._x = np.zeros(self._len - 1)  # history, first element is input index _x0
        self._x0 = -(self._len - 1)
        self._m = 0  # next output index
        self._n = 0  # total input samples

    def resample_chunk(self, x: np.ndarray, last: bool = False) -> np.ndarray:
        up, down, half, length = self._up, self._down, self._half, self._len
        x = np.asarray(x, dtype=np.float64)
        self._n += len(x)
        if last:  # every output whose centre lies inside the input, then zero look-ahead
            total = -(-self._n * up // down)
            x = np.concatenate((x, np.zeros(half // up + length + 1)))
            end = total
        else:
            end = None
        self._x = np.concatenate((self._x, x))
        have = self._x0 + len(self._x)  # inputs available: indices < have
        if end is None:  # output m needs input index (m*down+half)//up < have
            end = max(self._m, (have * up - half - 1) // down + 1)
            end = min(end, -(-self._n * up // down))
        m = np.arange(self._m, end)
        if not len(m):
            return np.empty(0, dtype=np.float32)
        pos = m * down + half
        k = pos // up - self._x0  # buffer index of the newest input tap
        win = self._x[k[:, None] - np.arange(length)[None, :]]
        y = np.einsum('ml,ml->m', win, self._phases[pos % up])
        self._m = end
        keep = (end * down + half) // up - (length - 1) - self._x0
        if keep > 0:
            self._x = self._x[keep:]
            self._x0 += keep
        return y.astype(np.float32)
