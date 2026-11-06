# 제3자 라이선스 고지

이 프로젝트 자체는 Apache-2.0([LICENSE](LICENSE))이며, 아래 구성요소는 각자의 라이선스를 따른다. 법률 자문이 아니라 고지 목록이다.

## 패키지에 포함되는 것

| 구성요소 | 라이선스 | 원문 위치 | 비고 |
|---|---|---|---|
| Silero VAD 모델 6.2.1 (`silero_vad_v6.2.1.onnx`) | MIT | `src/xgen_audio/models/silero_vad_v6.2.1.LICENSE.txt` | 저작권 © 2020-present Silero Team. 로드 전 SHA-256 검사 |

## 설치 시 내려받아 빌드하는 것

| 구성요소 | 라이선스 | 원문 위치 | 비고 |
|---|---|---|---|
| RNNoise (소스 + 공식 모델 weights) | BSD-3-Clause | `src/xgen_audio/licenses/RNNoise-COPYING.txt` | `scripts/build_rnnoise.py`가 고정 커밋·해시로 빌드. 빌드한 `librnnoise`를 앱에 함께 배포하면 이 고지를 같이 넣을 것 |

## 의존성 (pip 이 설치)

| 구성요소 | 라이선스 | 비고 |
|---|---|---|
| numpy | BSD-3-Clause | wheel 에 OpenBLAS 등 번들 고지 포함. 런타임을 앱에 묶어 배포하면 해당 고지를 유지 |
| onnxruntime | MIT | wheel 에 third-party 고지 포함. 위와 동일 |

## 선택 extra / 개발 전용 (배포 대상 아님)

| 구성요소 | 상태 |
|---|---|
| deepfilternet-rs (`[deepfilter]` extra) | 래퍼에 LICENSE 파일이 없고 GitHub 라이선스가 비어 있음(PyPI 는 MIT 표기). **제품 배포물에 포함하지 않는다.** 상위 DeepFilterNet 은 MIT 또는 Apache-2.0 |
| faster-whisper, scipy, soundfile, pytest (`[test]` extra) | 테스트 전용. `requirements-validation.lock` 환경(PyAV 등 FFmpeg 번들 패키지 포함)을 제품에 가져가지 않는다 |

## 리샘플러

16 kHz ↔ 48 kHz 변환은 자체 구현(`src/xgen_audio/resample.py`, numpy 전용 polyphase 필터)이며 외부 리샘플 라이브러리에 의존하지 않는다. 이전 빌드(dist 의 0.1.1 배포물)가 쓰던 soxr(LGPL-2.1+)은 제거했으므로 LGPL 의무는 없다.

## 테스트 데이터

음성 WAV 는 저장소와 wheel 에 포함하지 않는다. 비교에 쓴 DeepFilterNet 샘플 중 CC BY-NC 3.0(`clean33711`)은 번들에서 제외했고, CC BY 3.0(noise2530)은 출처 표기를 유지한다. 자세한 내용은 [docs/RESEARCH.md](docs/RESEARCH.md).
