"""
스크립트 생성 파이프라인 (Pipeline 2)

정보 검색 파이프라인이 생성한 Markdown 파일을 읽어 1분 내외의 오디오 가이드
스크립트를 작성하고 outputs/script/에 저장한다.

주요 기능:
- /outputs/info/[output_name].md 파일 읽기
- 버전별 프롬프트 템플릿 지원 (prompts/script_generation/)
- OpenAI GPT를 사용한 오디오 가이드 스크립트 생성
- /outputs/script/[output_name]_script.md에 구조화된 결과 저장
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from src.utils.yaml_utils import load_yaml, list_yaml_files, format_template, get_value
from src.utils.path_sanitizer import script_markdown_path
from src.utils.metadata import create_metadata

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 기본 설정
DEFAULT_OUTPUT_DIR = Path("outputs/script")


def run(
    output_name: str,
    script_gen_prompt_template_name: str,
    script_gen_model: str,
    info_retrieval_result_file_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    script_gen_user_content_text: Optional[str] = None,
    temperature: float = 0.7,
) -> Path:
    """
    스크립트 생성 파이프라인 실행

    Args:
        output_name: 파일명 (식별자로 사용됨)
        script_gen_prompt_template_name: 스크립트 프롬프트 템플릿 버전
        script_gen_model: 사용할 모델명 (OpenAI 'gpt-*' 또는 Google 'gemini-*')
        info_retrieval_result_file_path: 정보 검색 결과 파일 경로 (필수)
        output_dir: 스크립트를 저장할 디렉토리 (기본: outputs/script)
        script_gen_user_content_text: 사용자 커스텀 프롬프트 (선택적, 기본 프롬프트에 추가됨)
        temperature: LLM temperature 파라미터 (0.0~1.0)

    Returns:
        생성된 스크립트 파일의 경로 (Path 객체)

    Raises:
        FileNotFoundError: 정보 파일 또는 프롬프트 템플릿을 찾을 수 없을 때
        ValueError: API 키가 설정되지 않았을 때
        Exception: API 호출 실패 등 기타 오류
    """
    # 환경변수 로드
    load_dotenv()

    # 기본 경로 설정
    if info_retrieval_result_file_path is None:
        raise ValueError("info_retrieval_result_file_path는 필수입니다.")
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)

    info_file = info_retrieval_result_file_path

    script_gen_result_file_path = script_markdown_path(output_name, output_dir)

    logger.info(f"스크립트 생성 파이프라인 시작: {output_name}")
    logger.info(f"스크립트 프롬프트 버전: {script_gen_prompt_template_name}")
    if script_gen_user_content_text:
        logger.info(f"커스텀 프롬프트 추가: 예")
    logger.info(f"입력 파일: {info_file}")
    logger.info(f"출력 파일: {script_gen_result_file_path}")

    # 프롬프트 템플릿 로드
    try:
        prompt_dir = Path("prompts/script_generation")
        prompt_path = (
            prompt_dir / script_gen_prompt_template_name
            if script_gen_prompt_template_name.endswith(".yaml")
            else prompt_dir / f"{script_gen_prompt_template_name}.yaml"
        )
        prompt_config = load_yaml(prompt_path)
        prompt_config["path"] = prompt_path
        prompt_config.setdefault("parameters", {})
        logger.info(
            "프롬프트 템플릿 로드 완료: %s",
            prompt_config.get("name", script_gen_prompt_template_name),
        )
        if prompt_config.get("description"):
            logger.info("프롬프트 설명: %s", prompt_config["description"])
        tags = prompt_config.get("tags") or []
        if tags:
            logger.info("프롬프트 태그: %s", ", ".join(tags))
    except FileNotFoundError as e:
        logger.error(f"프롬프트 템플릿 로드 실패: {e}")
        available = list_prompts()
        logger.info(f"사용 가능한 버전: {', '.join(available)}")
        raise

    # 정보 파일 존재 확인
    if not info_file.exists():
        error_msg = f"정보 파일을 찾을 수 없습니다: {info_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # 정보 파일 읽기
    logger.info("정보 파일 읽기 중...")
    with open(info_file, "r", encoding="utf-8") as f:
        info_retrieval_result_content_text = f.read()

    logger.info(
        f"정보 파일 로드 완료 (길이: {len(info_retrieval_result_content_text)} 문자)"
    )

    # API 키 확인 및 LLM 호출
    try:
        logger.info(
            f"LLM 호출 시작 (모델: {script_gen_model}, temperature: {temperature})"
        )

        if script_gen_model.startswith("gpt"):
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                error_msg = (
                    "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            # 프롬프트 생성
            safe_custom_prompt = (
                script_gen_user_content_text if script_gen_user_content_text else "없음"
            )
            system_prompt = get_value(prompt_config, "system_prompt", "")
            user_prompt_template = get_value(prompt_config, "user_prompt_template", "")
            if not system_prompt or not user_prompt_template:
                raise ValueError(
                    f"system_prompt 또는 user_prompt_template이 YAML에 없습니다: {prompt_config.get('path')}"
                )
            user_prompt = format_template(
                user_prompt_template,
                parameters=prompt_config.get("parameters"),
                info_retrieval_result_content_text=info_retrieval_result_content_text,
                script_gen_user_content_text=safe_custom_prompt,
            )

            response = client.chat.completions.create(
                model=script_gen_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            script_gen_result_content = response.choices[0].message.content

        elif script_gen_model.startswith("gemini"):
            # Gemini API 사용 (google-genai)
            api_key = os.getenv(
                "GEMINI_API_KEY"
            )  # Assuming GEMINI_API_KEY is used for google.genai
            if not api_key:
                # google-genai might pick up GOOGLE_API_KEY automatically, but explicit check is good.
                # Usually GOOGLE_API_KEY is standard for AI Studio.
                api_key = os.getenv("GOOGLE_API_KEY")

            if not api_key:
                error_msg = "GEMINI_API_KEY 또는 GOOGLE_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."
                logger.error(error_msg)
                raise ValueError(error_msg)

            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)

            # 프롬프트 생성
            safe_custom_prompt = (
                script_gen_user_content_text if script_gen_user_content_text else "없음"
            )
            system_prompt = get_value(prompt_config, "system_prompt", "")
            user_prompt_template = get_value(prompt_config, "user_prompt_template", "")
            if not system_prompt or not user_prompt_template:
                raise ValueError(
                    f"system_prompt 또는 user_prompt_template이 YAML에 없습니다: {prompt_config.get('path')}"
                )
            user_prompt = format_template(
                user_prompt_template,
                parameters=prompt_config.get("parameters"),
                info_retrieval_result_content_text=info_retrieval_result_content_text,
                script_gen_user_content_text=safe_custom_prompt,
            )

            response = client.models.generate_content(
                model=script_gen_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=temperature,
                ),
            )
            script_gen_result_content = response.text

        else:
            raise ValueError(
                f"지원하지 않는 모델명입니다: {script_gen_model}. 'gpt-' 또는 'gemini-'로 시작해야 합니다."
            )

        logger.info(f"LLM 응답 수신 완료 (길이: {len(script_gen_result_content)} 문자)")

    except Exception as e:
        error_msg = f"LLM 호출 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e

    # 스크립트 저장
    try:
        with open(script_gen_result_file_path, "w", encoding="utf-8") as f:
            f.write(script_gen_result_content)
        logger.info(f"✅ 스크립트 파일 저장 완료: {script_gen_result_file_path}")

    except Exception as e:
        error_msg = f"스크립트 파일 저장 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e

    # 메타데이터 생성
    try:
        create_metadata(
            output_name=output_name,
            pipeline="script_gen",
            output_file_path=script_gen_result_file_path,
            mode="production",
            model=script_gen_model,
            script_gen_user_content_text=script_gen_user_content_text,
        )
    except Exception as e:
        logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")

    return script_gen_result_file_path


def main():
    """CLI 진입점"""
    import argparse

    parser = argparse.ArgumentParser(
        description="오디오 가이드 스크립트 생성 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 사용 (v1 프롬프트)
  python src/pipelines/script_gen.py --output-name "01_celadon"

  # v2 프롬프트로 실제 생성
  python src/pipelines/script_gen.py --output-name "01_celadon" --prompt-template-name v2-tts

  # 커스텀 프롬프트 추가
  python src/pipelines/script_gen.py --output-name "01_celadon" --user-content-text "전문적인 톤 사용"

  # 사용 가능한 프롬프트 버전 확인
  python src/pipelines/script_gen.py --list-prompts
        """,
    )
    parser.add_argument(
        "--output-name",
        type=str,
        required=True,
        help="식별자 (파일명)",
    )
    parser.add_argument(
        "--info-result-file",
        type=Path,
        required=True,
        help="정보 검색 결과 파일 경로 (필수)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="출력 디렉토리 (기본: outputs/script)",
    )
    parser.add_argument(
        "--prompt-template-name",
        type=str,
        default="v1",
        help="스크립트 프롬프트 템플릿 버전 (기본: v1)",
    )
    parser.add_argument(
        "--user-content-text",
        type=str,
        default=None,
        help="사용자 커스텀 프롬프트 (기본 프롬프트에 추가됨)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (0.0~1.0, 기본: 0.7)",
    )
    parser.add_argument(
        "--script-gen-model",
        type=str,
        default="gpt-4o",
        help="사용할 모델명 (기본: gpt-4o, 예: gpt-4.1, gemini-3-pro-preview)",
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="사용 가능한 프롬프트 버전 목록 출력",
    )

    args = parser.parse_args()

    # 프롬프트 목록 출력 모드
    if args.list_prompts:
        print("\n사용 가능한 프롬프트 버전:")
        print("=" * 70)
        prompt_dir = Path("prompts/script_generation")
        for version in list_yaml_files(prompt_dir):
            try:
                template = load_yaml(
                    prompt_dir / (version if version.endswith(".yaml") else f"{version}.yaml")
                )
                print(f"\n📝 {version}:")
                print(f"    이름: {template.get('name', '')}")
                print(f"    설명: {template.get('description', '')}")
                tags = template.get("tags") or []
                if tags:
                    print(f"    태그: {', '.join(tags)}")
                params = template.get("parameters") or {}
                if params:
                    print(f"    파라미터: {params}")
            except Exception as e:
                print(f"\n❌ {version}: (로드 실패 - {e})")
        print("\n" + "=" * 70)
        print("\n💡 사용 예시:")
        print(
            '  python src/pipelines/script_gen.py --output-name "01_celadon" --prompt-template-name v1'
        )
        print(
            '  python src/pipelines/script_gen.py --output-name "02_seokguram" --prompt-template-name v2-tts'
        )
        print("=" * 70)
        return

    try:
        output_path = run(
            output_name=args.output_name,
            info_retrieval_result_file_path=args.info_result_file,
            output_dir=args.output_dir,
            script_gen_prompt_template_name=args.prompt_template_name,
            script_gen_user_content_text=args.user_content_text,
            temperature=args.temperature,
            script_gen_model=args.script_gen_model,
        )

        print("\n" + "=" * 60)
        print("✅ 스크립트 생성 완료!")
        print("=" * 60)
        print(f"Output Name: {args.output_name}")
        print(f"스크립트 프롬프트 버전: {args.prompt_template_name}")
        if args.user_content_text:
            print(f"커스텀 프롬프트: 추가됨")
        print(f"출력 파일: {output_path}")
        print("=" * 60)

        # 생성된 스크립트 미리보기 (처음 200자)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            preview = content[:200]

        print("\n📄 스크립트 미리보기:")
        print("-" * 60)
        print(preview + "..." if len(content) > 200 else preview)
        print("-" * 60)

    except FileNotFoundError as e:
        logger.error(f"❌ 파일을 찾을 수 없습니다: {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(f"❌ 설정 오류: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
