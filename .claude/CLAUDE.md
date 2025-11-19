# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an audio guide generation pipeline for cultural heritage artifacts. The system takes a cultural artifact name (e.g., "청자 상감운학문 매병") and automatically generates an audio guide file through three independent stages:

1. **Information Retrieval** → `/outputs/info/[keyword].md`
2. **Script Generation** → `/outputs/script/[keyword]_script.md`
3. **Audio Synthesis** → `/outputs/audio/[keyword].mp3`

Each pipeline stage is designed to be independently extensible and can be run separately or as part of the full workflow.

## Quick Start Commands

**Environment setup:**
```bash
# Initial setup (installs Python, creates venv, installs dependencies)
./setup-venv.sh
source .venv/bin/activate

# After pulling changes
source .venv/bin/activate
./setup-venv.sh
```

**Basic usage:**
```bash
# Single file generation (full pipeline)
python -m src.main --search-keyword "청자 상감운학문 매병"

# Batch generation from track file
python -m src.batch_runner --track-file tracks/sample_track.yaml

# Test mode (no API calls)
python -m src.main --search-keyword "테스트" --dry-run
python -m src.batch_runner --track-file tracks/sample_track.yaml --dry-run

# Run specific stages only
python -m src.main --search-keyword "유물명" --stages 2,3  # Skip info retrieval
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2  # Re-generate scripts only
```

**Individual pipeline testing:**
```bash
# Pipeline 1: Info retrieval
python -m src.pipelines.info_retrieval --search-keyword "유물명" --dry-run
python -m src.pipelines.info_retrieval --list-prompts

# Pipeline 2: Script generation
python -m src.pipelines.script_gen --search-keyword "유물명" --script-prompt-version v2-tts --dry-run
python -m src.pipelines.script_gen --list-prompts

# Pipeline 3: Audio generation
python -m src.pipelines.audio_gen --search-keyword "유물명" --voice Zephyr --dry-run
```

## Environment Setup

This project uses pyenv for Python version management and a `.venv` virtual environment.

**Python version:** See `.python-version` file (currently 3.13.9)

**Key dependencies:**
- `openai>=1.0.0` - For LLM API calls in info/script pipelines (SDK 1.x+ required)
- `google-cloud-texttospeech>=2.29.0` - For Google TTS API in audio pipeline (check implementation for actual SDK used)
- `python-dotenv>=1.0.0` - Environment variable management (requires `.env` file with API keys)
- `pyyaml>=6.0.0` - For YAML-based prompt template parsing
- `langchain-openai>=0.1.0` - For prompt/chain structures (optional but recommended)
- `perplexityai` - Web search SDK (Perplexity AI integration)
- `backoff>=2.0.0` - Exponential backoff for API retry logic
- `exa-py>=1.0.0` - Alternative web search SDK (currently unused)

## Architecture

### Core Design Principles

**Pipeline Independence:** Each of the three stages (info → script → audio) is:
- Independently executable with its own CLI
- Testable in isolation using `--dry-run` mode
- Extensible through YAML-based prompt templates

**File-Based Communication:** Stages communicate through markdown/audio files on disk:
- Enables debugging intermediate outputs
- Allows re-running individual stages without full pipeline
- Supports partial pipeline execution via `--stages` parameter

**Unified Prompt Management:** Both pipelines use YAML templates (`src/utils/prompt_loader.py`):
- Info pipeline: Responses API format (`instructions`, `input_template`, `tools`)
- Script pipeline: Chat Completions API format (`system_prompt`, `user_prompt_template`)

### Three-Stage Pipeline Design

Each pipeline stage is independent and communicates through file I/O:

**Pipeline 1: Information Retrieval** (`src/pipelines/info_retrieval.py`)
- Input: Search keyword (user input)
- Process: Uses Perplexity AI web search to retrieve and summarize information
- **Prompt System**: YAML-based templates in `/prompts/info_retrieval/` using Responses API format
- Output: Markdown file in `/outputs/info/[search_keyword].md`
- Extension point: Multiple prompt styles (detailed, simple, children-friendly, etc.)
- CLI: `python -m src.pipelines.info_retrieval --search-keyword "유물명" --prompt-version default [--dry-run]`
- List prompts: `python -m src.pipelines.info_retrieval --list-prompts`

