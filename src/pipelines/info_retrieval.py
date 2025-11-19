"""
정보 검색 파이프라인 (Pipeline 1) - Perplexity 기반

입력된 문화유산 키워드를 기반으로 Perplexity API로 검색하고,
OpenAI LLM으로 정리하여 구조화된 Markdown 파일로 저장한다.

주요 기능:
- Perplexity API를 활용한 웹 검색
- OpenAI Responses API를 활용한 검색 쿼리 생성 및 마크다운 정리
- YAML 기반 프롬프트 템플릿 시스템 지원 (버전별 관리 가능)
- info_prompt와 search_keyword 분리로 명시적 검색 제어
- outputs/info/ 디렉토리에 파일 저장
- 에러 처리 및 dry_run 모드 지원
"""

import logging
import os
import json
from pathlib import Path
from typing import Optional, List, Dict

from dotenv import load_dotenv
from openai import OpenAI
import backoff

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


def _generate_search_queries(
    search_keyword: str,
    info_prompt: str,
    model: str,
    prompt_template,
    max_queries: Optional[int] = None
) -> List[str]:
    """
    OpenAI Responses API로 검색 쿼리 생성

    Args:
        search_keyword: 검색 키워드
        info_prompt: 검색 맥락
        model: OpenAI 모델명
        prompt_template: 프롬프트 템플릿 객체
        max_queries: 쿼리 개수 제한 (None=무제한)

    Returns:
        검색 쿼리 리스트
    """
    api_key = _validate_api_key()
    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.create(
            model=model,
            instructions=prompt_template.format_query_generation_instructions(max_queries),
            input=prompt_template.format_query_generation_input(search_keyword, info_prompt)
        )

        # JSON 파싱
        queries = json.loads(response.output_text)
        if not isinstance(queries, list):
            raise ValueError("응답이 배열 형식이 아닙니다")
        return queries

    except json.JSONDecodeError as e:
        logger.error(f"⚠️ JSON 파싱 실패: {e}")
        logger.error(f"응답 내용: {response.output_text}")
        # Fallback: 키워드 그대로 사용
        return [search_keyword]
    except Exception as e:
        logger.error(f"검색 쿼리 생성 실패: {e}")
        # Fallback
        return [search_keyword]


def _search_with_perplexity(
    queries: List[str],
    max_results: int = 10,
    country: str = "KR"
) -> List[Dict]:
    """
    Perplexity Search API로 검색 (RAG 기반, 할루시네이션 감소)

    Args:
        queries: 검색 쿼리 리스트
        max_results: 쿼리당 결과 개수
        country: 국가 코드

    Returns:
        검색 결과 리스트 (각 항목에 title, url, snippet, date 포함)
    """
    try:
        from perplexity import Perplexity
    except ImportError:
        logger.error("perplexity 패키지가 설치되지 않았습니다. pip install perplexityai")
        raise

    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError(
            "PERPLEXITY_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 API 키를 추가해주세요."
        )

    client = Perplexity(api_key=api_key)
    all_results = []

    # 각 쿼리를 개별적으로 검색 (Search API 사용)
    for idx, query in enumerate(queries, 1):
        logger.info(f"  쿼리 {idx}/{len(queries)}: {query[:50]}...")

        @backoff.on_exception(backoff.expo, Exception, max_tries=3)
        def search_with_retry():
            # Perplexity Search API 사용 (Chat 대신 Search)
            response = client.search.create(
                query=query,
                max_results=max_results,
                country=country,
                max_tokens_per_page=1024
            )
            return response

        try:
            search_response = search_with_retry()

            # Search API 응답에서 결과 추출
            # 응답 형태: list of {title, url, snippet, date, last_updated}
            if hasattr(search_response, 'results') and search_response.results:
                results = search_response.results
            elif isinstance(search_response, list):
                results = search_response
            else:
                # 응답 형태가 예상과 다른 경우 로깅
                logger.warning(f"예상치 못한 응답 형태: {type(search_response)}")
                results = []

            all_results.append({
                "query": query,
                "results": results,  # 원본 검색 결과 (title, url, snippet 포함)
                "result_count": len(results),
                "index": idx
            })

        except Exception as e:
            logger.warning(f"⚠️ Perplexity API 오류 (쿼리 {idx}): {e}")
            # 에러 발생해도 빈 결과로 계속 진행
            all_results.append({
                "query": query,
                "results": [],
                "result_count": 0,
                "index": idx,
                "error": str(e)
            })
            continue

    return all_results


