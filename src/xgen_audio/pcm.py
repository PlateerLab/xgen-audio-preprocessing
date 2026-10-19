"""PCM16LE mono offsets shared with the extracted XGEN VAD."""
from dataclasses import dataclass
from typing import Literal


def ms_to_bytes(ms: float, sample_rate: int) -> int:
    return int(ms / 1000 * sample_rate) * 2


@dataclass(frozen=True)
class VadEvent:
    type: Literal["speech_start", "speech_end"]
    offset_bytes: int
