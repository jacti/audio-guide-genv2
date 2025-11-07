# Audio Guide Pipeline – Command Reference

이 문서는 파이프라인 사용자가 각 단계를 개별 실행하거나 `src/main.py`로 통합 실행할 때 필요한 CLI 명령어를 빠르게 찾을 수 있도록 정리한 안내서입니다.

## 1. 실행 전 준비
1. **가상환경 및 의존성 설치**
   ```bash
   ./setup-venv.sh
   source .venv/bin/activate
   ```
2. **환경변수(.env) 구성** – 최소 `OPENAI_API_KEY`를 정의해야 하며, 없으면 실행 전에 생성해야 합니다.

## 2. Pipeline 1 – 정보 검색 (`info_retrieval`)
문화유산 키워드를 입력하면 `/outputs/info/{keyword}.md`를 생성합니다.

```bash
python -m src.pipelines.info_retrieval --keyword "청자 상감운학문 매병"
```
주요 옵션
- `--model gpt-4o` : 사용할 OpenAI 모델 지정 (기본 `gpt-4.1`).
- `--output-dir outputs/custom-info` : 결과 저장 경로 변경.
- `--dry-run` : API 호출 없이 목업 Markdown 생성.

## 3. Pipeline 2 – 스크립트 생성 (`script_gen`)
정보 Markdown을 읽어 `/outputs/script/{keyword}_script.md`를 생성합니다.

```bash
python -m src.pipelines.script_gen --keyword "청자 상감운학문 매병" --prompt-version v1
```
주요 옵션
- `--prompt-version version` : 사용할 프롬프트 템플릿.
- `--info-dir outputs/info` / `--output-dir outputs/script` : 입·출력 디렉터리 지정.
- `--model gpt-4o-mini` , `--temperature 0.7` : LLM 파라미터 조정.
- `--dry-run` : API 호출 대신 고정 스크립트 예시 생성.
- `--list-prompts` : 사용 가능한 프롬프트 목록만 출력.

## 4. Pipeline 3 – 오디오 생성 (`audio_gen`)
스크립트를 읽어 `/outputs/audio/{keyword}.mp3`를 생성합니다.

```bash
python -m src.pipelines.audio_gen --keyword "청자 상감운학문 매병" --voice alloy
```
주요 옵션
- `--script-dir outputs/script` / `--output-dir outputs/audio` : 입·출력 경로 지정.
- `--model gpt-4o-mini-tts` , `--voice alloy|nova|...` , `--speed 1.0` : TTS 설정.
- `--max-retries 8 --initial-wait 1.0 --max-wait 60.0` : 지수 백오프 파라미터.
- `--dry-run` : 더미 MP3(112 bytes)를 생성하여 흐름만 검증.

## 5. 통합 실행 – `src/main.py`
세 파이프라인을 순차 실행해 최종 MP3까지 생성합니다.

```bash
python -m src.main --keyword "청자 상감운학문 매병"
```
자주 사용하는 옵션
- `--dry-run` : 세 단계 모두 목업 데이터를 생성.
- `--model gpt-4o-mini` : info/script 단계 공통 모델 지정.
- `--prompt-version v1|v2` : 스크립트 프롬프트 선택.
- `--voice alloy --speed 1.0` : 오디오 파라미터 조정.
- `--temperature 0.7` : 스크립트 단계 온도.
- `--max-retries 8` : 오디오 단계 재시도 횟수.

### 예시 – 커스텀 설정
```bash
python -m src.main --keyword "석굴암" \
  --model gpt-4o \
  --prompt-version v2 \
  --voice nova \
  --speed 1.1 \
  --temperature 0.6
```

## 6. 출력 파일 위치
- 정보: `outputs/info/{keyword}.md`
- 스크립트: `outputs/script/{keyword}_script.md`
- 오디오: `outputs/audio/{keyword}.mp3`
각 단계는 실행 시 파일 경로를 로그로 안내하므로, 완료 후 바로 내용을 확인할 수 있습니다.

필요한 추가 지시는 항상 `docs/commands/` 내 최신 YAML 명령서를 참고해 주세요.