**Pipeline 2: Script Generation** (`src/pipelines/script_gen.py`)
- Input: `/outputs/info/[search_keyword].md`
- Process: Uses LLM to transform information into audio guide script (1 min duration, friendly tone, visual imagery)
- Prompt system: YAML-based templates in `/prompts/script_generation/` (loaded via `src.utils.prompt_loader`)
- Current default: `v2-tts` (TTS-optimized, no markdown headers)
- **New**: Supports custom user prompts via `script_gen_prompt` field (appended to base prompt)
- Output: Script markdown in `/outputs/script/[search_keyword]_script.md`
- Extension point: Tone/style parameters, length control, session segmentation
- CLI: `python -m src.pipelines.script_gen --search-keyword "유물명" --script-prompt-version v2-tts [--custom-prompt "전문적인 톤"] [--dry-run]`
- List prompts: `python -m src.pipelines.script_gen --list-prompts`

**Pipeline 3: Audio Generation** (`src/pipelines/audio_gen.py`)
- Input: `/outputs/script/[search_keyword]_script.md`
- Process: Google TTS API conversion with exponential backoff retry logic (`backoff` package)
- **Note**: Implementation may use either `google-cloud-texttospeech` or `google-genai` SDK
- Default model: "gemini-2.5-flash-tts", voice: "Zephyr" (model name may vary by API version)
- Output: WAV/MP3 file in `/outputs/audio/[search_keyword].wav`
- Extension point: Voice selection (30+ voices), model selection, BGM mixing
- Supported voices: Zephyr, Puck, Charon, Kore, Fenrir, Aoede, Laomedeia 등 30+ voices
- CLI: `python -m src.pipelines.audio_gen --search-keyword "유물명" --voice Zephyr --model gemini-2.5-flash-tts [--dry-run]`
- **If model errors occur**: Verify the correct model name for your installed SDK version

### Shared Utilities

**Path Sanitization** (`src/utils/path_sanitizer.py`)
- Centralizes filename generation logic for all three pipelines
- Functions: `info_markdown_path()`, `script_markdown_path()`, `audio_output_path()`
- Removes filesystem-unsafe characters while preserving spaces
- All pipelines use `output_name` parameter for custom naming (overrides keyword)

**Prompt Loading** (`src/utils/prompt_loader.py`) - 통합 시스템
- YAML-based prompt template system for **all pipelines**
- Supports both API types:
  - Chat Completions API: `system_prompt` + `user_prompt_template` (Pipeline 2)
  - Responses API: `instructions` + `input_template` + `tools` (Pipeline 1)
- Auto-discovers prompts in:
  - `prompts/info_retrieval/*.yaml` (Pipeline 1)
  - `prompts/script_generation/*.yaml` (Pipeline 2)
- Templates contain: `name`, `description`, `tags`, `parameters`, `metadata`, `api_type`

**Metadata Tracking** (`src/utils/metadata.py`)
- Records pipeline execution details (keyword, model, timestamp, mode)
- Used for audit trails and debugging

### Main Entry Point

`src/main.py` orchestrates the full pipeline:

```bash
# Basic usage
python -m src.main --search-keyword "청자 상감운학문 매병"

# With custom settings
python -m src.main --search-keyword "석굴암" \
  --model gpt-4.1 \
  --info-prompt-version default \
  --script-prompt-version v2-tts \
  --voice Zephyr \
  --temperature 0.7 \
  --max-retries 8

# Different voice selection
python -m src.main --search-keyword "Celadon Vase" \
  --voice Puck

# Dry-run mode (no API calls, uses mock data)
python -m src.main --search-keyword "사유의 방" --dry-run

# Custom output naming
python -m src.main --search-keyword "청자 매병" --output-name "celadon_vase_01"

# 특정 파이프라인만 실행
# 스크립트만 재생성 (info 파일은 이미 존재)
python -m src.main --search-keyword "청자 매병" --stages 2

# 오디오만 재생성 (script 파일은 이미 존재)
python -m src.main --search-keyword "청자 매병" --stages 3
```

Expected output flow:
```
[1/3] 정보 검색 완료 → outputs/info/청자 상감운학문 매병.md
[2/3] 스크립트 생성 완료 → outputs/script/청자 상감운학문 매병_script.md
[3/3] 오디오 생성 완료 → outputs/audio/청자 상감운학문 매병.mp3
✅ 전체 파이프라인 완료!
```

