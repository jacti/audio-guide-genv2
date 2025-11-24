"""
정보 검색 파이프라인 (Pipeline 1) - Perplexity Chat API 단일 호출

입력된 문화유산 키워드를 기반으로 Perplexity Chat API로 검색 + 정리를
단일 호출로 처리하여 구조화된 Markdown 파일로 저장한다.

주요 기능:
- Perplexity Chat Completions API 단일 호출 (웹 검색 자동 통합)
- Structured Output (JSON Schema)으로 구조화된 출력 보장
- YAML 기반 프롬프트 템플릿 시스템 지원
- outputs/info/ 디렉토리에 파일 저장
- 에러 처리 및 dry_run 모드 지원
"""

import logging
import os
import json
from pathlib import Path
from typing import Optional, Dict, Tuple

from dotenv import load_dotenv
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
DEFAULT_MODEL = "sonar-pro"  # Perplexity 모델


def _validate_api_key() -> str:
    """
    Perplexity API 키 유효성 검증

    Returns:
        str: 유효한 API 키

    Raises:
        ValueError: API 키가 없거나 비어있을 경우
    """
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError(
            "PERPLEXITY_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 API 키를 추가해주세요."
        )
    return api_key


@backoff.on_exception(
    backoff.expo,
    Exception,
    max_tries=3,
    max_time=30
)
def _chat_with_perplexity(
    search_keyword: str,
    info_prompt: str,
    prompt_template,
    model: str,
) -> Tuple[str, Dict]:
    """
    Perplexity Chat API로 검색 + 마크다운 생성 (단일 호출)

    Args:
        search_keyword: 검색 키워드
        info_prompt: 추가 맥락 및 요구사항
        prompt_template: 프롬프트 템플릿 객체
        model: Perplexity 모델 (sonar, sonar-pro)

    Returns:
        (markdown_content, metadata_dict)
    """
    # Perplexity API 호출
    api_key = _validate_api_key()

    from perplexity import Perplexity

    client = Perplexity(api_key=api_key)

    logger.info(f"[Perplexity Chat] 검색 시작: {search_keyword}")

    try:
        # Chat Completions API 호출 (마크다운 직접 생성)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": prompt_template.get_system_prompt()
                },
                {
                    "role": "user",
                    "content": prompt_template.format_user_prompt(
                        search_keyword=search_keyword,
                        info_prompt=info_prompt
                    )
                }
            ],
            temperature=0.3
        )

        # 마크다운 응답 직접 사용
        markdown = response.choices[0].message.content

        logger.info(f"[Perplexity Chat] 마크다운 생성 완료 ({len(markdown)} chars)")

        # 메타데이터 준비
        metadata = {
            "finish_reason": response.choices[0].finish_reason
        }

        # Usage 정보 추가 (있을 경우)
        if hasattr(response, 'usage') and response.usage:
            metadata["usage"] = {
                "prompt_tokens": getattr(response.usage, 'prompt_tokens', None),
                "completion_tokens": getattr(response.usage, 'completion_tokens', None),
                "total_tokens": getattr(response.usage, 'total_tokens', None)
            }

        return markdown, metadata

    except Exception as e:
        logger.error(f"Perplexity API 호출 실패: {e}")
        raise


def save_metadata(
    output_path: Path,
    pipeline: str,
    search_keyword: str,
    model: str,
    info_prompt: str,
    **extra_metadata
) -> None:
    """
    메타데이터를 JSON 파일로 저장

    Args:
        output_path: 출력 파일 경로
        pipeline: 파이프라인 이름
        search_keyword: 검색 키워드
        model: 사용한 모델
        info_prompt: 입력 프롬프트
        **extra_metadata: 추가 메타데이터
    """
    metadata_path = create_metadata(
        search_keyword=search_keyword,
        pipeline=pipeline,
        output_file_path=output_path,
        mode="production",
        model=model,
        info_prompt=info_prompt,
        **extra_metadata
    )

    logger.info(f"메타데이터 저장 완료: {metadata_path}")


