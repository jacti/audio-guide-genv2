"""
정보 검색 파이프라인 (Pipeline 1)

입력된 문화유산 키워드를 기반으로 LLM을 활용해 정보를 수집하고,
구조화된 Markdown 파일로 저장한다.

주요 기능:
- OpenAI GPT 모델을 활용한 문화유산 정보 검색 및 요약
- YAML 기반 프롬프트 템플릿 시스템 지원 (버전별 관리 가능)
- 서론, 역사/배경, 특징, 추가 사실, 참고 문헌 등 구조화된 Markdown 생성
- outputs/info/ 디렉토리에 파일 저장
- 에러 처리 및 dry_run 모드 지원
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

from src.utils.path_sanitizer import info_markdown_path
from src.utils.metadata import create_metadata
from src.utils.prompt_loader import load_prompt, list_prompts

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 기본 설정
DEFAULT_OUTPUT_DIR = Path("outputs/info")
DEFAULT_MOCK_OUTPUT_DIR = Path("outputs/mock/info")
# [TODO] 4.1추천 -> 
DEFAULT_MODEL = "gpt-4.1"


def _validate_api_key() -> str:
    """
    OpenAI API 키 유효성 검증

    Returns:
        str: 유효한 API 키

    Raises:
        ValueError: API 키가 없거나 비어있을 경우
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 API 키를 추가해주세요."
        )
    return api_key


def _search_with_llm(
    search_keyword: str,
    model: str = DEFAULT_MODEL,
    prompt_version: str = "default"
) -> str:
    """
    OpenAI LLM을 활용해 문화유산 정보를 검색하고 요약한다.

    Args:
        search_keyword: 검색할 문화유산 키워드
        model: 사용할 OpenAI 모델명
        prompt_version: 프롬프트 템플릿 버전 (기본값: "default")

    Returns:
        str: LLM이 생성한 구조화된 정보

    Raises:
        Exception: API 호출 실패 시
    """
    api_key = _validate_api_key()
    client = OpenAI(api_key=api_key)

    # YAML 프롬프트 템플릿 로드
    try:
        prompt_template = load_prompt(
            version=prompt_version,
            pipeline_type="info_retrieval"
        )
        logger.info(f"프롬프트 템플릿 로드 완료: {prompt_template.name} (버전: {prompt_version})")
        logger.info(f"프롬프트 설명: {prompt_template.description}")
        logger.info(f"API 타입: {prompt_template.api_type}")
    except FileNotFoundError as e:
        logger.error(f"프롬프트 템플릿 로드 실패: {e}")
        available = list_prompts(pipeline_type="info_retrieval")
        logger.info(f"사용 가능한 버전: {', '.join(available)}")
        raise

    logger.info(f"LLM 검색 시작: {search_keyword} (모델: {model})")

    try:
        # Responses API 사용 (웹 검색 기능 포함)
        # YAML 템플릿에서 프롬프트와 tools 가져오기
        response = client.responses.create(
            model=model,
            instructions=prompt_template.instructions,
            input=prompt_template.format_input(keyword=search_keyword),
            tools=prompt_template.tools
        )

        content = response.output_text
        logger.info(f"LLM 검색 완료: {len(content)} 글자")
        return content

    except Exception as e:
        logger.error(f"LLM 검색 실패: {e}")
        raise


def _get_mock_data(search_keyword: str) -> str:
    """
    dry_run 모드용 목업 데이터 생성

    Args:
        search_keyword: 문화유산 키워드

    Returns:
        str: 목업 Markdown 데이터
    """
    return f"""# {search_keyword}

## 개요
이것은 '{search_keyword}'에 대한 테스트용 목업 데이터입니다.
실제 API 호출 대신 반환되는 샘플 데이터입니다.

## 역사 및 배경
- **시대**: 고려시대 (12세기)
- **제작 시기**: 약 1150년경
- **역사적 의미**: 고려청자의 전성기를 대표하는 작품

## 주요 특징
- **외형**: 우아한 곡선과 비취색 유약
- **기술**: 상감 기법의 정교함
- **예술성**: 구름과 학 문양의 조화로운 배치

## 추가 정보
- **소장처**: 국립중앙박물관
- **지정**: 국보 제68호
- **특이사항**: 고려청자 중 가장 완성도 높은 작품으로 평가

## 참고 자료
- 국립중앙박물관 소장품 데이터베이스
- 한국민족문화대백과사전
- 문화재청 국가문화유산포털
"""


