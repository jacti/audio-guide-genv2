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
문화유산 키워드를 입력하면 `/outputs/info/{search_keyword}.md`를 생성합니다.

```bash
python -m src.pipelines.info_retrieval --search-keyword "청자 상감운학문 매병"
```
주요 옵션
- `--search-keyword` : 검색할 문화유산 키워드 (필수)
- `--model gpt-4.1` : 사용할 OpenAI 모델 지정 (기본값: `gpt-4.1`)
- `--prompt-version default` : 정보 검색 프롬프트 버전 (기본값: `default`)
- `--output-dir outputs/custom-info` : 결과 저장 경로 변경
- `--output-name custom_name` : 커스텀 출력 파일명 (검색 키워드 대신 사용)
- `--dry-run` : API 호출 없이 목업 Markdown 생성
- `--list-prompts` : 사용 가능한 프롬프트 템플릿 목록 출력

## 3. Pipeline 2 – 스크립트 생성 (`script_gen`)
정보 Markdown을 읽어 `/outputs/script/{search_keyword}_script.md`를 생성합니다.

```bash
python -m src.pipelines.script_gen --search-keyword "청자 상감운학문 매병" --script-prompt-version v2-tts
```
주요 옵션
- `--search-keyword` : 검색 키워드 (필수, info 파일명 매칭에 사용)
- `--script-prompt-version v2-tts` : 스크립트 생성 프롬프트 템플릿 (기본값: `v1`)
- `--info-dir outputs/info` : 입력 정보 파일 디렉터리
- `--output-dir outputs/script` : 출력 스크립트 디렉터리
- `--model gpt-4.1` : LLM 모델 (기본값: `gpt-4.1`)
- `--temperature 0.7` : LLM temperature (기본값: `0.7`)
- `--output-name custom_name` : 커스텀 출력 파일명
- `--dry-run` : API 호출 대신 고정 스크립트 예시 생성
- `--list-prompts` : 사용 가능한 프롬프트 목록 출력

## 4. Pipeline 3 – 오디오 생성 (`audio_gen`)
스크립트를 읽어 `/outputs/audio/{search_keyword}.mp3`를 생성합니다. **Gemini TTS API**를 사용합니다.

```bash
python -m src.pipelines.audio_gen --search-keyword "청자 상감운학문 매병" --voice Zephyr
```
주요 옵션
- `--search-keyword` : 검색 키워드 (필수, script 파일명 매칭에 사용)
- `--script-dir outputs/script` : 입력 스크립트 디렉터리
- `--output-dir outputs/audio` : 출력 오디오 디렉터리
- `--model gemini-2.5-flash-tts` : Gemini TTS 모델 (기본값, 선택: gemini-2.5-flash-tts, gemini-2.5-pro-tts)
- `--voice Zephyr` : Gemini TTS 음성 (기본값: `Zephyr`)
  - 사용 가능 음성 (32개): Zephyr, Puck, Charon, Kore, Fenrir, Aoede, Leda, Achernar, Laomedeia 등
- `--max-retries 8` : API 재시도 횟수 (기본값: `8`)
- `--initial-wait 1.0` : 초기 대기 시간(초)
- `--max-wait 60.0` : 최대 대기 시간(초)
- `--output-name custom_name` : 커스텀 출력 파일명
- `--dry-run` : 더미 MP3를 생성하여 흐름만 검증

**참고:** Gemini TTS는 `speed` 파라미터를 지원하지 않습니다.

## 5. 통합 실행 – `src/main.py`
세 파이프라인을 순차 실행해 최종 MP3까지 생성합니다.

```bash
python -m src.main --search-keyword "청자 상감운학문 매병"
```