def _format_results_to_markdown(
    search_results: List[Dict],
    search_keyword: str,
    info_prompt: str,
    model: str,
    prompt_template
) -> str:
    """
    OpenAI Responses API로 마크다운 정리

    Args:
        search_results: Perplexity 검색 결과
        search_keyword: 검색 키워드
        info_prompt: 검색 맥락
        model: OpenAI 모델명
        prompt_template: 프롬프트 템플릿 객체

    Returns:
        마크다운 텍스트
    """
    api_key = _validate_api_key()
    client = OpenAI(api_key=api_key)

    # 검색 결과를 텍스트로 포맷팅 (Perplexity Search API 응답 구조)
    formatted_results = []
    all_urls = []  # 모든 URL 수집

    for query_result in search_results:
        query = query_result.get('query', '')
        results = query_result.get('results', [])
        idx = query_result.get('index', 'N/A')

        query_section = f"[쿼리 {idx}] {query}\n\n"

        if results:
            query_section += "검색 결과:\n"
            for i, item in enumerate(results, 1):
                # Pydantic 모델이므로 직접 속성 접근
                title = getattr(item, 'title', 'N/A')
                url = getattr(item, 'url', '')
                snippet = getattr(item, 'snippet', 'N/A')
                date = getattr(item, 'date', '')

                query_section += f"\n{i}. {title}\n"
                if url:
                    query_section += f"   URL: {url}\n"
                    all_urls.append(url)  # URL 수집
                query_section += f"   내용: {snippet}\n"
                if date:
                    query_section += f"   날짜: {date}\n"
        else:
            query_section += "검색 결과 없음\n"

        formatted_results.append(query_section)

    results_text = "\n\n---\n\n".join(formatted_results)

    # 실제 검색된 URL 목록 추가
    if all_urls:
        results_text += "\n\n=== 실제 참조된 URL 목록 ===\n"
        results_text += "\n".join(f"- {url}" for url in set(all_urls))

    try:
        response = client.responses.create(
            model=model,
            instructions=prompt_template.get_markdown_formatting_instructions(),
            input=prompt_template.format_markdown_formatting_input(
                search_keyword=search_keyword,
                info_prompt=info_prompt,
                search_results=results_text
            )
        )

        return response.output_text

    except Exception as e:
        logger.error(f"마크다운 생성 실패: {e}")
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
    info_prompt: str = "한국 문화유산에 대한 상세한 정보를 수집해주세요.",
    max_queries: Optional[int] = None,
    dry_run: bool = False,
    output_name: Optional[str] = None
) -> Path:
    """
    정보 검색 파이프라인 실행 (Perplexity 기반)

    주어진 키워드에 대한 문화유산 정보를 Perplexity로 검색하고,
    구조화된 Markdown 파일로 저장한다.

    Args:
        search_keyword: 검색할 문화유산 키워드 (명시적 검색용)
        output_dir: 출력 디렉토리 (기본값: outputs/info)
        model: 사용할 OpenAI 모델명 (기본값: gpt-4.1)
        prompt_version: 프롬프트 템플릿 버전 (기본값: "default")
        info_prompt: 검색 맥락 및 지시사항
        max_queries: 검색 쿼리 최대 개수 (None=제한없음)
        dry_run: True일 경우 API 호출 없이 목업 데이터 사용
        output_name: 파일명으로 사용할 이름 (선택적, 미제공 시 search_keyword 사용)

    Returns:
        Path: 생성된 Markdown 파일의 절대 경로

    Raises:
        ValueError: API 키가 없거나 키워드가 비어있을 경우
        Exception: API 호출 실패 또는 파일 저장 실패 시

    Example:
        >>> output_path = run("청자 상감운학문 매병", info_prompt="도자기 기법 중심")
        >>> output_path = run("석굴암", max_queries=5)
    """
    # 입력 검증
    if not search_keyword or not search_keyword.strip():
        raise ValueError("키워드는 비어있을 수 없습니다.")

    search_keyword = search_keyword.strip()
    mode = "dry_run" if dry_run else "production"
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}정보 검색 파이프라인 시작: {search_keyword}")
    logger.info(f"프롬프트 버전: {prompt_version}")
    logger.info(f"검색 맥락: {info_prompt[:50]}...")
    if max_queries:
        logger.info(f"쿼리 개수 제한: {max_queries}개")

    # 출력 디렉토리 설정
    if output_dir is None:
        output_dir = DEFAULT_MOCK_OUTPUT_DIR if dry_run else DEFAULT_OUTPUT_DIR

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Dry-run 모드
    if dry_run:
        logger.info("DRY RUN 모드: 목업 데이터 사용")
        content = _get_mock_data(search_keyword)
    else:
        # 프롬프트 템플릿 로드
        try:
            prompt_template = load_prompt(
                version=prompt_version,
                pipeline_type="info_retrieval"
            )
            logger.info(f"프롬프트 템플릿 로드 완료: {prompt_template.name}")
        except FileNotFoundError as e:
            logger.error(f"프롬프트 템플릿 로드 실패: {e}")
            available = list_prompts(pipeline_type="info_retrieval")
            logger.info(f"사용 가능한 버전: {', '.join(available)}")
            raise

        # Stage 1: 검색 쿼리 생성
        print(f"[1/3] 검색 쿼리 생성 중...")
        queries = _generate_search_queries(
            search_keyword=search_keyword,
            info_prompt=info_prompt,
            model=model,
            prompt_template=prompt_template,
            max_queries=max_queries
        )
        print(f"✓ 생성된 쿼리 {len(queries)}개: {queries[:3]}{'...' if len(queries) > 3 else ''}")

        # Stage 2: Perplexity 검색
        print(f"[2/3] Perplexity 검색 실행 중...")
        search_results = _search_with_perplexity(queries)
        print(f"✓ 검색 결과 {len(search_results)}개 수집 완료")

        # Stage 3: 마크다운 정리
        print(f"[3/3] 마크다운 문서 생성 중...")
        content = _format_results_to_markdown(
            search_results=search_results,
            search_keyword=search_keyword,
            info_prompt=info_prompt,
            model=model,
            prompt_template=prompt_template
        )

    # 파일 저장
    output_path = info_markdown_path(search_keyword, output_dir, output_name)

    try:
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"파일 저장 완료: {output_path.absolute()}")
    except Exception as e:
        logger.error(f"파일 저장 실패: {e}")
        raise

    # 메타데이터 생성
    try:
        # Dry-run이 아닐 경우 검색 쿼리 정보도 포함
        extra_metadata = {}
        if not dry_run and 'queries' in locals():
            extra_metadata["search_queries"] = queries
            extra_metadata["total_queries"] = len(queries)
            extra_metadata["max_queries_limit"] = max_queries
            extra_metadata["info_prompt"] = info_prompt

        create_metadata(
            search_keyword=search_keyword,
            pipeline="info_retrieval",
            output_file_path=output_path,
            mode=mode,
            model=model if not dry_run else None,
            **extra_metadata
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
        $ python -m src.pipelines.info_retrieval --search-keyword "석굴암" --info-prompt "불교 예술" --max-queries 5
        $ python -m src.pipelines.info_retrieval --list-prompts
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="문화유산 정보 검색 파이프라인 (Perplexity API 기반)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 사용
  python -m src.pipelines.info_retrieval --search-keyword "청자 상감운학문 매병"

  # 검색 맥락 및 쿼리 개수 제한
  python -m src.pipelines.info_retrieval --search-keyword "석굴암" \\
    --info-prompt "불교 조각 예술의 특징" --max-queries 5

  # Dry-run 모드
  python -m src.pipelines.info_retrieval --search-keyword "훈민정음" --dry-run

  # 사용 가능한 프롬프트 버전 확인
  python -m src.pipelines.info_retrieval --list-prompts
        """
    )

    parser.add_argument(
        "--search-keyword",
        type=str,
        help="검색할 문화유산 키워드 (명시적 검색용)"
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
        "--info-prompt",
        type=str,
        default="한국 문화유산에 대한 상세한 정보를 수집해주세요.",
        help="검색 맥락 및 지시사항"
    )

    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="생성할 검색 쿼리의 최대 개수 (기본값: 제한 없음)"
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
            info_prompt=args.info_prompt,
            max_queries=args.max_queries,
            dry_run=args.dry_run,
            output_name=args.output_name
        )

        print(f"\n✅ 정보 검색 완료!")
        print(f"📄 파일 위치: {output_path}")
        print(f"프롬프트 버전: {args.prompt_version}")
        if args.max_queries:
            print(f"쿼리 개수 제한: {args.max_queries}개")
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
