# 추출 출처

- source: XGEN model의 `backend/asr_streaming/silero_vad.py`에서 스트리밍 VAD 구현을 추출했다.
- source SHA-256: `941dfa0f14a3b2187f1045682e7a5681d81c9c191f9796c6fec863bd8a32e27f`.
- model repo는 다른 미커밋 변경이 존재한다. 이 파일/모델의 현재 내용을 읽어서 추출했으며 기존 파일을 수정하지 않았다.
- cross-check: XGEN core의 `service/audio/silero_vad.py` 및 검증 문서와 동작을 대조했다.
- 기존 시작0.5×3frames, 종료0.35/20frames 중16 + 마지막3frames, 1.2초 pre-roll, 4ms context, shared ONNX + per-instance state, checksum guard를 보존했다.
- 변경: 서비스 import를 로컬 pcm module로 치환; 이전 발화 종료 이전으로 pre-roll이 돌아가지 않도록 clamp. 서버의 buffer_base clamp에 의존하던 조건을 standalone 이벤트 API 자체에 반영했다.
- 기존 Silero unit tests 중 실제 모델·짧은 네/아니요·quiet·state isolation·flush·split 테스트를 가져왔다. 엔진 테스트 전체를 라이브러리로 복사하지 않았다.
- RNNoise source70f1d256acd4b34a572f999a05c87bf00b67730d, source archive SHA-256 f61ee0b3f4c4cd337303e003d333357c5eaf25ef5d75a742109ee59e9a0a3932.
- RNNoise model archive SHA-256 0a8755f8e2d834eff6a54714ecc7d75f9932e845df35f8b59bc52a7cfe6e8b37.
