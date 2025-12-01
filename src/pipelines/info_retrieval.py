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
from typing import Optional, Dict, Tuple, Any

from dotenv import load_dotenv
import backoff

from src.utils.path_sanitizer import info_markdown_path
from src.utils.metadata import create_metadata
from src.utils.yaml_utils import load_yaml, list_yaml_files, format_template, get_value

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
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


@backoff.on_exception(backoff.expo, Exception, max_tries=3, max_time=30)
def _chat_with_perplexity(
    info_retrieval_user_content_text: str,
    prompt_config: Dict[str, Any],
    perplexity_model: str,
) -> Tuple[str, Dict]:
    """
    Perplexity Chat API로 검색 + 마크다운 생성 (단일 호출)

    Args:
        info_retrieval_user_content_text: 추가 맥락 및 요구사항 (텍스트)
        prompt_template: 프롬프트 템플릿 객체
        perplexity_model: Perplexity 모델 (sonar, sonar-pro)

    Returns:
        (markdown_content, metadata_dict)
    """
    # Perplexity API 호출
    api_key = _validate_api_key()

    from perplexity import Perplexity

    client = Perplexity(api_key=api_key)

    logger.info(
        f"[Perplexity Chat] 검색 시작: {info_retrieval_user_content_text[:50]}..."
    )

    try:
        # Chat Completions API 호출 (마크다운 직접 생성)
        system_prompt = get_value(prompt_config, "system_prompt", "")
        user_prompt_template = get_value(prompt_config, "user_prompt_template", "")
        if not system_prompt or not user_prompt_template:
            raise ValueError(
                f"system_prompt 또는 user_prompt_template이 YAML에 없습니다: {prompt_config.get('path')}"
            )

        user_content = format_template(
            user_prompt_template,
            parameters=prompt_config.get("parameters"),
            info_retrieval_user_content_text=info_retrieval_user_content_text,
        )

        response = client.chat.completions.create(
            model=perplexity_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            temperature=0.3,
            search_domain_filter=["-tistory.com", "-phoenix1024.com"],
            web_search_options={
                "search_context_size": "high",
            },
        )

        # 마크다운 응답 직접 사용
        markdown = response.choices[0].message.content

        logger.info(f"[Perplexity Chat] 마크다운 생성 완료 ({len(markdown)} chars)")

        # 메타데이터 준비
        metadata = {"finish_reason": response.choices[0].finish_reason}

        # search_results 정보 추가 (있을 경우)
        if hasattr(response, "search_results") and response.search_results:
            metadata["search_results"] = [
                sr.model_dump() for sr in response.search_results
            ]

        # Usage 정보 추가 (있을 경우)
        if hasattr(response, "usage") and response.usage:
            metadata["usage"] = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", None),
                "completion_tokens": getattr(response.usage, "completion_tokens", None),
                "total_tokens": getattr(response.usage, "total_tokens", None),
            }

        return markdown, metadata

    except Exception as e:
        logger.error(f"Perplexity API 호출 실패: {e}")
        raise


def save_metadata(
    output_path: Path,
    pipeline: str,
    output_name: str,
    perplexity_model: str,
    info_retrieval_user_content_text: str,
    **extra_metadata,
) -> None:
    """
    메타데이터를 JSON 파일로 저장

    Args:
        output_path: 출력 파일 경로
        pipeline: 파이프라인 이름
        output_name: 파일명 (식별자)
        perplexity_model: 사용한 모델
        info_retrieval_user_content_text: 입력 프롬프트
        **extra_metadata: 추가 메타데이터
    """
    metadata_path = create_metadata(
        output_name=output_name,
        pipeline=pipeline,
        output_file_path=output_path,
        mode="production",
        model=perplexity_model,
        info_retrieval_user_content_text=info_retrieval_user_content_text,
        **extra_metadata,
    )

    logger.info(f"메타데이터 저장 완료: {metadata_path}")


