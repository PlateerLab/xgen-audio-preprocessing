# XGEN Audio Preprocessing

실시간 마이크 PCM을 위한 독립 Python 라이브러리. 폴더 이름은 요청한 `xgen-audio-preprecessing`, Python 배포 이름은 `xgen-audio-preprocessing`, import는 `xgen_audio`입니다.

**현재 권장 기본값은 Silero VAD + 소음 제거 OFF입니다.** RNNoise/DeepFilterNet은 선택적으로 켤 수 있습니다. 잡음이 줄어도 STT가 좋아지는 것은 아니며, 이번 한국어 실험에서는 두 필터 모두 일부 인식을 악화시켰습니다. [실측 결과](docs/VALIDATION.md), [DEX 연결 계획](docs/DEX_INTEGRATION.md), [후보·라이선스 조사](docs/RESEARCH.md)를 먼저 확인하세요.

## 개발자 설치

macOS/Linux용 설치 스크립트가 새 전용 환경에 패키지·RNNoise를 설치하고 네 가지 옵션 조합을 점검합니다. Python 3.11.8+ 또는 3.12와 C 컴파일러가 필요합니다.

```sh
python3.11 scripts/install.py --target "$HOME/.local/share/xgen-audio/0.1.1"
source "$HOME/.local/share/xgen-audio/0.1.1/env.sh"
```

기존 target에는 덮어쓰지 않습니다. 실제 검증 플랫폼은 macOS ARM64이며 Windows 설치는 지원하지 않습니다.
**[개발자 설치·DEX 연결·실제 STT 검증](docs/DEVELOPER_INSTALL.md)**에서 상세 절차와 오류 대응을 확인하세요.

Silero 모델 6.2.1은 패키지에 포함되고 로드 전에 SHA-256을 검사합니다. 실행 중 모델을 자동 다운로드하지 않습니다. RNNoise 소스와 모델은 설치할 때 고정된 해시로 다운로드·빌드합니다.
DeepFilterNet은 실험용 optional extra이며 기본 설치에서 제외합니다. 선택한 필터가 없으면 명확하게 실패하며 다른 필터로 조용히 전환하지 않습니다.

소스 개발용 editable 설치나 로컬 Whisper 평가가 필요한 경우에만 별도 개발 환경에서 `pip install -e '.[test,deepfilter]'`를 사용하세요. 기본 설치 경로의 환경을 재사용하지 마세요.

## Python API

```python
from xgen_audio import AudioPreprocessor

# 한 마이크 캡처당 한 객체. 생성·push·finish·close는 동일 스레드에서 수행.
with AudioPreprocessor(sample_rate=16000, denoise="rnnoise") as stream:
    for pcm16_bytes in microphone_chunks:
        result = stream.push(pcm16_bytes)
        send_to_stt(result.pcm)
        for event in result.events:
            handle_vad(event.type, event.offset_bytes)
    tail = stream.finish()
    send_to_stt(tail.pcm)  # 반드시 upstream stop보다 먼저 전달
    for event in tail.events:
        handle_vad(event.type, event.offset_bytes)
```

`denoise`: `none`(기본), `rnnoise`, `deepfilter`(실험). 입력은 16kHz 또는 48kHz, mono, signed PCM16LE raw bytes입니다. 출력은 항상 16kHz mono PCM16LE입니다. WAV/WebM/Opus 컨테이너와 stereo는 지원하지 않으므로 입력 경계에서 먼저 디코딩해야 합니다.

`push`는 불규칙·홀수 바이트 청크도 보관하여 샘플을 보존합니다. EOF에 홀수 바이트가 남으면 손상된 PCM으로 실패합니다. `finish`는 필터 지연과 마지막 부분 프레임을 배출하고 한 번만 결과를 냅니다. 정상 종료는 finish, 취소는 close입니다. 출력 전체 샘플 수는 입력 시간에 맞고 패딩은 외부에 노출하지 않습니다.

오디오는 무음까지 **연속 출력**합니다. VAD는 출력 PCM 기준 절대 바이트 위치의 `speech_start`/`speech_end` 이벤트를 제공합니다. 시작에는 1.2초 pre-roll이 포함됩니다. 이전 발화 종료보다 과거로 돌아가는 시작은 제한하므로 이벤트를 이용한 자르기에서 중복 구간이 생기지 않습니다. 이벤트가 발생하는 시각과 과거를 가리키는 offset은 다릅니다. 끝점은 640ms 창 기반이며 감지 지연이 존재합니다.