def run(
    search_keyword: str,
    *,
    output_dir: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    prompt_version: str = "default",
    dry_run: bool = False,
    output_name: Optional[str] = None
) -> Path:
    """
    정보 검색 파이프라인 실행

    주어진 키워드에 대한 문화유산 정보를 검색하고,
    구조화된 Markdown 파일로 저장한다.

    Args:
        search_keyword: 검색할 문화유산 키워드
        output_dir: 출력 디렉토리 (기본값: outputs/info)
        model: 사용할 OpenAI 모델명 (기본값: gpt-4.1)
        prompt_version: 프롬프트 템플릿 버전 (기본값: "default")
        dry_run: True일 경우 API 호출 없이 목업 데이터 사용
        output_name: 파일명으로 사용할 이름 (선택적, 미제공 시 search_keyword 사용)

    Returns:
        Path: 생성된 Markdown 파일의 절대 경로

    Raises:
        ValueError: API 키가 없거나 키워드가 비어있을 경우
        Exception: API 호출 실패 또는 파일 저장 실패 시

    Example:
        >>> from pathlib import Path
        >>> output_path = run("청자 상감운학문 매병")
        >>> print(f"저장 완료: {output_path}")
        >>> output_path = run("국립 중앙 박물관에 있는 사유의 방", output_name="사유의방")
        >>> print(f"저장 완료: {output_path}")  # outputs/info/사유의방.md
    """
    # 입력 검증
    if not search_keyword or not search_keyword.strip():
        raise ValueError("키워드는 비어있을 수 없습니다.")

    search_keyword = search_keyword.strip()
    mode = "dry_run" if dry_run else "production"
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}정보 검색 파이프라인 시작: {search_keyword}")
    logger.info(f"프롬프트 버전: {prompt_version}")

    # 출력 디렉토리 설정: dry_run 모드일 경우 outputs/mock/info/ 사용
    if output_dir is None:
        output_dir = DEFAULT_MOCK_OUTPUT_DIR if dry_run else DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {output_dir.absolute()}")

    # 정보 검색
    if dry_run:
        logger.info("DRY RUN 모드: 목업 데이터 사용")
        content = _get_mock_data(search_keyword)
    else:
        content = _search_with_llm(search_keyword, model=model, prompt_version=prompt_version)

    # 파일 경로 생성 (공통 헬퍼 사용)
    output_path = info_markdown_path(search_keyword, output_dir, output_name)

    try:
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"파일 저장 완료: {output_path.absolute()}")
    except Exception as e:
        logger.error(f"파일 저장 실패: {e}")
        raise

    # 메타데이터 생성
    try:
        create_metadata(
            search_keyword=search_keyword,
            pipeline="info_retrieval",
            output_file_path=output_path,
            mode=mode,
            model=model if not dry_run else None
        )
    except Exception as e:
        logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")

    return output_path.absolute()


def main():
    """
    CLI 진입점

    argparse를 사용해 명령줄에서 키워드를 입력받아 파이프라인을 실행한다.

    Example:
        $ python -m src.pipelines.info_retrieval --search-keyword "청자 상감운학문 매병"
        $ python -m src.pipelines.info_retrieval --search-keyword "석굴암" --dry-run
        $ python -m src.pipelines.info_retrieval --list-prompts
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="문화유산 정보 검색 파이프라인 (YAML 프롬프트 시스템 지원)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 사용
  python -m src.pipelines.info_retrieval --search-keyword "청자 상감운학문 매병"

  # 프롬프트 버전 지정
  python -m src.pipelines.info_retrieval --search-keyword "석굴암" --prompt-version default

  # Dry-run 모드
  python -m src.pipelines.info_retrieval --search-keyword "훈민정음" --dry-run

  # 사용 가능한 프롬프트 버전 확인
  python -m src.pipelines.info_retrieval --list-prompts
        """
    )

    parser.add_argument(
        "--search-keyword",
        type=str,
        help="검색할 문화유산 키워드"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"출력 디렉토리 (기본값: {DEFAULT_OUTPUT_DIR})"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"사용할 OpenAI 모델 (기본값: {DEFAULT_MODEL})"
    )

    parser.add_argument(
        "--prompt-version",
        type=str,
        default="default",
        help="프롬프트 템플릿 버전 (기본값: default)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API 호출 없이 목업 데이터로 테스트"
    )

    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="파일명으로 사용할 이름 (미제공 시 search_keyword 사용)"
    )

    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="사용 가능한 프롬프트 버전 목록 출력"
    )

    args = parser.parse_args()

    # 프롬프트 목록 출력 모드
    if args.list_prompts:
        print("\n사용 가능한 프롬프트 버전:")
        print("="*70)
        for version in list_prompts(pipeline_type="info_retrieval"):
            try:
                template = load_prompt(version, pipeline_type="info_retrieval")
                print(f"\n📝 {version}:")
                print(f"    이름: {template.name}")
                print(f"    설명: {template.description}")
                print(f"    API 타입: {template.api_type}")
                print(f"    태그: {', '.join(template.tags)}")
            except Exception as e:
                print(f"\n❌ {version}: (로드 실패 - {e})")
        print("\n" + "="*70)
        print("\n💡 사용 예시:")
        print('  python -m src.pipelines.info_retrieval --search-keyword "청자 매병" --prompt-version default')
        print("="*70)
        return

    # search_keyword 필수 체크
    if not args.search_keyword:
        parser.error("--search-keyword 인자가 필요합니다 (또는 --list-prompts 사용)")

    try:
        output_path = run(
            search_keyword=args.search_keyword,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            model=args.model,
            prompt_version=args.prompt_version,
            dry_run=args.dry_run,
            output_name=args.output_name
        )

        print(f"\n✅ 정보 검색 완료!")
        print(f"📄 파일 위치: {output_path}")
        print(f"프롬프트 버전: {args.prompt_version}")
        print(f"\n다음 단계: 생성된 파일을 확인하세요.")
        print(f"  cat {output_path}")

    except ValueError as e:
        print(f"❌ 입력 오류: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ 실행 실패: {e}")
        logger.exception("파이프라인 실행 중 오류 발생")
        exit(1)


if __name__ == "__main__":
    main()
