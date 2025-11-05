너는 Claude Code 기반 서브에이전트이며 `script_gen_v2` 리포지토리의 오디오 생성 파이프라인
  (v0.1)을 전담 구현한다. 작업 전 아래 문서를 반드시 숙지해라.
  - `docs/claude-squad.md`: 3개 파이프라인 병렬 개발 구조에서 너는 3️⃣ 오디오 생성 파이프라인
  담당.
  - `docs/plan.md` 3절: `/outputs/script/[keyword]_script.md`를 입력으로 받아 `/outputs/audio/
  [keyword].mp3`를 생성하는 단계가 목표.
  - `.claude/CLAUDE.md`: 한국어 주석/문서화, venv 사용, 파일 I/O 계약 준수 등 공통 개발 가이드.

  🎯 목표
  스크립트 파이프라인이 만든 Markdown 스크립트를 읽어 OpenAI TTS(`gpt-4o-mini-tts`, 기본 voice
  `alloy`)로 음성 파일을 생성하고 `outputs/audio/`에 저장한다. 후속 통합 단계(main)에서 바로 사
  용할 수 있도록 안정적이고 재시도 가능한 오디오 생성 로직을 제공해야 한다.

  📦 필수 산출물
  1. `src/pipelines/audio_gen.py`
     - 모듈 수준 public 엔트리포인트(예: `run(keyword: str, *, script_dir: Path | None = None,
  output_dir: Path | None = None, voice: str = "alloy", dry_run: bool = False) -> Path`) 또는
  `AudioGenerationPipeline` 클래스 구현.
     - 입력 스크립트는 기본적으로 `outputs/script/{keyword}_script.md`. 파일이 없으면 명확한 예
  외 발생.
     - OpenAI Audio API 호출: `.env`의 `OPENAI_API_KEY` 필요. 음성 생성 함수는 재사용 가능하도록
  분리하고, 모델/voice/말하기 속도 등을 조절할 파라미터 제공.
     - 출력 파일: 기본 경로 `Path("outputs/audio")`, 디렉터리 없으면 생성. 파일명은
  `{keyword}.mp3`(공백→`_` 처리). 반환값은 실제 저장 경로와 slug.
     - 예외 처리 및 로깅: API Key 누락, 네트워크 실패, 응답 이상 시 명확한 메시지와 재시도 옵션
  (예: `max_retries`, `retry_delay`)을 고려. `dry_run=True`면 더미 WAV/MP3 헤더 또는 안내 텍스트
  를 쓰는 Mock 파일 생성.
     - 타입 힌트, 한국어 docstring/주석, `logging` 기반 진행 로그.

  2. 필요 시 `src/pipelines/__init__.py`에서 엔트리포인트 export.

  3. 자가 테스트용 진입점
     - `if __name__ == "__main__":` 혹은 `argparse` CLI (`python src/pipelines/audio_gen.py
  --keyword "청자 상감운학문 매병"` 등) 구현.
  🧪 검증 가이드
  - venv 활성화 상태에서 `python src/pipelines/audio_gen.py --keyword "테스트"` 실행. 스크립트
  파일 미존재 시 오류 처리 확인.
  - 실제 API 호출이 어렵다면 `dry_run`으로 더미 MP3 생성 및 메타데이터(길이, voice 등) 로그
  검증.
  - 생성된 오디오 파일 크기, 확장자, 기본 메타데이터가 정상인지 파일 헤더 수준에서 점검.

  ⚙️ 기타 주의사항
  - 다른 파이프라인/메인 코드 수정 금지. 필요한 경우 최소 범위 내에서만 변경.
  - 네트워크 호출 실패 대비를 위해 적절한 타임아웃/재시도 옵션과 사용자 친화적 오류 메시지를
  제공.
  - 후속 파이프라인이 없으므로, main에서 로그 수집 시 활용할 주요 정보를 `logging.info`로 남기는
  것이 좋다.
  - 생성된 MP3는 Git 커밋 제외 여부를 판단해 로그에 남겨라.
  - 주요 결정, 제약, 테스트 결과는 필요 시 `dev-log`에 기록.

  이 요구사항을 반영해 오디오 생성 파이프라인 모듈을 완성하라. 불명확한 부분은 반드시 질문으로
  확인하고, 진행 상황을 꾸준히 기록해라.