def run(
    output_name: str,
    perplexity_model: str,
    info_retrieval_prompt_template_name: str,
    info_retrieval_user_content_text: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Perplexity Chat API로 정보 검색 + 마크다운 생성 (단일 호출)

    Args:
        output_name: 파일명 (식별자로 사용됨)
        perplexity_model: Perplexity 모델 (sonar, sonar-pro)
        info_retrieval_prompt_template_name: 프롬프트 버전 (default, ...)
        info_retrieval_user_content_text: 추가 맥락 및 요구사항 (텍스트)
        output_dir: 출력 디렉토리 (기본: outputs/info/)

    Returns:
        Path: 생성된 마크다운 파일 경로

    Examples:
        # 기본 사용
        run(
            output_name="01_shilla_crown",
            perplexity_model="sonar-pro",
            info_retrieval_prompt_template_name="default",
            info_retrieval_user_content_text="신라 금관에 대해 조사해주세요."
        )
    """
    logger.info(f"=== 정보 검색 파이프라인 시작 ===")
    logger.info(f"Output Name: {output_name}")
    logger.info(f"모델: {perplexity_model}")
    logger.info(f"프롬프트 버전: {info_retrieval_prompt_template_name}")

    # 1. 프롬프트 템플릿 로드
    prompt_dir = Path("prompts/info_retrieval")
    prompt_path = (
        prompt_dir / info_retrieval_prompt_template_name
        if info_retrieval_prompt_template_name.endswith(".yaml")
        else prompt_dir / f"{info_retrieval_prompt_template_name}.yaml"
    )

    prompt_config = load_yaml(prompt_path)
    prompt_config["path"] = prompt_path
    prompt_config.setdefault("parameters", {})
    logger.info(
        "프롬프트 로드 완료: %s",
        prompt_config.get("name", info_retrieval_prompt_template_name),
    )

    # 2. Perplexity Chat API 호출 (검색 + 마크다운 생성)
    content, api_metadata = _chat_with_perplexity(
        info_retrieval_user_content_text=info_retrieval_user_content_text,
        prompt_config=prompt_config,
        perplexity_model=perplexity_model,
    )

    logger.info(f"마크다운 생성 완료 ({len(content)} chars)")

    # 3. 파일 저장
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    # output_name을 사용하여 파일 경로 생성
    output_path = info_markdown_path(output_name, output_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    logger.info(f"파일 저장 완료: {output_path}")

    # 4. 메타데이터 저장
    save_metadata(
        output_path,
        pipeline="info_retrieval",
        output_name=output_name,
        perplexity_model=perplexity_model,
        info_retrieval_user_content_text=info_retrieval_user_content_text,
        **api_metadata,
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
        "--output-name", type=str, required=True, help="식별자 (파일명)"
    )
    parser.add_argument(
        "--perplexity-model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Perplexity 모델 (기본: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--prompt-template-name",
        type=str,
        default="default",
        help="프롬프트 버전 (기본: default)",
    )
    parser.add_argument(
        "--user-content-text",
        type=str,
        default="한국 문화유산에 대한 상세한 정보를 수집해주세요.",
        help="추가 맥락 및 요구사항",
    )
    parser.add_argument(
        "--output-dir", type=Path, help="출력 디렉토리 (기본: outputs/info/)"
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="사용 가능한 프롬프트 버전 목록 출력",
    )

    args = parser.parse_args()

    # 프롬프트 목록 출력
    if args.list_prompts:
        prompt_dir = Path("prompts/info_retrieval")
        versions = list_yaml_files(prompt_dir)
        print(f"\n사용 가능한 프롬프트 버전:")
        for v in versions:
            print(f"  - {v}")
        return

    # 파이프라인 실행
    try:
        output_path = run(
            output_name=args.output_name,
            perplexity_model=args.perplexity_model,
            info_retrieval_prompt_template_name=args.prompt_template_name,
            info_retrieval_user_content_text=args.user_content_text,
            output_dir=args.output_dir,
        )
        print(f"\n✅ 완료: {output_path}")

    except Exception as e:
        logger.error(f"파이프라인 실패: {e}")
        raise


if __name__ == "__main__":
    main()
