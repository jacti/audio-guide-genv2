# 파이프라인 사용 예제

이 문서는 업데이트된 필수 파라미터를 포함하여 각 파이프라인을 실행하는 방법을 설명합니다.

## 1. 정보 검색 파이프라인 (`src.pipelines.info_retrieval`)

**필수 파라미터:**

- `search_keyword`: 검색할 키워드.
- `model`: Perplexity 모델 (예: "sonar-pro").
- `prompt_version`: 프롬프트 템플릿 버전 (예: "default").
- `info_prompt`: 정보 수집을 위한 구체적인 지시사항.

### Python 코드 예제

```python
from pathlib import Path
from src.pipelines import info_retrieval

output_path = info_retrieval.run(
    search_keyword="청자 상감운학문 매병",
    model="sonar-pro",
    prompt_version="default",
    info_prompt="예술적 가치와 역사적 중요성에 초점을 맞춰주세요.",
    # 선택 사항
    output_dir=Path("outputs/info")
)
```

### CLI 실행 예제

터미널에서 직접 실행할 때는 다음과 같이 인자를 전달합니다.

```bash
python src/pipelines/info_retrieval.py \
  --search-keyword "청자 상감운학문 매병" \
  --model "sonar-pro" \
  --prompt-version "default" \
  --info-prompt "예술적 가치와 역사적 중요성에 초점을 맞춰주세요."
```

---

## 2. 스크립트 생성 파이프라인 (`src.pipelines.script_gen`)

**필수 파라미터:**

- `search_keyword`: 검색 키워드 (파일 조회용).
- `script_prompt_version`: 스크립트 생성 프롬프트 템플릿 버전.
- `model`: OpenAI 모델 (예: "gpt-4.1").

### Python 코드 예제

```python
from src.pipelines import script_gen

output_path = script_gen.run(
    search_keyword="청자 상감운학문 매병",
    script_prompt_version="v2-tts",
    model="gpt-4.1",
    # 선택 사항
    custom_prompt="친근한 어조로 작성해주세요.",
    temperature=0.7
)
```

### CLI 실행 예제

```bash
python src/pipelines/script_gen.py \
  --search-keyword "청자 상감운학문 매병" \
  --script-prompt-version "v2-tts" \
  --model "gpt-4.1" \
  --custom-prompt "친근한 어조로 작성해주세요."
```

---

## 3. 오디오 생성 파이프라인 (`src.pipelines.audio_gen`)

**필수 파라미터:**

- `search_keyword`: 검색 키워드 (파일 조회용).
- `tts_language`: 언어 코드 (예: "ko-KR").
- `tts_prompt`: TTS 페르소나를 위한 시스템 프롬프트.

**선택 파라미터 (기본값 있음):**

- `voice`: "Zephyr"
- `model`: "gemini-2.5-pro-tts"

### Python 코드 예제

```python
from src.pipelines import audio_gen

output_path = audio_gen.run(
    search_keyword="청자 상감운학문 매병",
    tts_language="ko-KR",
    tts_prompt="당신은 따뜻하고 매력적인 박물관 도슨트입니다.",
    # 선택 사항
    voice="Zephyr",
    model="gemini-2.5-pro-tts"
)
```

### CLI 실행 예제

```bash
python src/pipelines/audio_gen.py \
  --search-keyword "청자 상감운학문 매병" \
  --tts-language "ko-KR" \
  --tts-prompt "당신은 따뜻하고 매력적인 박물관 도슨트입니다." \
  --voice "Zephyr" \
  --model "gemini-2.5-pro-tts"
```

---

## 4. 배치 러너 설정 (`tracks/*.yaml`)

`src.batch_runner`를 사용할 때는 YAML 설정 파일의 `defaults` 또는 개별 파일 설정(`files`)에 필요한 파라미터가 모두 제공되어야 합니다.

### YAML 설정 예시

```yaml
track_name: "박물관 하이라이트"
defaults:
  model: "sonar-pro" # 정보 검색용 모델
  info_prompt_version: "default"
  script_prompt_version: "v2-tts"
  tts_language: "ko-KR"
  tts_prompt: "당신은 도슨트입니다..."

files:
  - search_keyword: "청자 상감운학문 매병"
    output_name: "01_celadon_vase"
    # 개별 설정 오버라이드
    voice: "Puck"
```

### 배치 러너 CLI 실행

```bash
# 전체 파이프라인 실행
python -m src.batch_runner --track-file tracks/sample_track.yaml

# 병렬 실행 (속도 향상)
python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel
```
