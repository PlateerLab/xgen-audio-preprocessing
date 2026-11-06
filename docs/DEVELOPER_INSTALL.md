# 개발자 설치와 DEX 연결

이 문서는 사내 개발자용이다. 공개 패키지 저장소에 게시하거나 DEX 설치 파일에 번들하는 절차는 아니다.
폴더 이름과 Python 패키지 이름은 `xgen-audio-preprocessing`, import는 `xgen_audio`다.

## 준비

- macOS 또는 Linux, Python **3.11.8 이상 3.11.x 또는 3.12.x**와 `venv`/`ensurepip`.
- `cc` C 컴파일러. macOS는 Xcode Command Line Tools, Linux는 C 빌드 도구와 Python venv 패키지가 필요하다.
- 설치 중 Python 패키지 저장소, GitHub RNNoise 소스, Xiph 모델 다운로드 접근.
- 실제 검증한 OS/CPU는 macOS ARM64. Linux는 스크립트 경로만 지원하며 실기 검증하지 않았다. Windows 설치는 지원하지 않는다.
- 기존 DEX 개발 환경과 XGEN 로그인은 별도다. 서버 계정에 STT가 활성화되어 있어야 실제 STT 검증을 할 수 있다.

## 설치

전달받은 소스 압축을 풀고 해당 폴더에서 실행한다. wheel 하나만 전달하면 RNNoise 빌드 스크립트가 없으므로 이 설치 절차에는 **소스 묶음**을 사용한다.

```sh
python3.11 scripts/install.py --target "$HOME/.local/share/xgen-audio/0.1.2"
source "$HOME/.local/share/xgen-audio/0.1.2/env.sh"
```

설치기는 기존 target이 있으면 중단한다. 기존 환경에 덮어쓰지 않는다. 업그레이드/재설치에는 새 경로를 지정한다.
실패 시 불완전한 target을 남기며, 출력된 원인을 해결하고 다른 새 target으로 재시도한다. 자동 삭제·시스템 Python 변경·sudo는 하지 않는다.

수행 내용:

1. target 안의 `.venv` 생성, 소스를 일반 wheel로 빌드하여 설치(editable 아님).
2. 고정 커밋과 SHA-256을 확인한 RNNoise 소스·모델 다운로드 및 `.local/rnnoise`에 빌드.
3. `pip check`, 소음 제거/VAD 네 조합의 모델 로드·무음 처리·출력 길이 확인.
4. DEX용 `env.sh`, 환경 정보 `install-info.json`, 실제 설치 버전 `installed-requirements.txt` 생성.

`env.sh`는 `DEX_AUDIO_ROOT`, `DEX_AUDIO_PYTHON`, `XGEN_RNNOISE_LIBRARY`를 설정한다. 경로에 공백이 있어도 사용할 수 있다.
설치된 패키지는 소스 폴더 없이 실행할 수 있지만 **Python 본체는 계속 필요**하다. `.venv`를 다른 PC에 복사하거나 target을 이동하지 말고 각 PC에서 설치한다.
의존성은 `pyproject.toml` 범위에서 설치 시 해결되므로 향후 버전이 달라질 수 있다. 실행 환경의 정확한 버전은 생성된 `installed-requirements.txt`로 확인한다.
로컬 Whisper 평가 도구는 설치하지 않는다. DEX의 RNNoise/Silero 연결에 필요하지 않다.

## DEX 실행

DEX 오디오 연결 코드가 포함된 버전에서 실행한다. `env.sh`는 **앱을 시작하는 터미널**에서 읽어야 한다. 이미 실행 중인 앱에는 적용되지 않는다.

```sh
source "$HOME/.local/share/xgen-audio/0.1.2/env.sh"
cd /path/to/xgen-dex-core/apps/desktop
npm run dev
```

설정 → 아바타 설정 → 음성(STT/TTS) 관리에서 **DEX 소음 제거**와 **DEX Silero 발화 감지(VAD)**를 선택한다. 마이크를 껐다 켜면 적용된다.

