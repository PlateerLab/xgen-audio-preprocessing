"""Silero VAD 기반 스트리밍 발화 경계 판정.

ONNX Runtime 세션은 프로세스에서 하나만 지연 생성한다. 반면 recurrent state와
프레임 경계에 걸친 PCM 잔여분은 ``SileroVadSegmenter`` 인스턴스에 두므로 서로 다른
WebSocket 세션의 음성이 섞이지 않는다.

모델은 이미지에 포함한 고정 버전을 사용하고 로드 전에 SHA-256을 확인한다. 모델,
런타임 또는 입력 sample rate가 유효하지 않으면 호출부가 기존 RMS/ZCR VAD로
전환할 수 있도록 원인이 포함된 ``SileroVadUnavailable``을 낸다.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Any, Deque, List, Optional

import numpy as np

from . import pcm as pcmutil


logger = logging.getLogger("audio-stream-silero-vad")

SILERO_MODEL_VERSION = "6.2.1"
SILERO_MODEL_SHA256 = "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"
SILERO_MODEL_PATH = Path(__file__).with_name("models") / "silero_vad_v6.2.1.onnx"
SUPPORTED_SAMPLE_RATES = frozenset({8000, 16000})

FRAME_MS = 32
START_PROBABILITY = 0.5
START_FRAMES = 3
END_PROBABILITY = 0.35
END_WINDOW_FRAMES = 20          # 32ms × 20 = 640ms
END_NONSPEECH_FRAMES = 16       # 80%
END_TRAILING_FRAMES = 3
# 약한 첫 음절은 확률 임계에 늦게 도달할 수 있다. -60dBFS 한국어 fixture는
# 약 1초 뒤 감지되므로 앞 1.2초를 보존해 첫 단어를 자르지 않는다.
# 엔진의 buffer_base가 이미 확정한 발화 쪽으로 되돌아가는 것은 막는다.
PRE_ROLL_MS = 1200


class SileroVadUnavailable(RuntimeError):
    """Silero를 선택할 수 없어 legacy VAD로 폴백해야 하는 상태."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


_session: Optional[Any] = None
_session_error: Optional[SileroVadUnavailable] = None
_session_lock = threading.Lock()


def _verified_model_path() -> Path:
    try:
        digest = hashlib.sha256(SILERO_MODEL_PATH.read_bytes()).hexdigest()
    except OSError as exc:
        raise SileroVadUnavailable(
            "model_unreadable", f"Silero VAD 모델을 읽지 못했습니다: {exc}"
        ) from exc
    if digest != SILERO_MODEL_SHA256:
        raise SileroVadUnavailable(
            "model_hash_mismatch",
            f"Silero VAD 모델 SHA-256 불일치: expected={SILERO_MODEL_SHA256} actual={digest}",
        )
    return SILERO_MODEL_PATH