**Important flags:**
- `--dry-run`: Test mode - generates mock data without API calls (useful for testing flow)
- `--output-name`: Override filename (default uses search_keyword with sanitization)
- `--stages`: Select which pipeline stages to run (1=info, 2=script, 3=audio). Default: 1,2,3
- `--info-prompt-version`: Pipeline 1 prompt version (default: "default")
- `--script-prompt-version`: Pipeline 2 prompt version (default: "v2-tts")
- All pipelines support independent CLI execution for debugging specific stages

## Directory Structure

```
script_gen_v2/
├── .claude/                # Claude Code configuration & context
│   └── CLAUDE.md          # This file
├── src/
│   ├── main.py            # Pipeline orchestration (runs all 3 stages)
│   ├── batch_runner.py    # Track-based batch execution
│   ├── pipelines/
│   │   ├── info_retrieval.py    # Stage 1: Web search & summarization
│   │   ├── script_gen.py        # Stage 2: LLM script generation
│   │   └── audio_gen.py         # Stage 3: TTS conversion
│   └── utils/
│       ├── prompt_loader.py     # Unified YAML prompt template loader
│       ├── path_sanitizer.py    # Filename sanitization logic
│       └── metadata.py          # Execution metadata tracking
├── prompts/
│   ├── info_retrieval/          # Pipeline 1 prompts (default.yaml)
│   └── script_generation/       # Pipeline 2 prompts (v1, v2, v2-tts)
├── notebooks/
│   └── prompt_optimizer.ipynb   # Interactive prompt testing & comparison tool
├── test_results/                # Saved prompt test results
│   ├── info_retrieval/
│   └── script_generation/
├── outputs/
│   ├── info/              # Stage 1 output (markdown info files)
│   ├── script/            # Stage 2 output (audio guide scripts)
│   ├── audio/             # Stage 3 output (mp3 files)
│   ├── tracks/            # Batch execution outputs (organized by track)
│   └── mock/              # Dry-run mode outputs
├── tracks/                # Track configuration YAML files
├── docs/
│   ├── plan.md            # Detailed design document
│   └── commands/          # Command reference YAML files
├── dev-log/               # Development logs (timestamped)
├── setup-venv.sh          # Automated venv setup script
├── requirements.txt       # Python dependencies
└── .python-version        # pyenv Python version (3.13.9)
```

## Development Guidelines

**Current Version (v0.1):** This is an MVP focused on validating the entire '입력 → md 정보 → 스크립트 → mp3 오디오' workflow with minimal features.

**When adding new features:**
- Each pipeline stage should remain independently executable
- File-based I/O between stages is intentional for debugging and extensibility
- Follow the input/output contract for each pipeline stage

**Testing & Quality Assurance:**
- Currently no automated tests exist (future improvement)
- Manual testing workflow:
  1. Use `--dry-run` flag to test pipeline flow without API costs
  2. Test individual pipelines: `python -m src.pipelines.[pipeline_name] --dry-run`
  3. Verify outputs in `outputs/mock/` directory
  4. Compare prompt versions using `notebooks/prompt_optimizer.ipynb`
  5. Use `--stages` parameter to test specific pipeline segments

**Planned extensions (v0.2+):**
- Enhanced search sources: Exa.ai → Wikipedia → museum.go.kr API
- Tone variations: 감성/교육/아동용 styles
- BGM auto-mixing with Suno
- Metadata tracking (JSON format)
- Automated testing suite
- UI layer: Streamlit or Next.js interface

## Batch Execution (트랙 기반 배치 실행)

**v0.1+**: 여러 오디오 가이드 파일을 트랙 단위로 묶어 일괄 생성하는 배치 실행 기능이 추가되었습니다.

### 트랙(Track) 개념

트랙은 주제나 카테고리로 묶인 여러 오디오 파일의 모음입니다.
- 예: "박물관 이용 가이드" 트랙에 "박물관 소개", "전시관 안내", "앱 사용법" 포함
- 트랙별로 독립적인 디렉토리 구조 유지
- YAML 설정 파일로 트랙 전체를 한 번에 관리

### 설정 파일 작성

**위치**: `tracks/` 디렉토리에 YAML 파일 생성

