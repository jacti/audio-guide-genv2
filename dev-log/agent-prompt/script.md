너는 Claude Code 기반 서브에이전트이며 `script_gen_v2` 리포지토리의 스크립
  트 작성 파이프라인(v0.1)을 전담 구현한다. 작업 전 아래 문서를 반드시 숙지
  해라.
  - `docs/claude-squad.md`: 3개 파이프라인을 병렬 개발하는 구조이며, 너는 2️⃣
  스크립트 작성 파이프라인 담당.
  - `docs/plan.md` 2절: `/outputs/info/[keyword].md`를 입력으로 받아 오디오가
  이드 스크립트를 생성해 `/outputs/script/[keyword]_script.md`에 저장하는 단
  계가 목표.
  - `.claude/CLAUDE.md`: 한국어 주석/문서화, venv 사용, 파일 I/O 계약 준수 등
  프로젝트 공통 개발 가이드.

  🎯 목표
  정보 검색 파이프라인이 생성한 Markdown 정보를 읽어 1분 내외의 오디오 가이드
  스크립트를 작성하고 `outputs/script/`에 저장한다. 톤은 친절하고 시각적 이미
  지를 그리도록 구성하며, 후속 오디오 파이프라인이 그대로 활용할 수 있는 구조
  화된 결과를 제공해야 한다.

  📦 필수 산출물
  1. `src/pipelines/script_gen.py`
     - 모듈 수준 public 엔트리포인트(예: `run(keyword: str, *, info_dir: Path
  | None = None, output_dir: Path | None = None, dry_run: bool = False) ->
  Path`) 또는 `ScriptGenerationPipeline` 클래스 구현.
     - `/outputs/info/`에 존재하는 원본 정보 Markdown을 읽어들여 핵심 섹션을
  파싱/요약한 뒤, LLM(OpenAI `gpt-4o-mini` 계열) 호출로 오디오 가이드 스크립
  트를 생성. API 키는 `.env`(`OPENAI_API_KEY`)에서 로드.
     - 프롬프트 빌더 함수를 별도 정의해 톤/길이/구성 요소(인사, 본문, 마무리
  등)를 명시하고, 재사용 가능한 템플릿을 유지.
     - Markdown 출력 규칙: 제목, 인트로, 본문(최소 3개 소제목), 마무리/호흡
  안내 등을 포함. 오디오 세그먼트별로 말하는 속도나 감정 힌트를 괄호로 표기해
  도 좋다.
     - 파일명 규칙: 기본 경로는 `Path("outputs/script")`, 디렉터리 없으면 생
  성. 파일명은 `{keyword}_script.md`(공백→`_`). 실제 저장 경로와 slug를 반환.
     - 예외 처리: 정보 파일 없음, API Key 미설정, LLM 실패 등에 대해 명확한
  오류 메시지. `dry_run=True`면 고정 템플릿 데이터를 생성하도록 설계.
     - 타입 힌트, 한국어 docstring/주석, `logging` 기반 상태 로그.

  2. 필요 시 `src/pipelines/__init__.py`에서 엔트리포인트 export.

  3. 자가 테스트용 진입점
     - `if __name__ == "__main__":` 혹은 `argparse` CLI (`python src/
  pipelines/script_gen.py --keyword "청자 상감운학문 매병"`).
     - 실행 시 입력 파일 존재 여부 확인, 생성된 스크립트 경로 및 요약 정보를
  콘솔에 출력.

  🧪 검증 가이드
  - venv 활성화 상태에서 `python src/pipelines/script_gen.py --keyword "테스
  트"` 실행.
  - `outputs/info/테스트.md`가 없을 경우 적절한 에러를 반환하는지, `dry_run`
  옵션으로 모의 파일이 만들어지는지 확인.
  - 결과 Markdown이 문법적/구조적으로 타당한지 점검(제목, 소제목, 문단, 리스
  트 등).

  ⚙️ 기타 주의사항
  - 다른 파이프라인 파일은 수정하지 말 것. 필요한 최소 범위만 변경.
  - LLM 호출 시 재시도 로직이나 temperature 조절 가능하도록 파라미터화.
  - 후속 오디오 파이프라인이 문장 단위로 처리하기 쉽도록 문장부호와 줄바꿈을
  명확히 유지.
  - 실행 과정과 결정 사항, 테스트 결과는 필요 시 `dev-log`에 기록.
  - 생성된 스크립트는 Git 커밋 대상에서 제외할지 여부를 판단해 로그로 남겨라.

  이 요구사항을 반영해 스크립트 작성 파이프라인 모듈을 완성하라. 불명확한 부
  분은 반드시 질문으로 확인하고 진행 상황은 로그에 남겨라.

  🎯 현재 상황
  - 1차 개발은 완료되었고 테스트 중인 단계이다. 추가 명령을 대기하라.