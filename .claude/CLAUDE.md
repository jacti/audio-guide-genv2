# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an audio guide generation pipeline for cultural heritage artifacts. The system takes a cultural artifact name (e.g., "청자 상감운학문 매병") and automatically generates an audio guide file through three independent stages:

1. **Information Retrieval** → `/outputs/info/[keyword].md`
2. **Script Generation** → `/outputs/script/[keyword]_script.md`
3. **Audio Synthesis** → `/outputs/audio/[keyword].mp3`

Each pipeline stage is designed to be independently extensible and can be run separately or as part of the full workflow.

## Environment Setup

This project uses pyenv for Python version management and a `.venv` virtual environment.

**Initial setup:**
```bash
# Run the setup script (handles pyenv, venv, and dependencies)
./setup-venv.sh

# Activate the virtual environment (if not already active)
source .venv/bin/activate
```

**After pulling changes:**
```bash
# Ensure venv is activated, then run setup script to update dependencies
source .venv/bin/activate
./setup-venv.sh
```

**Python version:** See `.python-version` file (currently 3.12.12)

**Key dependencies:**
- `openai>=1.0.0` - For LLM API calls and TTS generation (SDK 1.x+ required)
- `python-dotenv>=1.0.0` - Environment variable management (requires `.env` file with API keys)
- `pyyaml>=6.0.0` - For YAML-based prompt template parsing
- `langchain-openai>=0.1.0` - For prompt/chain structures (optional but recommended)
- `perplexityai` - Web search SDK (Perplexity AI integration)
- `backoff>=2.0.0` - Exponential backoff for API retry logic
- `exa-py>=1.0.0` - Alternative web search SDK (currently unused)

## Architecture

### Three-Stage Pipeline Design

Each pipeline stage is independent and communicates through file I/O:

**Pipeline 1: Information Retrieval** (`src/pipelines/info_retrieval.py`)
- Input: Artifact keyword (user input)
- Process: Uses GPT or LangChain + Perplexity AI (`perplexityai` package) to search and summarize web information
- Output: Markdown file in `/outputs/info/[keyword].md`
- Extension point: Domain-specific retriever can be swapped in
- CLI: `python -m src.pipelines.info_retrieval --keyword "유물명" [--dry-run]`

**Pipeline 2: Script Generation** (`src/pipelines/script_gen.py`)
- Input: `/outputs/info/[keyword].md`
- Process: Uses LLM to transform information into audio guide script (1 min duration, friendly tone, visual imagery)
- Prompt system: YAML-based templates in `/prompts/script_generation/` (loaded via `src.utils.prompt_loader`)
- Current default: `v2-tts` (TTS-optimized, no markdown headers)
- Output: Script markdown in `/outputs/script/[keyword]_script.md`
- Extension point: Tone/style parameters, length control, session segmentation
- CLI: `python -m src.pipelines.script_gen --keyword "유물명" --prompt-version v2-tts [--dry-run]`
- List prompts: `python -m src.pipelines.script_gen --list-prompts`

**Pipeline 3: Audio Generation** (`src.pipelines/audio_gen.py`)
- Input: `/outputs/script/[keyword]_script.md`
- Process: OpenAI TTS API conversion with exponential backoff retry logic (`backoff` package)
- Default model: "gpt-4o-mini-tts", voice: "alloy", speed: 1.0
- Output: MP3 file in `/outputs/audio/[keyword].mp3`
- Extension point: Voice selection (alloy/echo/fable/onyx/nova/shimmer), speed adjustment, BGM mixing
- CLI: `python -m src.pipelines.audio_gen --keyword "유물명" --voice alloy --speed 1.0 [--dry-run]`

### Shared Utilities

**Path Sanitization** (`src/utils/path_sanitizer.py`)
- Centralizes filename generation logic for all three pipelines
- Functions: `info_markdown_path()`, `script_markdown_path()`, `audio_output_path()`
- Removes filesystem-unsafe characters while preserving spaces
- All pipelines use `output_name` parameter for custom naming (overrides keyword)

**Prompt Loading** (`src/utils/prompt_loader.py`)
- YAML-based prompt template system for script generation
- Templates contain: `system_prompt`, `user_prompt_template`, `parameters`, `tags`
- Auto-discovers prompts in `prompts/script_generation/*.yaml`

**Metadata Tracking** (`src/utils/metadata.py`)
- Records pipeline execution details (keyword, model, timestamp, mode)
- Used for audit trails and debugging

### Main Entry Point

`src/main.py` orchestrates the full pipeline:

```bash
# Basic usage
python -m src.main --keyword "청자 상감운학문 매병"

# With custom settings
python -m src.main --keyword "석굴암" \
  --model gpt-4o \
  --prompt-version v2-tts \
  --voice nova \
  --speed 1.1 \
  --temperature 0.7 \
  --max-retries 8

# Dry-run mode (no API calls, uses mock data)
python -m src.main --keyword "사유의 방" --dry-run

# Custom output naming
python -m src.main --keyword "청자 매병" --output-name "celadon_vase_01"
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
- `--output-name`: Override filename (default uses keyword with sanitization)
- All pipelines support independent CLI execution for debugging specific stages

## Directory Structure

```
script_gen_v2/
├── .claude/                # Claude Code configuration & context
│   └── CLAUDE.md          # This file
├── src/
│   ├── main.py            # Pipeline orchestration (runs all 3 stages)
│   ├── pipelines/
│   │   ├── info_retrieval.py    # Stage 1: Web search & summarization
│   │   ├── script_gen.py        # Stage 2: LLM script generation
│   │   └── audio_gen.py         # Stage 3: TTS conversion
│   └── utils/
│       ├── prompt_loader.py     # YAML prompt template loader
│       ├── path_sanitizer.py    # Filename sanitization logic
│       └── metadata.py          # Execution metadata tracking
├── prompts/
│   └── script_generation/       # YAML prompt templates (v1, v2, v2-tts)
├── outputs/
│   ├── info/              # Stage 1 output (markdown info files)
│   ├── script/            # Stage 2 output (audio guide scripts)
│   ├── audio/             # Stage 3 output (mp3 files)
│   └── mock/              # Dry-run mode outputs
├── docs/
│   ├── plan.md            # Detailed design document
│   └── commands/          # Command reference YAML files
├── dev-log/               # Development logs (timestamped)
├── setup-venv.sh          # Automated venv setup script
├── requirements.txt       # Python dependencies
└── .python-version        # pyenv Python version (3.12.12)
```

## Development Guidelines

**Current Version (v0.1):** This is an MVP focused on validating the entire '입력 → md 정보 → 스크립트 → mp3 오디오' workflow with minimal features.

**When adding new features:**
- Each pipeline stage should remain independently executable
- File-based I/O between stages is intentional for debugging and extensibility
- Follow the input/output contract for each pipeline stage

**Planned extensions (v0.2+):**
- Enhanced search sources: Exa.ai → Wikipedia → museum.go.kr API
- Tone variations: 감성/교육/아동용 styles
- BGM auto-mixing with Suno
- Metadata tracking (JSON format)
- UI layer: Streamlit or Next.js interface

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

**Adding New Prompt Templates:**
1. Create a new YAML file in `prompts/script_generation/[version].yaml`
2. Include: `name`, `description`, `tags`, `parameters`, `system_prompt`, `user_prompt_template`
3. Use `{info_content}` placeholder in `user_prompt_template` for info file content
4. Test with: `python -m src.pipelines.script_gen --keyword "테스트" --prompt-version [version] --dry-run`
5. Verify with `--list-prompts`

## Environment Variables

Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_key_here
# Add EXA_API_KEY when enabling web search
```
