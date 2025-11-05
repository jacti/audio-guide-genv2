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
- `openai` - For LLM API calls and TTS generation
- `python-dotenv` - Environment variable management (requires `.env` file with API keys)
- `langchain-openai` - For prompt/chain structures (optional but recommended)
- `exa-py` - Web search SDK (currently commented out in requirements.txt)

## Architecture

### Three-Stage Pipeline Design

Each pipeline stage is independent and communicates through file I/O:

**Pipeline 1: Information Retrieval** (`src/pipelines/info_retrieval.py`)
- Input: Artifact keyword (user input)
- Process: Uses GPT or LangChain + Exa.ai to search and summarize web information
- Output: Markdown file in `/outputs/info/[keyword].md`
- Extension point: Domain-specific retriever can be swapped in

**Pipeline 2: Script Generation** (`src/pipelines/script_gen.py`)
- Input: `/outputs/info/[keyword].md`
- Process: Uses LLM to transform information into audio guide script (1 min duration, friendly tone, visual imagery)
- Output: Script markdown in `/outputs/script/[keyword]_script.md`
- Extension point: Tone/style parameters, length control, session segmentation

**Pipeline 3: Audio Generation** (`src/pipelines/audio_gen.py`)
- Input: `/outputs/script/[keyword]_script.md`
- Process: OpenAI TTS API conversion (model: "gpt-4o-mini-tts", voice: "alloy")
- Output: MP3 file in `/outputs/audio/[keyword].mp3`
- Extension point: Voice selection, BGM mixing (future: Suno integration)

### Main Entry Point

`src/main.py` orchestrates the full pipeline:

```bash
python src/main.py --keyword "청자 상감운학문 매병"
```

Expected output flow:
```
[1/3] 정보 검색 완료 → outputs/info/청자 상감운학문 매병.md
[2/3] 스크립트 생성 완료 → outputs/script/청자 상감운학문 매병_script.md
[3/3] 오디오 생성 완료 → outputs/audio/청자 상감운학문 매병.mp3
✅ 전체 파이프라인 완료!
```

## Directory Structure

```
script_gen_v2/
├── .claude/                # Claude Code configuration & context
│   └── CLAUDE.md          # This file
├── src/
│   ├── main.py            # Pipeline orchestration
│   └── pipelines/
│       ├── info_retrieval.py    # Stage 1
│       ├── script_gen.py        # Stage 2
│       └── audio_gen.py         # Stage 3
├── outputs/
│   ├── info/              # Stage 1 output (markdown)
│   ├── script/            # Stage 2 output (scripts)
│   └── audio/             # Stage 3 output (mp3 files)
├── docs/
│   └── plan.md            # Detailed design document
└── dev-log/               # Development logs
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

**Python Environment:**
- ALWAYS check if venv is activated before running any Python commands
- If venv is not activated, activate it first: `source .venv/bin/activate`
- Verify activation by checking if `VIRTUAL_ENV` is set or by running `which python`
- This ensures all Python commands run in the correct isolated environment

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

## Environment Variables

Create a `.env` file in the project root with:
```
OPENAI_API_KEY=your_key_here
# Add EXA_API_KEY when enabling web search
```
