# Audio Generation Pipeline Overview

## 1. 목적과 입력/출력
- **Input**: `outputs/script/[keyword]_script.md`에 저장된 스크립트 Markdown.
- **Output**: OpenAI TTS API를 통해 생성된 `outputs/audio/[keyword].mp3` 파일.
- **Keyword 처리**: `src/utils/path_sanitizer.py`의 `script_markdown_path`, `audio_output_path`를 사용해 공백을 유지한 파일명을 만든다.

## 2. 주요 흐름 요약 (`src/pipelines/audio_gen.py`)
1. 환경 변수 로드(`load_dotenv`) 후 로거 설정.
2. `_read_script(path)`
   - 스크립트 파일 존재/내용 검증.
   - 비어 있거나 없으면 예외 발생.
3. 실행 모드 분기
   - `dry_run=True`: `_create_dummy_audio()`가 112바이트짜리 더미 MP3를 작성한다.
   - `dry_run=False`: `_generate_audio_openai()`가 실제 OpenAI TTS API(`audio.speech.create`)를 호출한다.
4. `_generate_audio_openai()`
   - API 키와 파라미터(voice, speed) 검증.
   - 최대 3회 재시도하며 실패 시 예외를 전파.
   - 성공 시 `response.content`를 MP3 바이너리로 반환.
5. 결과 MP3를 저장하고 경로/파라미터를 로그로 남긴다.
6. `main()` CLI는 argparse 기반으로 옵션을 받아 `run()`을 호출하고, 성공 시 경로를 인쇄한다.

## 3. 의존성 및 환경 요구 사항
- `openai` Python SDK: `client.audio.speech.create` 엔드포인트를 사용한다.
- `.env`에 `OPENAI_API_KEY`가 반드시 있어야 한다.
- 외부 네트워크 접근이 가능해야 하며, DNS가 `api.openai.com`을 정상 해석해야 한다.
- dry_run 모드는 외부 API 없이도 더미 파일을 생성해 파이프라인 연동을 테스트할 수 있다.

## 4. 에러 처리
- 스크립트 파일 없음 → `FileNotFoundError`로 명시적으로 안내.
- 스크립트 내용 없음 → `ValueError`.
- API 키 미설정 → `ValueError`.
- `audio.speech.create` 실패 → 시도마다 경고 로그 후, 최대 재시도 초과 시 예외 발생.
- 예외 발생 시 `main()`에서 `logger.error`로 메시지를 출력하고 예외를 다시 던진다.

## 5. dry_run 더미 파일 동작
- `_create_dummy_audio()`는 112바이트 헤더만 가지므로 실제 재생은 불가하다.
- dry_run 산출물과 실제 산출물을 구분하기 위해 파일명 또는 저장 위치를 분리하는 개선이 권장된다.

## 6. CLI 사용 예시
```bash
# Dry run (더미 MP3 생성)
python src/pipelines/audio_gen.py --keyword "청자 상감운학문 매병" --dry-run

# 실제 API 호출 (네트워크·API 키 필요)
python src/pipelines/audio_gen.py --keyword "청자 상감운학문 매병" --voice nova --speed 1.1
```

## 7. 현재 한계와 주의 사항
- OpenAI API 네트워크 연결 실패 시 즉시 예외로 종료한다. 최근 테스트에서 `socket.gaierror`(DNS 해석 실패)로 인해 접속이 차단된 사례가 있다.
- dry_run 결과가 저장 디렉터리와 동일하여, 프로덕션 산출물과 혼동될 수 있다.
- MP3 파일 크기 검증 로직이 없어 네트워크 실패 후 빈 파일이 저장될 위험이 있다(후속 개선 항목에 기록됨).

## 8. 관련 문서 및 후속 작업
- `docs/commands/audio-generation.md`: dry_run 파일 분리, TTS 성공 검증, 샘플 재생성 등 후속 지시 사항.
- 차후 `tests/` 혹은 스크립트를 통해 info→script→audio 연속 실행 드라이런을 자동화 예정.