### 주요 옵션
- `--search-keyword` : 문화유산 검색 키워드 (필수)
- `--model gpt-4.1` : LLM 모델 (info/script 단계 공통, 기본값: `gpt-4.1`)
- `--script-prompt-version v2-tts` : 스크립트 생성 프롬프트 버전 (기본값: `v2-tts`)
- `--info-prompt-version default` : 정보 검색 프롬프트 버전 (기본값: `default`)
- `--voice Zephyr` : Gemini TTS 음성 (기본값: `Zephyr`)
- `--tts-model gemini-2.5-flash-tts` : Gemini TTS 모델 (기본값, 선택: gemini-2.5-flash-tts, gemini-2.5-pro-tts)
- `--temperature 0.7` : 스크립트 생성 temperature (기본값: `0.7`)
- `--max-retries 8` : 오디오 생성 재시도 횟수 (기본값: `8`)
- `--output-name custom_name` : 커스텀 출력 파일명
- `--stages 1,2,3` : 실행할 파이프라인 단계 선택 (기본값: `1,2,3`)
- `--dry-run` : 테스트 모드 (API 호출 없이 목업 데이터 생성)

### 선택적 파이프라인 실행 (`--stages`)
특정 단계만 재실행할 수 있습니다. 비용 절감과 반복 테스트에 유용합니다.

```bash
# 정보 검색만 실행 (Stage 1)
python -m src.main --search-keyword "석굴암" --stages 1

# 스크립트 생성만 재실행 (info 파일이 이미 존재할 때)
python -m src.main --search-keyword "석굴암" --stages 2

# 오디오 생성만 재실행 (script 파일이 이미 존재할 때)
python -m src.main --search-keyword "석굴암" --stages 3

# 스크립트 + 오디오만 재생성
python -m src.main --search-keyword "석굴암" --stages 2,3
```

### 예시 1 – 기본 실행 (전체 파이프라인)
```bash
python -m src.main --search-keyword "청자 상감운학문 매병"
```

### 예시 2 – 커스텀 설정
```bash
python -m src.main --search-keyword "석굴암" \
  --model gpt-4.1 \
  --script-prompt-version v2-tts \
  --voice Puck \
  --temperature 0.6 \
  --max-retries 10
```

### 예시 3 – Dry-run 테스트
```bash
python -m src.main --search-keyword "사유의 방" --dry-run
```

## 6. 배치 실행 (트랙 기반) – `src/batch_runner.py`
여러 오디오 가이드를 하나의 트랙으로 묶어 일괄 생성합니다.

### 트랙(Track)이란?
주제나 카테고리로 묶인 여러 오디오 파일의 모음입니다.
- 예: "박물관 이용 가이드" 트랙에 "박물관 소개", "전시관 안내", "앱 사용법" 3개 파일 포함
- 트랙별로 독립적인 디렉토리 구조 유지
- YAML 설정 파일로 한 번에 관리

### 6.1. YAML 설정 파일 작성

`tracks/` 디렉토리에 YAML 파일을 생성합니다. (`tracks/sample_track.yaml` 참고)

```yaml
# 트랙 기본 정보
track_name: "꿀팁 가이드"
description: "박물관 이용에 도움이 되는 필수 가이드"

# 공통 설정 (모든 파일에 적용, 개별 오버라이드 가능)
defaults:
  model: "gpt-4.1"                          # LLM 모델 (Pipeline 1, 2)
  info_prompt_version: "default"            # Pipeline 1 (정보 검색) 프롬프트
  script_prompt_version: "v2-tts"           # Pipeline 2 (스크립트 생성) 프롬프트
  voice: "Zephyr"                           # Gemini TTS 음성
  tts_model: "gemini-2.5-flash-tts"         # Gemini TTS 모델
  temperature: 0.7                          # LLM temperature
  max_retries: 8                            # API 재시도 횟수
  dry_run: false                            # 테스트 모드

# 생성할 파일 목록
files:
  - output_name: "1_박물관소개"
    search_keyword: "국립중앙박물관 역사와 위치 소개"

  - output_name: "2_전시관소개"
    search_keyword: "국립중앙박물관 전시관 구성과 주요 관 소개"

  - output_name: "3_앱사용꿀팁"
    search_keyword: "국립중앙박물관 앱 사용법과 오디오가이드 이용법"
    voice: "Puck"                # 이 파일만 다른 목소리 사용
    temperature: 0.8             # 이 파일만 다른 온도 설정
    script_gen_prompt: |         # 커스텀 프롬프트 추가 (선택)
      따뜻하고 친근한 톤으로 작성해주세요.
      초보자도 쉽게 이해할 수 있도록 설명해주세요.
```