## Node / DEX 연결

`examples/dex-preprocessor.mjs`는 Electron main에서 사용할 자식 프로세스 연결 예제입니다. stdout은 PCM 전용, stderr는 ready/VAD JSON 및 진단입니다. Python 워커의 stdout 청크 경계는 원래 입력 청크와 같지 않습니다. downstream에서 재조립하고 마지막 640바이트 미만 조각도 보내야 합니다.

```sh
.venv/bin/python -m xgen_audio.cli --denoise rnnoise --events < input.pcm > clean.pcm
```

예제는 ready 이벤트, backpressure 대기, 정상 종료 drain, 취소를 제공합니다. 이 예제는 raw PCM 모드용입니다. 현재 DEX UI는 별도의 JSONL 워커 연결을 사용합니다. 실제 경로는 [DEX 연결 문서](docs/DEX_INTEGRATION.md)를 참조하세요.

## 재검증

다음은 소스 작업용 별도 환경이다. 개발자 설치 target은 그대로 둔다.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[test,deepfilter]'
.venv/bin/python scripts/build_rnnoise.py
# macOS 기준. Linux는 librnnoise.so로 지정.
export XGEN_RNNOISE_LIBRARY="$PWD/.local/rnnoise/librnnoise.dylib"
.venv/bin/python -m pytest -q
.venv/bin/python scripts/fetch_samples.py
.venv/bin/python scripts/benchmark.py --data artifacts/samples --backend rnnoise --output artifacts/rnnoise
.venv/bin/python scripts/benchmark.py --data artifacts/samples --backend deepfilter --output artifacts/deepfilter
# 실제 전사 비교는 --asr-model /path/to/local/faster-whisper-small 추가
# requirements-validation.lock은 이번 macOS Python 3.11 실험의 정확한 패키지 버전 기록
```

`artifacts/`는 로컬 검증 결과이며 wheel에 포함되지 않습니다. `docs/VALIDATION.md`에 정확한 실행 범위와 실패·제약을 기록했습니다. Git 초기화·브랜치 생성·add·commit·push는 수행하지 않았습니다.

## DEX 연결 (2026-10-17)

현재 DEX 작업 트리에 실시간·일반 녹음 전처리를 연결했습니다. [설정과 검증 범위](docs/DEX_INTEGRATION.md)를 참조하세요.

`AudioPreprocessor(denoise="rnnoise", vad=False)`로 로컬 VAD만 끌 수 있습니다. CLI는 `--no-vad`를 지원합니다. DEX는 `--jsonl`의 ready → push(base64 PCM) → audio(PCM/events/inSpeech) → finish 프로토콜을 사용합니다. 한 push는 최대 64,000 bytes이며 정상 종료에 finish가 필요합니다. 원래 stdin/stdout PCM 모드도 유지됩니다.

개발자 설치 스크립트와 새 환경 실제 STT 검증 결과는 [INSTALL_VALIDATION.md](docs/INSTALL_VALIDATION.md)를 참조하세요.

## 테스트 음성 준비

음성 WAV는 저장소에 포함하지 않습니다. 음성을 사용하는 테스트·벤치마크·STT 검증 전 [로컬 샘플 준비 안내](tests/fixtures/README.md)를 확인하세요.

## 라이선스

**Apache License 2.0** — [LICENSE](LICENSE) / [NOTICE](NOTICE) 참조. 재배포 시 저작권·라이선스 고지와 `NOTICE`를 유지해야 합니다.

- 제3자 구성요소(Silero VAD 모델 MIT, RNNoise BSD-3-Clause, numpy BSD, onnxruntime MIT)의 고지는 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 정리했습니다. 리샘플러는 자체 구현이라 LGPL 의존성이 없습니다.
- DeepFilterNet-rs(`[deepfilter]` extra)는 래퍼의 라이선스가 확정되지 않아 제품 배포 대상에서 제외합니다.
- 테스트용 음성 파일은 저장소에 포함하지 않습니다.