def run(
    search_keyword: str,
    model: str,
    prompt_version: str,
    info_prompt: str,
    output_dir: Optional[Path] = None,
    output_name: Optional[str] = None
) -> Path:
    """
    Perplexity Chat API로 정보 검색 + 마크다운 생성 (단일 호출)

    Args:
        search_keyword: 검색할 문화유산 키워드
        model: Perplexity 모델 (sonar, sonar-pro)
        prompt_version: 프롬프트 버전 (default, ...)
        info_prompt: 추가 맥락 및 요구사항
        output_dir: 출력 디렉토리 (기본: outputs/info/)
        output_name: 커스텀 파일명 (기본: search_keyword 사용)

    Returns:
        Path: 생성된 마크다운 파일 경로

    Examples:
        # 기본 사용
        run(
            search_keyword="신라 금관",
            model="sonar-pro",
            prompt_version="default",
            info_prompt="한국 문화유산에 대한 상세한 정보를 수집해주세요."
        )
    """
    logger.info(f"=== 정보 검색 파이프라인 시작 ===")
    logger.info(f"검색 키워드: {search_keyword}")
    logger.info(f"모델: {model}")
    logger.info(f"프롬프트 버전: {prompt_version}")

    # 1. 프롬프트 템플릿 로드
    try:
        template = load_prompt(prompt_version, pipeline_type="info_retrieval")
        logger.info(f"프롬프트 로드 완료: {template.name} (v{template.version})")
    except FileNotFoundError as e:
        logger.error(f"프롬프트 로드 실패: {e}")
        raise

    # 2. Perplexity Chat API 호출 (검색 + 마크다운 생성)
    content, api_metadata = _chat_with_perplexity(
        search_keyword=search_keyword,
        info_prompt=info_prompt,
        prompt_template=template,
        model=model,
    )

    logger.info(f"마크다운 생성 완료 ({len(content)} chars)")

    # 3. 파일 저장
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    output_path = info_markdown_path(
        search_keyword, output_dir, output_name
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    logger.info(f"파일 저장 완료: {output_path}")

    # 4. 메타데이터 저장
    save_metadata(
        output_path,
        pipeline="info_retrieval",
        search_keyword=search_keyword,
        model=model,
        info_prompt=info_prompt,
        **api_metadata
    )

    logger.info(f"=== 정보 검색 파이프라인 완료 ===\n")

    return output_path


def main():
    """CLI 진입점"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Perplexity Chat API 기반 정보 검색 파이프라인"
    )
    parser.add_argument(
        "--search-keyword",
        type=str,
        required=True,
        help="검색할 문화유산 키워드"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Perplexity 모델 (기본: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--prompt-version",
        type=str,
        default="default",
        help="프롬프트 버전 (기본: default)"
    )
    parser.add_argument(
        "--info-prompt",
        type=str,
        default="한국 문화유산에 대한 상세한 정보를 수집해주세요.",
        help="추가 맥락 및 요구사항"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="출력 디렉토리 (기본: outputs/info/)"
    )
    parser.add_argument(
        "--output-name",
        type=str,
        help="커스텀 파일명"
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="사용 가능한 프롬프트 버전 목록 출력"
    )

    args = parser.parse_args()

    # 프롬프트 목록 출력
    if args.list_prompts:
        versions = list_prompts(pipeline_type="info_retrieval")
        print(f"\n사용 가능한 프롬프트 버전:")
        for v in versions:
            print(f"  - {v}")
        return

    # 파이프라인 실행
    try:
        output_path = run(
            search_keyword=args.search_keyword,
            model=args.model,
            prompt_version=args.prompt_version,
            info_prompt=args.info_prompt,
            output_dir=args.output_dir,
            output_name=args.output_name
        )
        print(f"\n✅ 완료: {output_path}")

    except Exception as e:
        logger.error(f"파이프라인 실패: {e}")
        raise


if __name__ == "__main__":
    main()
