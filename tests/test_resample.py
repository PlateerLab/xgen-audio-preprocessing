import numpy as np
import pytest
from xgen_audio.resample import Resampler


def tone(freq, rate, n):
    return np.sin(2 * np.pi * freq * np.arange(n) / rate).astype(np.float32)


def run(x, rin, rout, size):
    r = Resampler(rin, rout)
    parts = [r.resample_chunk(x[i:i + size]) for i in range(0, len(x), size)]
    parts.append(r.resample_chunk(np.empty(0, np.float32), last=True))
    return np.concatenate(parts)


@pytest.mark.parametrize('rin,rout', [(16000, 48000), (48000, 16000)])
@pytest.mark.parametrize('n', [0, 1, 5, 1000, 4801])
def test_length(rin, rout, n):
    assert len(run(tone(440, rin, n), rin, rout, 333)) == -(-n * rout // rin)


@pytest.mark.parametrize('rin,rout', [(16000, 48000), (48000, 16000)])
def test_chunk_invariant(rin, rout):
    x = np.random.default_rng(1).normal(size=20011).astype(np.float32)
    expected = run(x, rin, rout, len(x))
    for size in (1, 7, 480, 4097):
        assert np.array_equal(run(x, rin, rout, size), expected)


def test_passband_gain_and_no_delay():
    x = tone(1000, 48000, 9600) * 8000
    y = run(x, 48000, 16000, 1000)
    ref = tone(1000, 16000, len(y)) * 8000
    assert np.abs(y[100:-100] - ref[100:-100]).max() < 80  # <1% of amplitude


def test_roundtrip_16k_48k_16k():
    x = tone(1000, 16000, 8000) * 8000
    y = run(run(x, 16000, 48000, 640), 48000, 16000, 640)
    assert len(y) == len(x) and np.abs(y[100:-100] - x[100:-100]).max() < 160


def test_alias_rejection():
    x = tone(12000, 48000, 9600) * 8000  # above the 16 kHz stream's Nyquist
    y = run(x, 48000, 16000, 1000)
    assert np.abs(y[100:-100]).max() < 8000 * 10 ** (-60 / 20)