**필수 필드:**
- `track_name`: 트랙 이름
- `files`: 파일 목록 (각 항목은 `output_name`, `search_keyword` 필수)

**선택 필드:**
- `description`: 트랙 설명
- `metadata`: 작성자, 버전, 태그 등
- `defaults`: 공통 설정 (개별 파일에서 오버라이드 가능)

**YAML 필드 설명:**
- `search_keyword`: 정보 검색 키워드 (필수)
- `script_gen_prompt`: 기본 프롬프트에 추가할 커스텀 지시사항 (선택)
- `info_prompt_version`: 정보 검색 프롬프트 템플릿 버전
- `script_prompt_version`: 스크립트 생성 프롬프트 템플릿 버전

### 6.2. 배치 실행 명령어

```bash
# 기본 실행 (전체 파이프라인)
python -m src.batch_runner --track-file tracks/sample_track.yaml

# Dry-run 모드 (API 호출 없이 테스트)
python -m src.batch_runner --track-file tracks/my_track.yaml --dry-run

# 선택적 파이프라인 실행 (--stages)
# 스크립트만 재생성 (info 파일은 이미 존재)
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2

# 스크립트 + 오디오만 재생성
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2,3

# 오디오만 재생성 (script 파일은 이미 존재)
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 3
```

**주요 옵션:**
- `--track-file` : YAML 트랙 설정 파일 경로 (필수)
- `--dry-run` : 테스트 모드 (YAML defaults 오버라이드)
- `--stages 1,2,3` : 실행할 파이프라인 단계 (기본값: `1,2,3`)

### 6.3. 출력 디렉토리 구조

```
outputs/tracks/꿀팁_가이드/
├── info/
│   ├── 1_박물관소개.md
│   ├── 2_전시관소개.md
│   └── 3_앱사용꿀팁.md
├── script/
│   ├── 1_박물관소개_script.md
│   ├── 2_전시관소개_script.md
│   └── 3_앱사용꿀팁_script.md
├── audio/                    # 최종 결과물
│   ├── 1_박물관소개.mp3
│   ├── 2_전시관소개.mp3
│   └── 3_앱사용꿀팁.mp3
└── batch_report.json         # 실행 결과 리포트
```

### 6.4. 실행 결과 리포트

배치 실행 완료 후 `batch_report.json`이 자동 생성됩니다:

```json
{
  "track_name": "꿀팁 가이드",
  "started_at": "2025-11-07T14:30:00",
  "completed_at": "2025-11-07T14:35:42",
  "duration_seconds": 342,
  "total_files": 3,
  "successful": 3,
  "failed": 0,
  "files": [
    {
      "output_name": "1_박물관소개",
      "search_keyword": "국립중앙박물관 역사와 위치 소개",
      "status": "success",
      "audio_path": "outputs/tracks/꿀팁_가이드/audio/1_박물관소개.mp3",
      "stages_run": [1, 2, 3]
    }
    // ...
  ]
}
```

### 6.5. 사용 시나리오

```bash
# 1. 샘플 파일 복사
cp tracks/sample_track.yaml tracks/cultural_heritage.yaml

# 2. YAML 파일 편집 (원하는 트랙 구성)
# vim tracks/cultural_heritage.yaml

# 3. Dry-run으로 테스트
python -m src.batch_runner --track-file tracks/cultural_heritage.yaml --dry-run

# 4. 실제 실행
python -m src.batch_runner --track-file tracks/cultural_heritage.yaml

# 5. 결과 확인
cat outputs/tracks/[트랙명]/batch_report.json
open outputs/tracks/[트랙명]/audio/
```

### 6.6. 에러 처리

- **순차 실행**: 파일을 하나씩 처리하여 안정성 확보
- **즉시 중단**: 에러 발생 시 전체 배치 중단
- **부분 리포트**: 실패 지점까지의 결과를 리포트에 기록
- **상세 로그**: 어느 파일의 어느 단계에서 실패했는지 명확히 표시

## 7. 프롬프트 반복 테스트 워크플로우

`--stages` 파라미터를 활용하면 비용을 절감하면서 프롬프트를 반복적으로 테스트할 수 있습니다.

### 워크플로우 1: main.py를 이용한 프롬프트 테스트

