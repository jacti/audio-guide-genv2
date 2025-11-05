너는 Claude Code 기반 서브에이전트이며 `script_gen_v2` 리포지토리의 정보 검색 파이프라인(v0.1)을 전담 구현한
  다. 작업 전 아래 메모를 숙지해라.
  - `docs/claude-squad.md`: 3개 파이프라인을 병렬 개발하며, 너는 1️⃣ 정보 검색 파이프라인 담당.
  - `docs/plan.md` 1절: 입력 키워드 → `/outputs/info/[keyword].md` 형식의 Markdown 정리본을 만드는 단계가 목표.
  - `.claude/CLAUDE.md`: 한국어 주석/문서화, venv 사용, 파이프라인 간 파일 I/O 계약 준수 등 개발 가이드.

  🎯 목표
  키워드를 입력받아 문화유산 정보를 수집·요약하고 `outputs/info/`에 Markdown 파일을 저장하는 모듈을 완성한다. 후
  속 파이프라인이 재사용할 수 있는 안정적인 인터페이스가 필요하다.

  📦 필수 산출물
  1. `src/pipelines/info_retrieval.py`
     - 모듈 수준의 public 엔트리포인트 함수(예: `run(keyword: str, *, output_dir: Path | None = None) -> Path`)
  또는 `InfoRetrievalPipeline` 클래스 구현.
     - OpenAI 기반 LLM 호출 로직: `OPENAI_API_KEY` 를 `.env`에서 불러오고, 기본 모델은 `gpt-4o-mini` 계열로 설
  정. 추후 Exa/Wiki 확장을 고려해 호출부를 함수로 분리해라.
     - Markdown 생성 규칙: 서론, 역사/배경, 특징, 추가 사실, 참고 문헌 섹션 등을 포함해 구조화. key-value 표나
  bullet을 활용해 가독성 있게 작성.
     - 파일 저장: 기본 경로는 `Path("outputs/info")`, 디렉터리가 없으면 생성. 파일명은 기본적으로 원본 키워드를
  유지하되, OS 호환성을 위해 공백을 `_`로 변환한 slug도 함께 반환하거나 내부적으로 보관.
     - 에러 처리: API Key 누락이나 실패 시 명확한 예외 메시지를 제공하고, 옵션으로 `dry_run=True`일 때는 하드코
  딩된 목업 데이터를 반환하도록 설계하면 좋다.
     - 타입 힌트, 한국어 docstring/주석, `logging` 활용.

  2. 필요 시 `src/pipelines/__init__.py`에서 위 엔트리포인트를 export해라.

  3. 자가 테스트용 진입점
     - `if __name__ == "__main__":` 혹은 `argparse` 기반 CLI (`python src/pipelines/info_retrieval.py --keyword
  "청자 상감운학문 매병"` 형태) 추가.
     - 실행 결과와 생성된 파일 경로를 콘솔에 출력.
  🧪 검증 가이드
  - venv가 활성화되어 있다는 가정하에 `python src/pipelines/info_retrieval.py --keyword "테스트"` 명령으로 동작
  확인.
  남겨라.
  - 주요 결정이나 한계는 `dev-log`에 기록(필요 시).