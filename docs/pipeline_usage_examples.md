# 파이프라인 사용 예제

이 문서는 업데이트된 변수명과 필수 파라미터를 포함하여 각 파이프라인을 실행하는 방법을 설명합니다.

## 1. 정보 검색 파이프라인 (`src.pipelines.info_retrieval`)

**필수 파라미터:**

- `search_keyword`: 검색할 키워드.
- `perplexity_model`: Perplexity 모델 (예: "sonar-pro").
- `info_retrieval_prompt_template_name`: 프롬프트 템플릿 버전 (예: "default").
- `info_retrieval_user_content_text`: 정보 수집을 위한 구체적인 지시사항 (텍스트).

### Python 코드 예제

```python
from pathlib import Path
from src.pipelines import info_retrieval

output_path = info_retrieval.run(
    search_keyword="청자 상감운학문 매병",
    perplexity_model="sonar-pro",
    info_retrieval_prompt_template_name="default",
    info_retrieval_user_content_text="예술적 가치와 역사적 중요성에 초점을 맞춰주세요.",
    # 선택 사항
    output_dir=Path("outputs/info")
)
```

### CLI 실행 예제

터미널에서 직접 실행할 때는 다음과 같이 인자를 전달합니다.

```bash
python src/pipelines/info_retrieval.py \
  --search-keyword "청자 상감운학문 매병" \
  --perplexity-model "sonar-pro" \
  --prompt-template-name "default" \
  --user-content-text "예술적 가치와 역사적 중요성에 초점을 맞춰주세요."
```

---

## 2. 스크립트 생성 파이프라인 (`src.pipelines.script_gen`)

**필수 파라미터:**

- `search_keyword`: 검색 키워드 (파일 조회용).
- `script_gen_prompt_template_name`: 스크립트 생성 프롬프트 템플릿 버전.
- `script_gen_model`: 사용할 모델명 (OpenAI 'gpt-_' 또는 Google 'gemini-_').

**선택 파라미터:**

- `info_retrieval_result_file_path`: 정보 검색 결과 파일 경로 (직접 지정 시 `search_keyword` 기반 조회보다 우선).
- `script_gen_user_content_text`: 추가 연출 지시사항 (텍스트).

### Python 코드 예제

```python
from src.pipelines import script_gen

output_path = script_gen.run(
    search_keyword="청자 상감운학문 매병",
    script_gen_prompt_template_name="v2-tts",
    script_gen_model="gpt-4.1",
    # 선택 사항
    script_gen_user_content_text="친근한 어조로 작성해주세요.",
    temperature=0.7
)
```

### CLI 실행 예제

```bash
python src/pipelines/script_gen.py \
  --search-keyword "청자 상감운학문 매병" \
  --prompt-template-name "v2-tts" \
  --script-gen-model "gpt-4.1" \
  --user-content-text "친근한 어조로 작성해주세요." \
  --info-result-file "outputs/info/청자_상감운학문_매병.md"  # 직접 파일 지정 가능
```

---

## 3. 오디오 생성 파이프라인 (`src.pipelines.audio_gen`)

**필수 파라미터:**

- `search_keyword`: 검색 키워드 (파일 조회용).
- `tts_language`: 언어 코드 (예: "ko-KR").
- `tts_system_prompt`: TTS 페르소나를 위한 시스템 프롬프트.

**선택 파라미터 (기본값 있음):**

- `voice`: "Zephyr"
- `gemini_tts_model`: "gemini-2.5-pro-tts"
- `script_gen_result_file_path`: 스크립트 파일 경로 (직접 지정 시 `search_keyword` 기반 조회보다 우선).

### Python 코드 예제

```python
from src.pipelines import audio_gen

output_path = audio_gen.run(
    search_keyword="청자 상감운학문 매병",
    tts_language="ko-KR",
    tts_system_prompt="당신은 따뜻하고 매력적인 박물관 도슨트입니다.",
    # 선택 사항
    voice="Zephyr",
    gemini_tts_model="gemini-2.5-pro-tts"
)
```

### CLI 실행 예제

```bash
python src/pipelines/audio_gen.py \
  --search-keyword "청자 상감운학문 매병" \
  --tts-language "ko-KR" \
  --tts-system-prompt "당신은 따뜻하고 매력적인 박물관 도슨트입니다." \
  --voice "Zephyr" \
  --gemini-tts-model "gemini-2.5-pro-tts" \
  --script-file "outputs/script/청자_상감운학문_매병_script.md" # 직접 파일 지정 가능
```

---

## 4. 배치 러너 설정 (`tracks/*.yaml`)

`src.batch_runner`를 사용할 때는 YAML 설정 파일의 `defaults` 또는 개별 파일 설정(`files`)에 필요한 파라미터가 모두 제공되어야 합니다.

### YAML 설정 예시

```yaml
track_name: "박물관 하이라이트"
defaults:
  perplexity_model: "sonar-pro" # 정보 검색용 모델
  info_retrieval_prompt_template_name: "default"
  script_gen_prompt_template_name: "v2-tts"
  tts_language: "ko-KR"
  tts_system_prompt: "당신은 도슨트입니다..."

files:
  - search_keyword: "청자 상감운학문 매병"
    output_name: "01_celadon_vase"
    # 개별 설정 오버라이드
    voice: "Puck"
    script_gen_user_content_text: "전문적인 톤으로 설명해주세요."
```

### 배치 러너 CLI 실행

```bash
# 전체 파이프라인 실행
python -m src.batch_runner --track-file tracks/sample_track.yaml

# 병렬 실행 (속도 향상)
python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel
```