**기본 구조** (`tracks/sample_track.yaml` 참고):
```yaml
track_name: "꿀팁 가이드"
description: "박물관 이용에 도움이 되는 필수 가이드"

# 공통 설정 (모든 파일에 적용, 개별 오버라이드 가능)
defaults:
  model: "gpt-4.1"                     # LLM 모델 (info/script 파이프라인용)
  info_prompt_version: "default"       # Pipeline 1 프롬프트 버전
  script_prompt_version: "v2-tts"      # Pipeline 2 프롬프트 버전
  voice: "Zephyr"                      # Gemini TTS voice (Pipeline 3)
  tts_model: "gemini-2.5-flash-tts"  # Gemini TTS 모델
  speed: 1.0                           # TTS 속도 (주의: Gemini API 미지원)
  temperature: 0.7                     # LLM temperature (script 생성용)
  max_retries: 8                       # API 재시도 횟수
  dry_run: false                       # 테스트 모드 여부

# 생성할 파일 목록
files:
  - output_name: "1_박물관소개"
    keyword: "국립중앙박물관 역사와 위치 소개"

  - output_name: "2_전시관소개"
    keyword: "국립중앙박물관 전시관 구성과 주요 관 소개"
    info_prompt_version: "default"     # 개별 설정 오버라이드 예시
    script_prompt_version: "v1"        # 이 파일만 다른 스크립트 프롬프트 사용
```

**필수 필드**:
- `track_name`: 트랙 이름 (출력 디렉토리명으로 사용)
- `files`: 파일 목록 (각 항목은 `output_name`, `keyword` 필수)

**선택 필드**:
- `description`: 트랙 설명
- `metadata`: 작성자, 버전, 태그 등 메타정보
- `defaults`: 공통 파이프라인 설정

### 배치 실행 명령어

```bash
# 기본 실행 (순차 처리, 모든 파이프라인)
python -m src.batch_runner --track-file tracks/sample_track.yaml

# 병렬 실행 (3개 워커, 2-3배 속도 향상)
python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel

# 병렬 실행 + 워커 수 지정
python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel --max-workers 2

# Dry-run 모드 (API 호출 없이 테스트)
python -m src.batch_runner --track-file tracks/my_track.yaml --dry-run

# 병렬 + Dry-run (테스트)
python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel --dry-run

# 특정 파이프라인만 재실행
# Stage 1: 정보 검색, Stage 2: 스크립트 생성, Stage 3: 오디오 생성

# 스크립트만 재생성 (info 파일은 이미 존재)
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2

# 스크립트 + 오디오만 병렬 재생성
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2,3 --parallel

# 오디오만 재생성 (script 파일은 이미 존재)
python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 3
```

**병렬 처리 모드 (`--parallel`)**:
- 여러 파일을 동시에 처리하여 속도 향상 (2-3배)
- 기본 워커 수: 3개 (Gemini TTS API 제약)
- 먼저 완료된 워커가 다음 파일을 자동으로 처리
- 하나의 파일이라도 실패 시 전체 중단
- Ctrl+C로 중단 시 모든 워커 즉시 종료
- **주의**: API quota를 빠르게 소진할 수 있으므로 대량 배치에만 사용 권장

**선택적 파이프라인 실행 (--stages 옵션)**:
- `--stages 1`: 정보 검색만 실행
- `--stages 2`: 스크립트 생성만 실행 (info 파일 필요)
- `--stages 3`: 오디오 생성만 실행 (script 파일 필요)
- `--stages 1,2`: 정보 검색 + 스크립트 생성
- `--stages 2,3`: 스크립트 생성 + 오디오 생성
- `--stages 1,2,3`: 전체 파이프라인 (기본값)

**주의사항**:
- Stage 2를 실행하려면 Stage 1의 출력 파일(info)이 필요합니다
- Stage 3을 실행하려면 Stage 2의 출력 파일(script)이 필요합니다
- 필요한 파일이 없으면 명확한 에러 메시지와 함께 즉시 중단됩니다

**사용 예시 - 프롬프트 테스트 워크플로우**:
```bash
# 1단계: 전체 파이프라인으로 초기 생성
python -m src.batch_runner --track-file tracks/국중박_꿀팁_가이드.yaml

# 2단계: 새로운 프롬프트(v3-tts)로 스크립트만 재생성
# (info 파일은 그대로 유지, script만 새로 생성)
python -m src.batch_runner --track-file tracks/국중박_꿀팁_가이드.yaml --stages 2

# 3단계: 커스텀 프롬프트를 추가하여 재생성
# YAML 파일의 defaults에 script_gen_prompt 필드 추가 후:
python -m src.batch_runner --track-file tracks/국중박_꿀팁_가이드.yaml --stages 2

# 4단계: 스크립트 결과 확인 후 만족하면 오디오만 생성
python -m src.batch_runner --track-file tracks/국중박_꿀팁_가이드.yaml --stages 3
```

