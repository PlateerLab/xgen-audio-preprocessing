> 추가 검증 (2026-10-17): DEX 작업 트리에 연결 후 기존 로그인으로 Core WebSocket·파일 STT까지 검증했습니다. 깨끗한 한국어/행사장 소음 0dB 각 네 조합, WS 8회 + 파일 8회 모두 전체 문장 일치. 첫 인사말 누락은 DEX 시작부 500ms 무음 보정 후 재검증했습니다. 라이브러리 63 tests + 5 subtests, DEX 25 tests 통과. 아래는 이전 라이브러리 단독 검증 기록이며, 최신 연결·제약은 [DEX_INTEGRATION.md](DEX_INTEGRATION.md)를 참조하세요.

# 검증 결과: 시연 기본값은 Silero + denoise none

2026-10-16~17 KST, macOS arm64 / Python3.11.16, CPU. 라이브 마이크 대신 공개·합성 WAV를 64ms PCM으로 replay했다. 결과는 **구현이 동작한다는 근거**이며 코엑스 현장 정확도를 입증하지 않는다.

## 실제 인식 비교

한국어1개 합성 문장 + 영어1개 공개 발화. 각 문장에 clean, 공개 소음2종/대화 간섭/white 각각10dB와0dB를 적용했다. 총18가지 조건, 원음·RNNoise·DFN3를 비교했다. CER는 공백·문장부호를 제거하고 소문자화한 character edit distance / reference length이며 삽입이 많으면100%를 넘는다. 아래는 조건별 CER의 단순 평균이다. 한 문장을 여러 소음으로 변형한 결과라 독립적인 대규모 표본이 아니다.

| 인식기·입력 | 필터 없음 | RNNoise | DeepFilterNet |
|---|---:|---:|---:|
| Whisper-small 한국어 | 6.67% | 8.15% | 11.85% |
| Whisper-small 영어 | 29.85% | 17.67% | 26.24% |
| 개발 Qwen3-ASR-1.7B 한국어 | 0.00% | 3.70% | 0.00% |

Qwen은 백색소음0dB의 RNNoise 처리본에서 “정말 좋네요”를 “상당히 쨍해요”로 인식(CER33.33%)했고, 나머지8조건은 CER0%. DFN3는 이9조건에서 CER0%였으나 별도의 -60dBFS quiet fixture에서 **Silero 시작 이벤트 자체가 사라졌다**. 따라서 한국어 성능 향상을 달성했다고 주장하지 않고, 두 필터 모두 opt-in으로 제공한다.

원자료: [Whisper RNNoise](../artifacts/whisper/results.json), [Whisper DFN3](../artifacts/deepfilter/results.json), [Qwen RNNoise](../artifacts/qwen-results.json), [Qwen DFN3](../artifacts/qwen-deepfilter-results.json), [짧은 응답/작은 음성](../artifacts/short-quiet.json). WAV 전후 파일도 각 artifacts 폴더에 있다.

## 처리 속도와 지연

초기 모델 로드 이후, 64ms push의 p95가 RNNoise는 약4.5ms 이하, DFN3는 약3.2ms 이하였고 처리시간/오디오시간 비율(RTF)은 각각 약0.05/0.03이었다. ASR 시간·프로세스 시작·OS 오디오 지연을 포함하지 않은 CPU 전처리 수치다. 기본 scalar RNNoise 빌드이며 다른 하드웨어 보장은 아니다.

16kHz 입력64ms 청크에서 최초 PCM 출력은 필터 없음64ms, 두 필터128ms였다. RNNoise 자체 overlap delay10ms, 고정 DFN3 delay30ms 외에 up/down SoXR buffering과 입력청크 크기가 포함된다. 파이프라인은 EOF 때 지연을 배출하고 시작 지연을 보정하여 output sample count를 보존한다. VAD endpoint의640ms 창은 이 처리시간과 별개다.

