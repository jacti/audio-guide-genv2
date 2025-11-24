# 파이프라인 사용 예제

업데이트된 파라미터 이름을 기준으로 각 파이프라인을 실행하는 방법을 정리했습니다. 이제 `output_name`과 `info_retrieval_user_content_text`로 식별과 검색 요구사항을 모두 전달합니다.

## 1. 정보 검색 파이프라인 (`src.pipelines.info_retrieval`)

**필수 파라미터**

- `output_name`: 결과 파일명 (playlists YAML의 files.output_name)
- `perplexity_model`: Perplexity 모델 (예: "sonar-pro")
- `info_retrieval_prompt_template_name`: 프롬프트 YAML 이름 (예: "universal_retrieval")
- `info_retrieval_user_content_text`: 정보 수집을 위한 구체적 지시사항 텍스트

```python
from pathlib import Path
from src.pipelines import info_retrieval

output_path = info_retrieval.run(
    output_name="01_celadon",
    perplexity_model="sonar-pro",
    info_retrieval_prompt_template_name="universal_retrieval",
    info_retrieval_user_content_text="예술적 가치와 역사적 중요성에 초점을 맞춰주세요.",
    output_dir=Path("outputs/info"),
)
```

```bash
python src/pipelines/info_retrieval.py \
  --output-name "01_celadon" \
  --perplexity-model "sonar-pro" \
  --prompt-template-name "universal_retrieval" \
  --user-content-text "예술적 가치와 역사적 중요성에 초점을 맞춰주세요."
```

---

## 2. 스크립트 생성 파이프라인 (`src.pipelines.script_gen`)

**필수 파라미터**

- `output_name`: 결과 파일명 (playlists YAML의 files.output_name)
- `script_gen_prompt_template_name`: 스크립트 프롬프트 YAML 이름 (예: "unniversal_script_gen")
- `script_gen_model`: 사용할 모델명 (OpenAI 'gpt-_' 또는 Google 'gemini-_')
- `info_retrieval_result_file_path`: 정보 파일 경로 (필수)

**선택 파라미터**

- `script_gen_user_content_text`: 추가 연출 지시사항 텍스트

```python
from pathlib import Path
from src.pipelines import script_gen

output_path = script_gen.run(
    output_name="01_celadon",
    script_gen_prompt_template_name="unniversal_script_gen",
    script_gen_model="gpt-4o",
    info_retrieval_result_file_path=Path("outputs/info/01_celadon.md"),
    script_gen_user_content_text="친근한 어조로 작성해주세요.",
    temperature=0.7,
)
```

```bash
python src/pipelines/script_gen.py \
  --output-name "01_celadon" \
  --prompt-template-name "unniversal_script_gen" \
  --script-gen-model "gpt-4o" \
  --user-content-text "친근한 어조로 작성해주세요." \
  --info-result-file "outputs/info/01_celadon.md"
```

---

## 3. 오디오 생성 파이프라인 (`src.pipelines.audio_gen`)

**필수 파라미터**

- `output_name`: 결과 파일명 (playlists YAML의 files.output_name)
- `script_gen_result_file_path`: 스크립트 파일 경로
- `tts_language`: 언어 코드 (예: "ko-KR")

**선택 파라미터 (기본값 있음)**

- `voice`: "Zephyr"
- `gemini_tts_model`: "gemini-2.5-pro-tts"

```python
from pathlib import Path
from src.pipelines import audio_gen

output_path = audio_gen.run(
    output_name="01_celadon",
    script_gen_result_file_path=Path("outputs/script/01_celadon_script.md"),
    tts_language="ko-KR",
    voice="Zephyr",
    gemini_tts_model="gemini-2.5-pro-tts",
)
```

```bash
python src/pipelines/audio_gen.py \
  --output-name "01_celadon" \
  --script-file "outputs/script/01_celadon_script.md" \
  --tts-language "ko-KR" \
  --voice "Zephyr"
```

---

## 4. 배치 러너 설정 (`playlists/*.yaml`)

`src.batch_runner`는 플레이리스트 YAML을 기반으로 info → script → audio를 실행합니다.

```yaml
playlist_name: "박물관 하이라이트"
defaults:
  perplexity_model: "sonar-pro"
  info_retrieval_prompt_template_name: "universal_retrieval"
  script_gen_prompt_template_name: "unniversal_script_gen"
  tts_language: "ko-KR"
  voice: "Zephyr"
files:
  - output_name: "01_celadon_vase"
    info_retrieval_user_content_text: "청자 상감운학문 매병 조사"
    script_gen_user_content_text: "전문적인 톤으로 설명해주세요."
    voice: "Puck" # 개별 오버라이드 예시
```

```bash
python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml
python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --parallel
```

---

## 5. 빠른 테스트 및 프로토타이핑

단일 파일을 빠르게 테스트하려면 `playlists/test.yaml` 플레이리스트를 사용하세요:

```bash
# 기본 테스트 실행 (순차 처리)
python -m src.batch_runner --playlist-file playlists/test.yaml

# 병렬 처리로 실행
python -m src.batch_runner --playlist-file playlists/test.yaml --parallel

# 특정 단계만 실행 (예: 스크립트 생성만)
python -m src.batch_runner --playlist-file playlists/test.yaml --stages 2

# 스크립트 + 오디오 재생성
python -m src.batch_runner --playlist-file playlists/test.yaml --stages 2,3
```

**playlists/test.yaml** 파일을 수정해서 테스트할 내용을 변경하세요:

```yaml
files:
  - output_name: "test_sample"
    info_retrieval_user_content_text: |
      여기에 조사할 내용을 작성하세요.
    script_gen_user_content_text: |
      여기에 추가 지시사항을 작성하세요.
```