이 방식으로 비용과 시간을 절약하면서 프롬프트를 반복적으로 테스트할 수 있습니다.

**`script_gen_prompt` 사용 예시 (YAML)**:
```yaml
defaults:
  script_prompt_version: "v2-tts"
  script_gen_prompt: |
    추가 지시사항:
    - 전문적이고 학술적인 톤을 사용하세요
    - 구체적인 연도와 수치를 포함하세요
```

### 출력 디렉토리 구조

```
outputs/tracks/[트랙명]/
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
│   └── 3_앱사용꿀팁_script.mp3
└── batch_report.json         # 실행 결과 리포트
```

### 실행 결과 리포트

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
      "keyword": "국립중앙박물관 역사와 위치 소개",
      "status": "success",
      "audio_path": "outputs/tracks/꿀팁_가이드/audio/1_박물관소개.mp3",
      "started_at": "...",
      "completed_at": "..."
    }
  ]
}
```

### 에러 처리

**순차 처리 모드**:
- 파일을 순서대로 하나씩 처리
- 에러 발생 시 전체 배치 즉시 중단
- 부분 리포트 생성 (실패 시점까지의 결과)
- 상세 로그: 어느 파일의 어느 단계에서 실패했는지 명확히 표시

**병렬 처리 모드 (`--parallel`)**:
- 여러 워커가 동시에 파일 처리
- **하나의 워커라도 에러 발생 시 전체 중단**
- 실행 중인 모든 워커 즉시 취소
- 부분 리포트 생성 (완료된 파일들의 결과)
- Ctrl+C (KeyboardInterrupt) 시 모든 워커 graceful shutdown
- 워커별 로그: `[Worker-1]`, `[Worker-2]` 형식으로 표시

### 개별 파일 설정 오버라이드

`defaults`에 설정한 값을 특정 파일에서만 변경 가능:

```yaml
defaults:
  voice: "ko-KR-Neural2-A"
  speed: 1.0

files:
  - output_name: "1_일반가이드"
    keyword: "..."
    # defaults 사용 (voice: ko-KR-Neural2-A, speed: 1.0)

  - output_name: "2_어린이가이드"
    keyword: "..."
    voice: "ko-KR-Wavenet-B"      # 이 파일만 다른 목소리
    speed: 0.9                    # 이 파일만 느린 속도
