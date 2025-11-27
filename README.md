# 오디오 가이드 생성 파이프라인

## 세팅

- python 3.13
- 가상환경 세팅
- requirements.txt 패키지 관리
- 환경변수 .env 필요
  ```
  EXA_API_KEY=...
  OPENAI_API_KEY=...
  PERPLEXITY_API_KEY=...
  GEMINI_API_KEY=...
  GOOGLE_APPLICATION_CREDENTIALS=...
  ```
- 오디오 생성을 위해 `gemini_tts_model: "gemini-2.5-pro-tts"` 모델 사용, API KEY는 `.env`와 별도로`./listentrip-55d51165ef78.json`로 관리

## 실행

- `docs/pipeline_usage_examples.md` 참고
- 생성할 오디오 플레이리스트 목록과 프롬프트를 `/playlists.test.yaml`의 형식에 알맞게 작성

```sh
python -m src.batch_runner --playlist-file playlists/test.yaml # 정보추출, 스크립트 생성, 오디오생성 전부 진행
python -m src.batch_runner --playlist-file playlists/test.yaml --stages 2 # 스크랩트 생성만
python -m src.batch_runner --playlist-file playlists/test.yaml --stages 2,3 # 스크랩트 생성, 오디오생성 만
```
