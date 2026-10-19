# 후보 조사와 상업 사용 조건

조회: 2026-10-16~17 KST. GitHub API 응답은 `research/*-metadata.json`에 보관했다. 아래 숫자는 조사 시점이며, open_issues_count에는 PR도 포함된다.

| 후보 | stars / forks | 최근 기본 브랜치 커밋 | 판단 |
|---|---:|---|---|
| [Silero VAD](https://github.com/snakers4/silero-vad) | 10,448 / 874 | 2026-09-29 `1e261b0` | MIT, 8/16kHz, CPU ONNX. 기존 XGEN 6.2.1 모델·동작 재사용 |
| [RNNoise](https://github.com/xiph/rnnoise) | 5,897 / 1,082 | 2025-02-22 `70f1d25` | BSD-3-Clause, C, 48kHz/480샘플. 구현·실측 완료, opt-in |
| [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | 4,834 / 534 | 2024-10-17 `d375b2d` | MIT OR Apache-2.0, Rust/PyTorch, 48kHz. 공식 Python 파일처리를 청크별 호출하는 방식은 피함 |
| [DeepFilterNet-rs](https://github.com/di-osc/DeepFilterNet-rs) | 2 / 0 | 2026-05-13 `1462af0` | 0.1.1 스트리밍 Rust 래퍼, MIT로 PyPI 선언. 실험 전용, 아래 위험 참조 |

## 유지보수와 설치

RNNoise GitHub는 공식 Xiph GitLab의 미러이며 기본 브랜치 157 commits가 표시되었다. open items207(페이지 기준 issues183 + PR24). 최근 issue 업데이트2026-10-11, PR2026-09-04. 최근 문의가 있다고 최근 코드 개선이 있다는 뜻은 아니다. macOS/Linux는 C 컴파일러와 공식 모델 다운로드가 필요하다. 이 프로젝트는 autotools 대신 upstream Makefile의10개 C 파일을 scalar shared library로 빌드한다. x86 SIMD 최적화는 넣지 않았으므로 서버 성능은 별도 측정해야 한다. Windows C ABI는 가능하지만 제공 빌드 스크립트는 macOS/Linux 전용이다.

DeepFilterNet 기본 브랜치1,602 commits, open67(issues22 + PR45). 최근 issue2026-09-29, PR2026-09-08. 기본 브랜치 마지막 변경이2024년이라 신형 Python/PyTorch 호환과 유지보수 부담이 있다. 공식 Python package는 torch/torchaudio와 Rust extension이 필요하다. 공식 실시간 Rust 경로를 쓰는 별도 래퍼를 시험했다.

Silero open16(PR포함), 2026-09-29에 여러 PR merge, 최근 PR/issue2026-10-06. 설치는 numpy+onnxruntime이며 모델6.2.1 파일을 기존 XGEN에서 그대로 포함했다. 본 환경은 macOS arm64 CPU, Linux/Windows ONNX wheels는 존재하지만 이 작업에서 실행하지 않았다.

DeepFilterNet-rs는 Python3.10~3.12의 macOS arm64/Linux x86_64/Windows x86_64 wheels를 제공한다. Python3.13 이상은 제외한다. 공개 저장소 open issues/PR0, 매우 작은 프로젝트이며 PyPI는 Alpha로 표기한다. **v0.1.1 finalize가 모델 delay tail을 배출하지 않아 입력 끝부분을 잃는 문제를 소스에서 확인했다.** 고정 DFN3의 `(fft960-hop480)+lookahead2*480 = 1440 samples`를 마지막에 추가 공급하고 실제 입력 길이까지만 출력하도록 보완했다. 0.1.1만 허용하며 다른 모델/버전의 지연을 임의로 같다고 가정하지 않는다.

## 라이선스 경계

- Silero: 동봉된 원문 MIT 고지 유지. 모델 hash `1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3`.
- RNNoise: [공식 COPYING](https://github.com/xiph/rnnoise/blob/70f1d256acd4b34a572f999a05c87bf00b67730d/COPYING)과 소스별 고지 보존. 상업 사용 가능한 BSD 계열 조건. 기본 배포 모델의 공식 SHA-256을 검증한다. 제3자 임의 학습 weights는 사용하지 않는다.
- DeepFilterNet upstream: [MIT/Apache 선택](https://github.com/Rikorose/DeepFilterNet/blob/main/LICENSE). 다만 **DeepFilterNet-rs wheel/sdist에 LICENSE 파일이 없고 GitHub API license=null**이었다. [PyPI MIT 선언](https://pypi.org/project/deepfilternet-rs/)만으로 전체 재배포 고지가 완비됐다고 판단하지 않는다. 실험 설치는 해두었지만 제품 배포 전 래퍼와 내장 upstream 소스·모델 고지를 정리해야 한다. 이것이 default로 채택하지 않은 추가 이유다.
- numpy/onnxruntime는 설치 패키지의 BSD/MIT 및 번들 고지를 유지한다.
- **soxr1.1.0은 LGPL-2.1-or-later**이다. 상업 사용 자체가 금지되는 라이선스는 아니지만 배포 시 LGPL 고지·소스 제공/접근·수정본 조건·교체/재링크 등 해당 의무를 충족해야 한다. 폐쇄 Electron 실행 파일로 합칠 경우 배포 방식에 대한 검토가 필요하다. Python wheel 의존성으로 분리했고 관련 원문을 `src/xgen_audio/licenses`에 보관했다. '전체가 MIT/BSD만으로 구성됨'이라는 주장은 하지 않는다.
- 새 XGEN glue 코드에 임의의 공개 OSS 라이선스를 부여하지 않았다. 소유자의 배포 정책을 따르며 제3자 라이선스는 그대로 적용된다.

## 시험 데이터는 제품 모델과 별개

DeepFilterNet assets의 [원문 attribution](https://github.com/Rikorose/DeepFilterNet/blob/main/assets/README.md): noise2530은 CC BY3.0, noise573577은 CC0. 파일명을 보존하고 출처 URL과 hash를 manifest로 기록했다. 직접 확인하지 못한 녹음 환경을 '코엑스 소음'이나 '군중 소음'이라고 부르지 않는다. **clean33711은 CC BY-NC3.0**임을 확인하여 비교·번들에서 제외했다. 임시 다운로드 파일만 있으며 결과 폴더에 복사하지 않았다.

한국어는 기존 XGEN의 합성 fixture, 영어는 whisper.cpp JFK 샘플이다. 모두 시험용이며 runtime wheel에 포함되지 않는다. 대화 간섭 조건은 JFK 음성을3초 roll한 합성 간섭이다. '다양한 실제 화자 데이터셋'으로 해석하지 않는다. 실제 코엑스 녹음/한국어 다화자 corpus와 현장 마이크로 재검증해야 한다.
