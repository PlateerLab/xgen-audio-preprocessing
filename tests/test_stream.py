from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from xgen_audio import AudioPreprocessor


def run(raw, size=2048, sr=16000, denoise=True):
    with AudioPreprocessor(sr, denoise="rnnoise" if denoise else "none") as stream:
        parts = [stream.push(raw[i:i+size]) for i in range(0, len(raw), size)]
        parts.append(stream.finish())
        assert stream.finish().pcm == b''
        with pytest.raises(RuntimeError):
            stream.push(b'00')
    return b''.join(p.pcm for p in parts), [(e.type, e.offset_bytes) for p in parts for e in p.events]


@pytest.mark.parametrize('sr', [16000, 48000])
@pytest.mark.parametrize('denoise', [True, False])
@pytest.mark.parametrize('n', [0, 1, 159, 160, 161, 1024, 16017])
def test_length_and_flush(sr, denoise, n):
    raw = np.random.default_rng(42).integers(-100, 100, n, dtype='<i2').tobytes()
    actual, _ = run(raw, 333, sr, denoise)
    assert len(actual) == ((n*16000 + sr//2)//sr)*2


def test_chunk_invariance_and_isolated_state():
    raw = np.random.default_rng(7).integers(-5000, 5000, 48001, dtype='<i2').tobytes()
    expected = run(raw, 2048)
    for size in [1, 333, 640, 4096, len(raw)]:
        assert run(raw, size) == expected
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(run, [raw, raw])) == [expected, expected]


def test_bypass_exact_pcm_and_validation():
    raw = np.array([-32768, -1, 0, 1, 32767], dtype='<i2').tobytes()
    assert run(raw, denoise=False)[0] == raw
    with pytest.raises(ValueError):
        AudioPreprocessor(44100)
    with AudioPreprocessor(denoise="none") as stream:
        with pytest.raises(TypeError):
            stream.push('bad')
        stream.push(b'0')
        with pytest.raises(ValueError, match='Truncated'):
            stream.finish()
        stream.push(b'0')
        assert len(stream.finish().pcm) == 0  # push already returned the complete sample


def test_cli_pcm_and_failure():
    raw = bytes(32001*2)
    result = subprocess.run([sys.executable, '-m', 'xgen_audio.cli', '--events'], input=raw, capture_output=True, check=True)
    assert len(result.stdout) == len(raw)
    assert b'speech_start' not in result.stderr
    result = subprocess.run([sys.executable, '-m', 'xgen_audio.cli'], input=b'x', capture_output=True)
    assert result.returncode == 1 and b'Truncated' in result.stderr


def test_noise_only_has_no_vad_events():
    raw = np.random.default_rng(42).normal(0, 104, 16000*6).astype('<i2').tobytes()
    assert run(raw)[1] == []

def test_explicit_backend_and_missing_library():
    with pytest.raises(ValueError):
        AudioPreprocessor(denoise='unknown')
    with pytest.raises(OSError):
        AudioPreprocessor(denoise='rnnoise', library='/nonexistent/librnnoise.so')
    raw = bytes(600)
    with AudioPreprocessor() as stream:
        assert stream.push(raw).pcm == raw  # safe default is no denoising
