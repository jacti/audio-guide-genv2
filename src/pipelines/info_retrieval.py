"""
정보 검색 파이프라인 (Pipeline 1)

입력된 문화유산 키워드를 기반으로 LLM을 활용해 정보를 수집하고,
구조화된 Markdown 파일로 저장한다.

주요 기능:
- OpenAI GPT 모델을 활용한 문화유산 정보 검색 및 요약
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


def _search_with_llm(keyword: str, model: str = DEFAULT_MODEL) -> str:
    """
    OpenAI LLM을 활용해 문화유산 정보를 검색하고 요약한다.

    Args:
        keyword: 검색할 문화유산 키워드
        model: 사용할 OpenAI 모델명

    Returns:
        str: LLM이 생성한 구조화된 정보

    Raises:
        Exception: API 호출 실패 시
    """
    api_key = _validate_api_key()
    client = OpenAI(api_key=api_key)

    # Structured output ->  
    # 프롬프트 구성: 구조화된 Markdown 생성 요청
    system_prompt = """당신은 한국 문화유산 전문가입니다.
주어진 문화유산에 대해 정확하고 체계적인 정보를 제공해주세요.

유물의 경우 응답은 반드시 아래 형식의 Markdown으로 작성해주세요:

# {문화유산 이름}

## 개요
간단한 소개 (2-3문장)

## 역사 및 배경
- 시대적 배경
- 제작 시기 및 장소
- 역사적 의미

## 주요 특징
- 외형적 특징
- 기술적 특징
- 예술적 가치

## 추가 정보
- 현재 소장처
- 지정 문화재 정보 (해당하는 경우)
- 관련 일화나 흥미로운 사실

## 참고 자료
- 주요 출처나 참고할 만한 정보

그 외의 경우 자유롭게 정리하여 Markdown으로 작성해주세요.
"""

    logger.info(f"LLM 검색 시작: {keyword} (모델: {model})")

    try:
        # responses API 사용 (웹 검색 기능 포함)
        response = client.responses.create(
            model=model,
            instructions=system_prompt,
            input=f"'{keyword}'에 대한 상세한 정보를 작성해주세요.",
            tools=[{"type": "web_search_preview"}]
        )

        content = response.output_text
        logger.info(f"LLM 검색 완료: {len(content)} 글자")
        return content

    except Exception as e:
        logger.error(f"LLM 검색 실패: {e}")
        raise


def _get_mock_data(keyword: str) -> str:
    """
    dry_run 모드용 목업 데이터 생성

    Args:
        keyword: 문화유산 키워드

    Returns:
        str: 목업 Markdown 데이터
    """
    return f"""# {keyword}

## 개요
이것은 '{keyword}'에 대한 테스트용 목업 데이터입니다.
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
    keyword: str,
    *,
    output_dir: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    dry_run: bool = False
) -> Path:
    """
    정보 검색 파이프라인 실행

    주어진 키워드에 대한 문화유산 정보를 검색하고,
    구조화된 Markdown 파일로 저장한다.

    Args:
        keyword: 검색할 문화유산 키워드
        output_dir: 출력 디렉토리 (기본값: outputs/info)
        model: 사용할 OpenAI 모델명 (기본값: gpt-4o-mini)
        dry_run: True일 경우 API 호출 없이 목업 데이터 사용

    Returns:
        Path: 생성된 Markdown 파일의 절대 경로

    Raises:
        ValueError: API 키가 없거나 키워드가 비어있을 경우
        Exception: API 호출 실패 또는 파일 저장 실패 시

    Example:
        >>> from pathlib import Path
        >>> output_path = run("청자 상감운학문 매병")
        >>> print(f"저장 완료: {output_path}")
    """
    # 입력 검증
    if not keyword or not keyword.strip():
        raise ValueError("키워드는 비어있을 수 없습니다.")

    keyword = keyword.strip()
    mode = "dry_run" if dry_run else "production"
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}정보 검색 파이프라인 시작: {keyword}")

    # 출력 디렉토리 설정: dry_run 모드일 경우 outputs/mock/info/ 사용
    if output_dir is None:
        output_dir = DEFAULT_MOCK_OUTPUT_DIR if dry_run else DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {output_dir.absolute()}")

    # 정보 검색
    if dry_run:
        logger.info("DRY RUN 모드: 목업 데이터 사용")
        content = _get_mock_data(keyword)
    else:
        content = _search_with_llm(keyword, model=model)

    # 파일 경로 생성 (공통 헬퍼 사용)
    output_path = info_markdown_path(keyword, output_dir)

    try:
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"파일 저장 완료: {output_path.absolute()}")
    except Exception as e:
        logger.error(f"파일 저장 실패: {e}")
        raise

    # 메타데이터 생성
    try:
        create_metadata(
            keyword=keyword,
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
        $ python -m src.pipelines.info_retrieval --keyword "청자 상감운학문 매병"
        $ python -m src.pipelines.info_retrieval --keyword "석굴암" --dry-run
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="문화유산 정보 검색 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m src.pipelines.info_retrieval --keyword "청자 상감운학문 매병"
  python -m src.pipelines.info_retrieval --keyword "석굴암" --dry-run
  python -m src.pipelines.info_retrieval --keyword "훈민정음" --model gpt-4o
        """
    )

    parser.add_argument(
        "--keyword",
        type=str,
        required=True,
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
        "--dry-run",
        action="store_true",
        help="API 호출 없이 목업 데이터로 테스트"
    )

    args = parser.parse_args()

    try:
        output_path = run(
            keyword=args.keyword,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            model=args.model,
            dry_run=args.dry_run
        )

        print(f"\n✅ 정보 검색 완료!")
        print(f"📄 파일 위치: {output_path}")
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
