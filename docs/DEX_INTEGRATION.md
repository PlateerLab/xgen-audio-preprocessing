# DEX 연결 및 사용

2026-10-17, `xgen-dex-core`의 현재 작업 트리에 연결했다. 커밋·설치 앱 교체는 하지 않았다.

## 사용

1. [개발자 설치 문서](DEVELOPER_INSTALL.md)에 따라 새 전용 환경에 설치한다.
2. 생성된 `env.sh`를 읽은 터미널에서 `xgen-dex-core/apps/desktop`의 개발 앱을 실행한다. `DEX_AUDIO_ROOT`는 설치 target을 가리킨다.
3. DEX **음성 설정 → DEX 소음 제거 / DEX 발화 감지(VAD)**를 각각 선택한다. 둘 다 기본 OFF이며 변경은 다음 마이크 캡처부터 적용된다.

VAD OFF는 **DEX의 Silero만 우회**한다. 실시간 XGEN 서버 VAD는 유지된다. 일반 마이크 버튼은 사용자가 중지하면 WAV를 전사한다. 로컬 VAD ON일 때 발화를 감지하지 못한 녹음은 보내지 않는다.

## 실제 경로

- 공통: 마이크 → PCM16/16kHz/mono/64ms → main IPC → Python `--jsonl` 워커 → 처리된 PCM/발화 이벤트 → renderer.
- 실시간 경로(`fastAct` ON): 처리된 PCM → main `VoiceStreamHub` → 인증된 `WS /api/audio/stt/stream` → XGEN Core → 모델 STT.
- 일반 아바타 핸즈프리: Silero ON은 모델, OFF는 기존 RMS로 발화 감지 → 발화별 WAV → 파일 STT. 오버레이에 workflow가 있고 `fastAct`가 ON이면 기존 실시간 분기를 사용한다.
- 일반 녹음: 워커 drain → WAV → 인증된 `POST /api/audio/stt/transcribe`.

브라우저 AEC 활성화와 noiseSuppression 비활성화를 요청한다. 실제 장치의 AEC 효과는 미검증이다. RNNoise만 사용자 소음 제거 스위치에 따라 동작한다. 둘 다 OFF이면 Python도 시작하지 않는다. 실시간 경로의 VAD ON에서 pre-roll은 1.2초, 종료 hold는 Silero 종료 후 1.2초, 발화 상한은 30초다. OFF에서는 서버 final 또는 30초 상한으로 실시간 세션을 마친다. 일반 핸즈프리는 기존 파일 STT를 유지하되 원음 MediaRecorder 대신 처리된 PCM으로 WAV를 만든다. Silero OFF의 RMS 기준은 0.015/시작 150ms/종료 900ms다.

worker는 캡처당 하나이며 JSONL request/reply를 직렬 처리한다. 4초 입력 큐와 10초 응답 제한을 넘으면 오류를 표시하고 마이크를 닫는다. 오류 뒤 원음으로 몰래 전환하지 않는다. 정상 종료는 Python finish를 기다려 마지막 PCM까지 전송하고, 취소/창 종료는 워커를 종료한다. WebSocket의 20ms 미만 끝 조각도 전송한다.

실제 서버에서 음성으로 바로 시작하는 샘플의 첫 인사말 누락을 재현했다. ready 후 입력 앞에 500ms 무음 프레임을 추가해 보정했고 원본 샘플로 재검증했다. 이 보정은 전송 오디오 앞부분이며 서버 VAD가 원인이라는 인과관계는 확인하지 않았다. 파일 STT에는 적용하지 않는다.

## 검증

- 실제 Python 워커 네 조합: PCM 길이, bypass 동일성, VAD 이벤트 ON/OFF, 마지막 샘플, 취소 통과.
- renderer 캡처: 순서, drain, TTS 중 무음, 오류 시 마이크 종료 통과.
- 실제 Electron 음성 설정: 독립 토글, 저장 성공/실패 표시 통과.
- 기존 DEX 로그인으로 개발 XGEN Core의 실시간/파일 API 호출. 깨끗한 한국어 샘플 네 조합 모두 `안녕하세요. 오늘 날씨가 정말 좋네요.`로 일치. 모델 서버 직접 호출만으로 대체하지 않았다.
- DEX 타입 검사와 Electron 빌드 통과. 상세 소음 비교는 DEX `apps/desktop/docs/audio-preprocessing.md` 참조.

## 설치 앱과 현장 범위

개발 체크아웃 인접 환경 또는 설치 스크립트의 전용 환경을 연결할 수 있다. 배포 앱에서는 `DEX_AUDIO_ROOT` 또는 앱 resources/audio-preprocessing의 별도 런타임이 필요하다. OS/CPU별 Python·ONNX Runtime·RNNoise 번들, 서명 및 설치 프로그램은 이번 작업 범위에 포함하지 않았다.

실제 마이크/스피커 AEC, COEX 현장, 30분 상시 청취, Windows/Linux 설치 앱은 검증하지 않았다. 소음 제거가 주변 사람의 발화를 선택적으로 제거하지는 않으며 작은 목소리 정확도는 나빠질 수 있다.