```bash
# 1단계: 정보 검색 (1회만 실행, API 비용 발생)
python -m src.main --search-keyword "청자 상감운학문 매병" --stages 1

# 2단계: 여러 프롬프트 버전으로 스크립트 생성 테스트 (저렴한 API 비용만 발생)
python -m src.main --search-keyword "청자 상감운학문 매병" --stages 2 --script-prompt-version v1
python -m src.main --search-keyword "청자 상감운학문 매병" --stages 2 --script-prompt-version v2
python -m src.main --search-keyword "청자 상감운학문 매병" --stages 2 --script-prompt-version v2-tts

# 3단계: 스크립트를 확인하고 마음에 드는 버전 선택
cat outputs/script/청자\ 상감운학문\ 매병_script.md

# 4단계: 최종 선택한 스크립트로 오디오 생성
python -m src.main --search-keyword "청자 상감운학문 매병" --stages 3
```

### 워크플로우 2: batch_runner.py를 이용한 프롬프트 테스트

```bash
# 1단계: YAML 파일 작성 (script_prompt_version: v1)
# tracks/test_track.yaml

# 2단계: 전체 파이프라인으로 초기 생성
python -m src.batch_runner --track-file tracks/test_track.yaml

# 3단계: YAML 파일에서 script_prompt_version만 v2-tts로 변경

# 4단계: 스크립트만 재생성 (info 파일 재사용, 비용 절감)
python -m src.batch_runner --track-file tracks/test_track.yaml --stages 2

# 5단계: 스크립트 확인 후 만족하면 오디오 생성
python -m src.batch_runner --track-file tracks/test_track.yaml --stages 3
```

### 워크플로우 3: 커스텀 프롬프트 테스트 (YAML only)

YAML 파일에서 `script_gen_prompt` 필드를 활용하여 기본 프롬프트에 추가 지시사항을 넣을 수 있습니다:

```yaml
files:
  - output_name: "test_formal"
    search_keyword: "청자 매병"
    script_gen_prompt: |
      격식있고 전문적인 톤으로 작성해주세요.
      박물관 큐레이터의 어조를 사용해주세요.

  - output_name: "test_friendly"
    search_keyword: "청자 매병"
    script_gen_prompt: |
      친근하고 대화체로 작성해주세요.
      초등학생도 이해할 수 있게 쉽게 설명해주세요.
```

```bash
# 동일한 info 파일로 다양한 톤의 스크립트 생성
python -m src.batch_runner --track-file tracks/tone_test.yaml --stages 2
```

**비용 절감 효과:**
- Stage 1 (정보 검색): 웹 검색 + LLM 호출 (비용 높음) → 1회만 실행
- Stage 2 (스크립트 생성): LLM 호출만 (비용 중간) → 여러 번 테스트 가능
- Stage 3 (오디오 생성): TTS API (비용 낮음) → 최종 확정 후 1회 실행

## 8. 환경 변수 설정

`.env` 파일을 프로젝트 루트에 생성하고 다음 내용을 추가하세요:

```
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

**API 키 발급:**
- OpenAI API: https://platform.openai.com/api-keys
- Gemini API: https://aistudio.google.com/apikey

## 9. 출력 파일 위치

**개별 실행 시 (main.py):**
- 정보: `outputs/info/{search_keyword}.md`
- 스크립트: `outputs/script/{search_keyword}_script.md`
- 오디오: `outputs/audio/{search_keyword}.mp3`

**배치 실행 시 (batch_runner.py):**
- 트랙 루트: `outputs/tracks/{track_name}/`
- 정보: `outputs/tracks/{track_name}/info/{output_name}.md`
- 스크립트: `outputs/tracks/{track_name}/script/{output_name}_script.md`
- 오디오: `outputs/tracks/{track_name}/audio/{output_name}.mp3`
- 리포트: `outputs/tracks/{track_name}/batch_report.json`

**Dry-run 모드:**
- 모든 출력: `outputs/mock/` 디렉토리에 저장

각 단계는 실행 시 파일 경로를 로그로 안내하므로, 완료 후 바로 내용을 확인할 수 있습니다.

---

필요한 추가 지시는 항상 `docs/commands/` 내 최신 YAML 명령서를 참고해 주세요.
