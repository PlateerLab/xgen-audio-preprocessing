# 개발자 설치 검증 — 2026-10-18

## 범위

macOS ARM64, Python 3.11.16에서 실행했다. 기존 라이브러리 `.venv`, `.local`, 빌드 결과를 복사하지 않고 **소스만 임시 디렉터리에 복사**했다.
그 소스의 `scripts/install.py`로 공백이 포함된 새 target에 설치했다. pip 다운로드 캐시는 사용하지 않았고, RNNoise 소스·모델도 새로 내려받아 빌드했다.

이는 **깨끗한 Python/RNNoise 환경** 검증이다. 새 OS/VM은 아니며 호스트 Python·C 컴파일러, 기존 DEX 체크아웃/Node 의존성, 로그인된 XGEN 계정을 사용했다.
검증 중 현재 실행 중인 DEX 앱 설정·프로세스를 변경하지 않았다. 별도 Electron 검증 프로세스에서 새 런타임을 지정했다.

## 결과

- 비-editable 패키지 설치, `pip check`, RNNoise 로드, 번들 Silero 모델 로드 성공.
- Python import 경로가 새 target의 `site-packages`임을 확인했다.
- 무음 PCM 네 옵션 조합에서 출력 길이 보존·발화 이벤트 없음 확인.
- 같은 target에 재설치 시 exit 2로 거부하고 기존 `env.sh`가 바뀌지 않음 확인.
- DEX `AudioProcessor` → 새 Python 워커 → `VoiceStreamHub` → 실제 Core WebSocket STT: **4/4 성공**.
- 처리된 PCM → WAV → 실제 Core 파일 STT: **4/4 성공**.
- 실제 React `useHandsfree` + 모의 마이크 + 새 Python 워커 → 실제 Core 파일 STT: **4/4 성공**. 발화당 업로드 1회, WebSocket 시작 0회, VAD ON에서 시작·종료 이벤트 확인, OFF에서 이벤트 0회.

각 4회는 소음 제거 OFF/ON × Silero OFF/ON 조합이다. 12개 STT 결과 모두 **“안녕하세요. 오늘 날씨가 정말 좋네요.”**와 일치했다.
핸즈프리 입력은 기존 RMS 기준을 통과하도록 테스트 음성만 4배 증폭했다. 앱의 게인·감지 임계값은 변경하지 않았다.

실제 서버와 별개인 mock-STT 회귀 실행에서도 녹음 취소, 중지 후 늦은 응답 차단, 30초 파일 상한, STT 실패 후 오류 표시·대기 복귀가 모두 통과했다. 이 실행도 같은 새 Python/RNNoise 환경을 사용했다.

## 설치된 버전

- xgen-audio-preprocessing 0.1.1
- numpy 2.4.6, onnxruntime 1.31.0, soxr 1.1.0
- flatbuffers 25.12.19, packaging 26.3, protobuf 7.36.2
- RNNoise 커밋: `70f1d256acd4b34a572f999a05c87bf00b67730d`

의존성을 고정한 전 플랫폼 lockfile이 아니라 이번 설치의 실측 버전이다. 설치마다 `installed-requirements.txt`가 생성된다.

## 확인하지 않은 것

- 이번 새 환경 검증은 공개 샘플/모의 마이크를 사용했다. 물리 마이크·AEC·COEX 소음 성능은 확인하지 않았다.
- WebSocket 검증은 실제 DEX 전송 코드를 사용하지만 renderer `voice-loop`의 구간 판단을 우회한다. 전체 앱 UI E2E로 보지 않는다.
- Linux/Windows, 다른 CPU, 설치 앱 번들·서명, 30분 상시 청취는 미검증.
- RNNoise와 Silero는 특정 화자의 목소리만 골라내는 기능이 아니다. 인식률 향상을 이번 결과로 주장하지 않는다.

재현 명령과 설치 전제는 [개발자 설치 문서](DEVELOPER_INSTALL.md)에 있다.