```

## Working with Claude Code

**Language & Documentation:**
- Write all code comments and docstrings in Korean (한국어)
- This helps maintain consistency with the project's Korean-language focus and domain (cultural heritage)
- User-facing log messages and CLI output are in Korean

**Python Environment:**
- ALWAYS check if venv is activated before running any Python commands
- If venv is not activated, activate it first: `source .venv/bin/activate`
- Verify activation by checking if `VIRTUAL_ENV` is set or by running `which python`
- This ensures all Python commands run in the correct isolated environment
- The `setup-venv.sh` script handles pyenv + venv setup and validates versions before installing dependencies

**Testing & Debugging:**
- Use `--dry-run` flag for all pipelines to test without API calls
- Each pipeline can be run independently for debugging: `python -m src.pipelines.[pipeline_name]`
- Check outputs in `outputs/info/`, `outputs/script/`, `outputs/audio/`
- Mock outputs go to `outputs/mock/` in dry-run mode
- Use `--list-prompts` on script_gen pipeline to see available prompt templates

**Common Debugging Workflow:**
1. Run individual pipeline with `--dry-run` to verify flow
2. Check intermediate files (info.md, script.md) before next stage
3. Use custom `--output-name` to avoid overwriting production files
4. Inspect metadata files for execution details

**Context Management:**
- When using `/compact` command to compress conversation context:
  - **ALWAYS create a timestamped development log immediately after `/compact` execution**
  - Log file format: `dev-log/[log num]YYYY-MM-DD_HH-MM-SS.md`
  - Summarize all changes made, decisions taken, and current status
  - Include what was modified, why, and what remains to be done
- You can also manually request a log anytime by saying "현재까지 작업을 로그로 남겨줘"

**Documentation Structure:**
- All planning, design documents, and specifications go in `docs/` as Markdown files
- Development logs and session summaries go in `dev-log/` with timestamps
- Keep `docs/` for persistent documentation, `dev-log/` for chronological records

**Prompt Management System (통합):**

All pipelines now use a unified YAML-based prompt system:

- **Pipeline 1 (info_retrieval)**: `prompts/info_retrieval/`
  - API Type: Responses API
  - Fields: `instructions`, `input_template`, `tools`
  - Example: `default.yaml`

- **Pipeline 2 (script_gen)**: `prompts/script_generation/`
  - API Type: Chat Completions API
  - Fields: `system_prompt`, `user_prompt_template`
  - Examples: `v1.yaml`, `v2-tts.yaml`

**Adding New Prompt Templates:**

For **info_retrieval**:
1. Create `prompts/info_retrieval/[version].yaml`
2. Include: `api_type: responses`, `instructions`, `input_template`, `tools`
3. Use `{search_keyword}` placeholder in `input_template`
4. Test: `python -m src.pipelines.info_retrieval --search-keyword "테스트" --prompt-version [version] --dry-run`
5. Verify: `python -m src.pipelines.info_retrieval --list-prompts`

For **script_generation**:
1. Create `prompts/script_generation/[version].yaml`
2. Include: `api_type: chat`, `system_prompt`, `user_prompt_template`
3. Use `{info_content}` placeholder in `user_prompt_template`
4. Test: `python -m src.pipelines.script_gen --search-keyword "테스트" --script-prompt-version [version] --dry-run`
5. Verify: `python -m src.pipelines.script_gen --list-prompts`

**Using custom prompts**:
- Add `script_gen_prompt` field in YAML for batch execution
- Or use `--custom-prompt` flag for CLI execution
- Custom prompt is appended as plain text after the base template prompt

**Prompt Optimization Workflow:**

Use the interactive Jupyter notebook for testing and comparing prompts:
```bash
cd notebooks
jupyter notebook prompt_optimizer.ipynb
```

Features:
- Edit prompts directly in cells and test immediately
- Save results with timestamps to `test_results/`
- Compare multiple prompt versions side-by-side
- Track metrics (length, quality, tone)

## Environment Variables

Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_api_key_here

# OR for Google Cloud Text-to-Speech (if using google-cloud-texttospeech):
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

**API 키 발급:**
- OpenAI: https://platform.openai.com/api-keys
- Gemini API (google-genai): https://aistudio.google.com/apikey
- Google Cloud (google-cloud-texttospeech): Requires service account JSON from Google Cloud Console

**Authentication methods for Pipeline 3 (Audio):**
- If using `google-genai` SDK: Set `GEMINI_API_KEY` in `.env`
- If using `google-cloud-texttospeech` SDK: Set `GOOGLE_APPLICATION_CREDENTIALS` or use `gcloud auth login`

## Troubleshooting

**Common Issues:**

1. **"ModuleNotFoundError" or import errors**
   - Solution: Ensure venv is activated (`source .venv/bin/activate`)
   - Check: `which python` should point to `.venv/bin/python`
   - Reinstall: `./setup-venv.sh`

2. **API authentication errors**
   - Verify `.env` file exists in project root
   - Check API keys are set: `cat .env | grep API_KEY`
   - For dry-run mode, API keys are not required

3. **"File not found" errors when using --stages**
   - Stage 2 requires Stage 1 output (info file must exist)
   - Stage 3 requires Stage 2 output (script file must exist)
   - Solution: Run earlier stages first or use full pipeline

4. **Gemini TTS errors (Pipeline 3)**
   - **Model not found error (404)**: The model name `gemini-2.5-flash-tts` may not be available. Check Google's documentation for current TTS model names.
   - Check GEMINI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS is set correctly
   - Note: `speed` parameter is currently unsupported by Gemini API
   - Try different voice names from supported list (Zephyr, Puck, Charon, etc.)
   - Verify which Google TTS API is being used (google-cloud-texttospeech vs google-genai SDK)

5. **YAML parsing errors in batch runner**
   - Validate YAML syntax using `python -c "import yaml; yaml.safe_load(open('tracks/your_file.yaml'))"`
   - Ensure required fields exist: `track_name`, `files` with `output_name` and `keyword`
   - Check indentation is consistent (use spaces, not tabs)

**Performance Issues:**
- Use `--dry-run` for testing without API costs
- Batch runner processes files sequentially (by design for stability)
- Consider using `--stages` to skip already-completed stages