잡음 단독8초, 시작1초 제외 RMS 기준 RNNoise 감소량: 공개2530 37.4dB, 공개573577 37.7dB, white36.4dB. DFN3는23.3/4.7/51.0dB. **이 숫자는 발화 혼합물 SNR 개선이나 음성 정확도가 아니다.** 경쟁 음성은 약2.8~2.9dB만 줄었고 VAD 이벤트도 남는다. generic denoising으로 옆사람 말이 제거된다고 가정하면 안 된다.

## 자동 검증

- pytest: 55 passed, 5 subtests. Silero 실제 ONNX inference, 8/16kHz VAD, 정상/작은 발화/짧은 네·아니요, 프레임 분할, 상태 분리, flush/reset 및 pre-roll 비중복.
- pipeline:16/48kHz 입력, 0/1sample/부분 프레임, 홀수 byte transport, EOF 손상 오류, chunk invariance, RNNoise 동시 독립 세션, DFN3 tail 보존, 기본 bypass byte identity, 잘못된 backend/누락 library.
- Node 실제 subprocess 왕복:158,288bytes 입력/출력 일치,20ms 패킷248개, speech_start/end 존재, 오류0. 마지막20ms 미만 조각을 포함. Python 직접 실행 결과와 byte-identical. [실행 예제](../examples/test-dex-preprocessor.mjs).
- 실제 XGEN engine 경로: 현재 xgen-model `SttStreamEngine` 원본 코드를 임시 Python에서 import, GPU process-manager 초기화만 제외. 처리된 음성을 wall-clock64ms로 공급하고 개발 Qwen REST에 실제3회 전사 요청. RNNoise·DFN3 모두 partial/final이 생성됐고 최종 “안녕하세요. 오늘 날씨가 정말 좋네요.”, error0. [RNNoise](../artifacts/xgen-engine-rnnoise.json), [DFN3](../artifacts/xgen-engine-deepfilter.json).

마지막 경로는 **실제 엔진+실제 ASR 통합 검증**이다. 인증된 Core WebSocket·Electron UI까지 포함한 full product E2E가 아니다. Python callback이나 STT 응답을 mock하지 않았지만 app bootstrap, ingress, auth, renderer는 검증 경계 밖이다.

## 재현

README의 설치/빌드 후 `scripts/benchmark.py`를 실행한다. local ASR은 `Systran/faster-whisper-small` snapshot `536b0662742c02347bc0e980a01041f333bce120`, CPU int8/4threads/beam1/temperature0/condition_on_previous_text=false/vad_filter=false로 사용했다. 모델 다운로드는 약464MiB였다. 새로운 noisy WAV를 전송할 때는 명시적으로 `scripts/test_remote_asr.py --base-url ... --benchmark ... --output ...`를 실행한다.

개발 Qwen은 검증자가 접근 권한을 가진 개발 ASR 엔드포인트의 모델 목록에서 선택했다. 서버 주소는 공개 문서에 포함하지 않는다. 전사 결과 파일에 정확한 모델 ID가 있다. 임의의 API키/사용자 음성/설정을 복사하지 않았다. 개발 STT 모델 상태가 바뀌면 결과가 달라질 수 있다.

## 미검증과 남은 위험

실제 COEX 음향·다화자 한국어 corpus·실제 마이크·브라우저 AEC/NS 중복처리·Electron 설치패키지·장시간 전력/메모리·Linux/Windows 실행은 검증하지 않았다. native Linux 빌드 경로는 제공하지만 이 머신에서 실행하지 않았다. 모델 성능 한계와 DFN3 래퍼 라이선스 고지 부족을 포함해 [후보 조사](RESEARCH.md)와 [DEX 연결 계획](DEX_INTEGRATION.md)에 기록했다.

권장 다음 적용은 기본 Silero only를 유지하며 실제 현장 녹음으로 RNNoise opt-in을 A/B 측정하는 것이다. DFN3는 quiet miss와 배포 고지 문제가 해소되기 전 시연 기본값으로 채택하지 않는다. Git/기존 저장소/서버 배포는 변경하지 않았다.
