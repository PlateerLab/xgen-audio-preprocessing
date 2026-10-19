"""DEX opt-out and bounded worker protocol contracts."""
import base64
import json
import subprocess
import sys
from unittest.mock import patch

import pytest
from xgen_audio import AudioPreprocessor


def worker(requests):
    return subprocess.run([sys.executable, '-m', 'xgen_audio.cli', '--jsonl', '--no-vad'],
                          input=requests, capture_output=True, timeout=10)


def test_vad_disabled_never_constructs_model():
    with patch('xgen_audio.stream.SileroVadSegmenter', side_effect=AssertionError('must not load')):
        with AudioPreprocessor(vad=False) as stream:
            chunk = stream.push(b'\x01\x02' * 1025)
            assert chunk.pcm == b'\x01\x02' * 1025
            assert chunk.events == []
            assert stream.finish().events == []


def test_jsonl_drain_and_bypass():
    pcm = b'\x01\x02' * 1025
    data = json.dumps({'type': 'push', 'pcm': base64.b64encode(pcm).decode()}) + '\n{"type":"finish"}\n'
    result = worker(data.encode())
    assert result.returncode == 0, result.stderr
    ready, chunk, tail = map(json.loads, result.stdout.splitlines())
    assert ready == {'type': 'ready'}
    assert base64.b64decode(chunk['pcm']) + base64.b64decode(tail['pcm']) == pcm
    assert chunk['events'] == tail['events'] == []
    assert chunk['inSpeech'] is False


@pytest.mark.parametrize('payload', [b'[]\n', b'{"type":"oops"}\n', b'{"type":"push","pcm":"!"}\n',
    b'x' * 90000, b'', b'{"type":"push","pcm":"AA=="}\n{"type":"finish"}\n'])
def test_bad_protocol_exits_nonzero(payload):
    assert worker(payload).returncode != 0