def get_silero_session() -> Any:
    """검증된 CPU ONNX 세션을 프로세스당 한 번만 지연 생성한다."""
    global _session, _session_error

    if _session is not None:
        return _session
    if _session_error is not None:
        raise _session_error

    with _session_lock:
        if _session is not None:
            return _session
        if _session_error is not None:
            raise _session_error
        try:
            model_path = _verified_model_path()
            try:
                import onnxruntime as ort
            except (ImportError, OSError) as exc:
                raise SileroVadUnavailable(
                    "onnxruntime_unavailable", f"ONNX Runtime을 불러오지 못했습니다: {exc}"
                ) from exc

            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            _session = ort.InferenceSession(
                str(model_path),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
            logger.info(
                "Silero VAD ONNX 세션 로드 완료 version=%s model_sha256=%s",
                SILERO_MODEL_VERSION,
                SILERO_MODEL_SHA256,
            )
            return _session
        except SileroVadUnavailable as exc:
            _session_error = exc
            raise
        except Exception as exc:  # noqa: BLE001 — ORT의 플랫폼별 로드 오류를 폴백으로 변환
            error = SileroVadUnavailable(
                "model_load_failed", f"Silero VAD ONNX 세션 생성 실패: {type(exc).__name__}: {exc}"
            )
            _session_error = error
            raise error from exc


class SileroVadSegmenter:
    """32ms 프레임 기반 Silero streaming VAD.

    ``session`` 주입은 단위 테스트용이다. 운영 경로에서는 공유 세션을 가져오되,
    ``_state``와 ``_residue``는 항상 이 객체에만 존재한다.
    """

    def __init__(self, sample_rate: int, *, session: Optional[Any] = None) -> None:
        if sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise SileroVadUnavailable(
                "unsupported_sample_rate",
                f"Silero VAD는 8kHz/16kHz만 지원합니다: sample_rate={sample_rate}",
            )
        self.sample_rate = sample_rate
        self._session = session if session is not None else get_silero_session()
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        # 공식 OnnxWrapper와 동일하게 직전 프레임의 4ms를 다음 입력 앞에 붙인다.
        # ONNX graph의 외부 프레임 계약은 512/256 샘플이지만 실제 graph 입력은
        # 16kHz에서 64+512, 8kHz에서 32+256 샘플이다.
        self._context = np.zeros((1, 64 if sample_rate == 16000 else 32), dtype=np.float32)
        self._residue = b""
        self._consumed_bytes = 0
        self._last_end_bytes = 0
        self._voiced_run = 0
        self._in_speech = False
        self._end_window: Deque[bool] = deque(maxlen=END_WINDOW_FRAMES)

    @property
    def frame_bytes(self) -> int:
        return pcmutil.ms_to_bytes(FRAME_MS, self.sample_rate)

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def _probability(self, frame: bytes) -> float:
        samples = np.frombuffer(frame, dtype="<i2").astype(np.float32) / 32768.0
        model_input = np.concatenate((self._context, samples.reshape(1, -1)), axis=1)
        output, state = self._session.run(
            None,
            {
                "input": model_input,
                "state": self._state,
                "sr": np.asarray(self.sample_rate, dtype=np.int64),
            },
        )
        self._state = np.asarray(state, dtype=np.float32)
        self._context = model_input[:, -self._context.shape[1]:]
        return float(np.asarray(output).reshape(-1)[0])

    def push(self, pcm: bytes) -> List[pcmutil.VadEvent]:
        events: List[pcmutil.VadEvent] = []
        data = self._residue + pcm
        frame_bytes = self.frame_bytes
        frame_count = len(data) // frame_bytes
        if frame_count == 0:
            self._residue = data
            return events

        usable_bytes = frame_count * frame_bytes
        usable = data[:usable_bytes]
        self._residue = data[usable_bytes:]

        for index in range(frame_count):
            relative_start = index * frame_bytes
            frame_start = self._consumed_bytes + relative_start
            probability = self._probability(
                usable[relative_start:relative_start + frame_bytes]
            )

            if not self._in_speech:
                if probability >= START_PROBABILITY:
                    self._voiced_run += 1
                    if self._voiced_run >= START_FRAMES:
                        self._in_speech = True
                        voiced_began = frame_start - (self._voiced_run - 1) * frame_bytes
                        start = max(
                            self._last_end_bytes,
                            voiced_began
                            - pcmutil.ms_to_bytes(PRE_ROLL_MS, self.sample_rate),
                        )
                        events.append(pcmutil.VadEvent("speech_start", start))
                        self._end_window.clear()
                else:
                    self._voiced_run = 0
                continue

            non_speech = probability < END_PROBABILITY
            self._end_window.append(non_speech)
            if (
                len(self._end_window) == END_WINDOW_FRAMES
                and sum(self._end_window) >= END_NONSPEECH_FRAMES
                and all(list(self._end_window)[-END_TRAILING_FRAMES:])
            ):
                self._in_speech = False
                self._voiced_run = 0
                self._end_window.clear()
                self._last_end_bytes = frame_start + frame_bytes
                events.append(pcmutil.VadEvent("speech_end", self._last_end_bytes))

        self._consumed_bytes += usable_bytes
        return events

    def flush(self) -> List[pcmutil.VadEvent]:
        """End the current input interval and discard its acoustic state.

        An idle flush can happen before enough silence arrives to decay the
        recurrent state. Carrying that state into resumed noise can produce a
        false speech_start. Preserve the absolute byte offset, but reset only
        this stream's state/context/residue; the shared ONNX session stays loaded.
        """
        end = self._consumed_bytes + len(self._residue)
        events = [pcmutil.VadEvent("speech_end", end)] if self._in_speech else []
        self._in_speech = False
        self._voiced_run = 0
        self._end_window.clear()
        self._state.fill(0)
        self._context.fill(0)
        self._residue = b""
        self._consumed_bytes = end
        self._last_end_bytes = end
        return events


def _reset_session_cache_for_tests() -> None:
    """단위 테스트에서 로더 성공/실패를 격리한다. 운영 코드에서는 사용하지 않는다."""
    global _session, _session_error
    with _session_lock:
        _session = None
        _session_error = None