- 일반 녹음: 사용자가 중지하면 처리된 PCM을 WAV로 만들어 파일 STT에 보낸다.
- 아바타 핸즈프리 기본 경로: Silero ON은 모델 감지, OFF는 기존 RMS 감지를 사용해 발화별 WAV를 파일 STT에 보낸다.
- `fastAct` ON 및 에이전트가 선택된 실시간 경로: 처리된 PCM을 WebSocket으로 보낸다. 현재 UI의 설정 이름은 **단계별 브라우저 조작(실험)**이다. Silero OFF에서는 RMS 대신 서버의 발화 종료 결과를 사용한다.

터미널에서 `ready`에 `noise:"rnnoise", vad:"silero"`, `pcm-active`에 `noise:true, vad:true`가 나오면 두 옵션으로 PCM 처리가 시작된 것이다.
`speech_start/end`는 로컬 Silero 이벤트이고, `voice-stream start/end`는 실시간 세션과 STT 결과다. RNNoise 사용 로그가 인식률 향상까지 입증하는 것은 아니다.

## 실제 서버 검증 (선택)

다음은 **별도로 준비한 한국어 샘플을 로그인된 DEX의 XGEN 서버로 전송**한다. 마이크를 켜거나 채팅/브라우저 조작을 실행하지 않는다. STT 사용량은 발생할 수 있다.
DEX의 Node 의존성이 설치되어 있어야 하며 `DEX_PROFILE`을 사용하는 계정은 동일 값을 지정한다. 토큰을 문서나 명령에 복사하지 않는다.
아래 `AUDIO_SOURCE`는 압축을 푼 소스 폴더의 절대 경로로 바꾼다.

```sh
source "$HOME/.local/share/xgen-audio/0.1.2/env.sh"
AUDIO_SOURCE=/path/to/xgen-audio-preprocessing
cd /path/to/xgen-dex-core/apps/desktop

# 실제 DEX AudioProcessor + VoiceStreamHub, WS 4회 및 파일 STT 4회
DEX_AUDIO_REAL_STT=1 DEX_AUDIO_FIXTURE="$AUDIO_SOURCE/tests/fixtures/speech.wav" \
  ./node_modules/.bin/electron -r tsx/cjs verify/audio-stt-smoke.cjs

# 실제 handsfree React 훅 + 모의 마이크 + 새 Python 런타임 + 파일 STT 4회
DEX_AUDIO_REAL_STT=1 DEX_AUDIO_FIXTURE="$AUDIO_SOURCE/tests/fixtures/speech.wav" \
  ./node_modules/.bin/electron -r tsx/cjs verify/handsfree-smoke.cjs
```

첫 검증은 `voice-loop`의 발화 구간 판단을 우회한다. 두 번째는 파일 핸즈프리의 구간 판단을 검증하지만 물리 마이크를 사용하지 않는다.
핸즈프리 검증은 원본 샘플이 RMS 시작 조건보다 작아서 **샘플만 4배 증폭**한다. 앱의 게인·임계값은 바꾸지 않는다.

검증 결과: [2026-10-18 깨끗한 환경 설치 검증](INSTALL_VALIDATION.md).

## 오류와 배포 범위

- `C compiler missing`: 컴파일러를 준비한 뒤 새 target으로 재시도.
- `No module named venv`/`ensurepip`: venv가 제공되는 Python으로 실행.
- 다운로드·해시 검사 실패: 네트워크/다운로드 출처 확인. 해시 검사를 끄지 않는다.
- DEX 실행 파일 없음: `env.sh`를 읽은 터미널에서 DEX를 완전히 재시작했는지 확인.
- STT 401/403 또는 로그인 없음: 해당 DEX 프로필에서 로그인 및 서버 STT 권한 확인.

RNNoise/Silero 모델 및 의존성 고지는 `src/xgen_audio/licenses/`와 `src/xgen_audio/models/`에 있다.
이 라이브러리 자체의 공개 배포 라이선스는 아직 지정하지 않았다. 공개 PyPI 게시 전에 별도로 결정해야 한다.
설치 앱 번들·코드 서명·COEX 현장 정확도·장시간 마이크 검증은 이 개발자 설치 범위에 포함하지 않는다.
