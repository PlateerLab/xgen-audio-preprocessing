"""Run: python -B -m unittest discover -s scripts -p _test_stt_silero.py -v.

Real packaged Silero inference; ASR stubbed to count/inspect requests.
Workflow/Qwen end-to-end tests are separate.
"""
import asyncio
from collections import deque
import hashlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import wave

import numpy as np
from xgen_audio.vad import (
    SileroVadSegmenter, SileroVadUnavailable, SILERO_MODEL_PATH,
    SILERO_MODEL_SHA256, get_silero_session,
)

ROOT = Path(__file__).parent / "fixtures"

def fixture(name="speech"):
    with wave.open(str(ROOT / (name + ".wav")), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        pcm = w.readframes(w.getnframes())
    assert pcm, name
    return pcm

def zero(seconds):
    return bytes(int(seconds * 32000))

def noise(seconds):
    return np.random.default_rng(42).normal(0, 104, int(seconds * 16000)).astype("<i2").tobytes()

class FakeSession:
    def __init__(self, probabilities):
        self.probabilities = deque(probabilities)
        self.states = []
    def run(self, outputs, inputs):
        self.states.append(inputs["state"].copy())
        p = self.probabilities.popleft() if self.probabilities else 0
        return np.array([[p]], dtype=np.float32), inputs["state"] + 1

class SileroBoundaryTests(unittest.TestCase):
    def test_packaged_model_hash_and_cpu(self):
        self.assertEqual(hashlib.sha256(SILERO_MODEL_PATH.read_bytes()).hexdigest(), SILERO_MODEL_SHA256)
        self.assertEqual(get_silero_session().get_providers(), ["CPUExecutionProvider"])

    def test_chunk_splits_and_offsets_at_both_sample_rates(self):
        for sr in (8000, 16000):
            with self.subTest(sr=sr):
                vad = SileroVadSegmenter(sr, session=FakeSession([0]*50 + [0.9]*3 + [0.9]*4 + [0.1]*16))
                pcm = bytes(int(sr * .032) * 2 * 73)
                events = []
                # Odd transport byte boundaries must also preserve samples.
                for offset in range(0, len(pcm), 333):
                    events.extend(vad.push(pcm[offset:offset+333]))
                self.assertEqual([(e.type, e.offset_bytes) for e in events],
                                 [("speech_start", int(sr*.4)*2), ("speech_end", len(pcm))])
                self.assertFalse(vad.in_speech)

    def test_state_is_isolated_for_shared_onnx_session(self):
        session = FakeSession([0, 0])
        a, b = [SileroVadSegmenter(16000, session=session) for _ in range(2)]
        a.push(bytes(1024)); b.push(bytes(1024))
        self.assertTrue(all(not np.any(s) for s in session.states))
        self.assertIsNot(a._state, b._state)
        self.assertIsNot(a._context, b._context)

    def test_real_speech_and_short_answers(self):
        for name in ("speech", "yes", "no"):
            with self.subTest(name=name):
                vad = SileroVadSegmenter(16000)
                events = vad.push(zero(1) + fixture(name) + zero(1))
                self.assertEqual([e.type for e in events], ["speech_start", "speech_end"])

    def test_real_speech_8khz(self):
        pcm = np.frombuffer(fixture(), dtype="<i2")[::2].tobytes()
        vad = SileroVadSegmenter(8000)
        self.assertEqual([e.type for e in vad.push(bytes(16000) + pcm + bytes(16000))],
                         ["speech_start", "speech_end"])

    def test_quiet_speech_not_rejected_by_legacy_floor(self):
        pcm = (np.frombuffer(fixture(), dtype="<i2") * 10**(-25/20)).astype("<i2").tobytes()
        vad = SileroVadSegmenter(16000)
        self.assertEqual([e.type for e in vad.push(zero(1)+pcm+zero(1))], ["speech_start", "speech_end"])

    def test_noise_after_initial_digital_silence(self):
        vad = SileroVadSegmenter(16000)
        self.assertEqual(vad.push(zero(1) + noise(25)), [])
        self.assertEqual(vad.flush(), [])

    def test_flush_preserves_partial_frame_offset_and_is_idempotent(self):
        vad = SileroVadSegmenter(16000, session=FakeSession([.9]*3))
        vad.push(bytes(3200))
        self.assertEqual(vad.flush()[0].offset_bytes, 3200)
        self.assertEqual(vad.flush(), [])

class LibraryBoundaryTests(unittest.TestCase):
    def test_preroll_cannot_overlap_previous_utterance(self):
        vad = SileroVadSegmenter(16000, session=FakeSession([.9]*3 + [.1]*20 + [.9]*3 + [.1]*20))
        events = vad.push(bytes(46*1024)) + vad.flush()
        offsets = [event.offset_bytes for event in events]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual([e.type for e in events], ['speech_start','speech_end','speech_start','speech_end'])

    def test_flush_resets_recurrent_state_before_resume(self):
        session = FakeSession([.9]*6)
        vad = SileroVadSegmenter(16000, session=session)
        vad.push(bytes(3*1024)); vad.flush(); vad.push(bytes(3*1024))
        self.assertFalse(np.any(session.states[3]))
