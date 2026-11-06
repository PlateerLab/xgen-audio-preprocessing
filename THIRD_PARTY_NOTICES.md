# 제3자 라이선스 고지

이 프로젝트 자체는 Apache-2.0([LICENSE](LICENSE))이며, 아래 구성요소는 각자의 라이선스를 따른다. 법률 자문이 아니라 고지 목록이다.

## 패키지에 포함되는 것

| 구성요소 | 라이선스 | 원문 위치 | 비고 |
|---|---|---|---|
| Silero VAD 모델 6.2.1 (`silero_vad_v6.2.1.onnx`) | MIT | `src/xgen_audio/models/silero_vad_v6.2.1.LICENSE.txt` | 저작권 © 2020-present Silero Team. 로드 전 SHA-256 검사 |

## 설치 시 내려받아 빌드하는 것

| 구성요소 | 라이선스 | 원문 위치 | 비고 |
|---|---|---|---|
| RNNoise (소스 + 공식 모델 weights) | BSD-3-Clause (소스 `COPYING` 은 동봉본과 동일함을 확인. weights 압축본에는 별도 라이선스 파일이 없다. 업스트림 README 는 배포 모델이 공개 데이터셋(`datasets.txt`)만으로 학습됐다고 밝히는데, 그 OpenSLR 데이터셋 27종의 라이선스를 각 페이지에서 확인한 결과 26종이 **CC BY-SA 4.0**, hi_fi_tts 1종이 CC BY 4.0 이다(2026-11-06). 학습 가중치가 이 데이터의 파생물로서 ShareAlike 의무를 지는지는 이 문서가 판단하지 않으며, Xiph 는 weights 를 저장소와 같은 BSD-3 로 배포한다. 노이즈 학습 데이터(Xiph 제공)는 확인하지 않음) | `src/xgen_audio/licenses/RNNoise-COPYING.txt` | `scripts/build_rnnoise.py`가 고정 커밋·해시로 빌드. 빌드한 `librnnoise`를 앱에 함께 배포하면 이 고지를 같이 넣을 것 |

## 의존성 (pip 이 설치)

| 구성요소 | 라이선스 | 비고 |
|---|---|---|
| numpy | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (2.4.6 wheel 메타데이터) | 2.4.6 cp311 wheel 의 파일 목록과 `LICENSE.txt` 를 확인(2026-11-06): **Linux x86_64(manylinux·musllinux)와 macOS 11+ x86_64/arm64 wheel 은 libquadmath(LGPL-2.1+)를 번들**하고, Linux aarch64·musllinux 는 libgfortran/libgcc/libstdc++(GPL-3.0+ WITH GCC-exception)를 번들한다. Windows amd64/arm64 wheel 은 OpenBLAS(BSD-3)와 MSVC 런타임(msvcp140.dll)만 번들하며 LGPL 라이브러리는 없다. macOS 14+ wheel(Accelerate 사용)과 win32 는 번들 라이브러리가 없다. 런타임을 앱에 묶어 배포하면 wheel 의 `LICENSE.txt` 전체를 유지하고 번들 라이브러리를 교체 가능하게 둔다 |
| onnxruntime | MIT (1.31.0 확인) | wheel 에 `LICENSE`, `ThirdPartyNotices.txt` 포함. 앱에 묶어 배포하면 두 파일을 유지 |

## 선택 extra / 개발 전용 (배포 대상 아님)

| 구성요소 | 상태 |
|---|---|
| scipy, soundfile, pytest (`[test]` extra) | 테스트 전용. 제품 배포물에 포함하지 않는다 |
| faster-whisper (`[asr-eval]` extra) | 전사 비교(`scripts/benchmark.py --asr-model`) 전용. 의존하는 PyAV(`av`)의 wheel 이 FFmpeg 와 함께 **libx264·libx265(GPL)를 번들**한다(번들 libavcodec 은 LGPL 3+ 로 표시되어 라이선스 상태 미확정). 이 extra 와 `requirements-validation.lock` 환경은 평가 전용이며 앱·wheel 에 넣지 않는다 |

## 리샘플러

16 kHz ↔ 48 kHz 변환은 자체 구현(`src/xgen_audio/resample.py`, numpy 전용 polyphase 필터)이며 외부 리샘플 라이브러리에 의존하지 않는다. 이전 빌드(dist 의 0.1.1 배포물)가 쓰던 soxr(LGPL-2.1+)은 제거했으므로 LGPL 의무는 없다.

## 테스트 데이터

음성 WAV 는 저장소와 wheel 에 포함하지 않는다. 비교에 쓴 Rikorose/DeepFilterNet 저장소의 샘플 중 CC BY-NC 3.0(`clean33711`)은 번들에서 제외했고, CC BY 3.0(noise2530)은 출처 표기를 유지한다. 자세한 내용은 [docs/RESEARCH.md](docs/RESEARCH.md).
