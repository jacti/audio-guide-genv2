"""
스크립트 생성 파이프라인 (Pipeline 2)

정보 검색 파이프라인이 생성한 Markdown 파일을 읽어 1분 내외의 오디오 가이드
스크립트를 작성하고 outputs/script/에 저장한다.

주요 기능:
- /outputs/info/[keyword].md 파일 읽기
- 버전별 프롬프트 템플릿 지원 (prompts/script_generation/)
- OpenAI GPT를 사용한 오디오 가이드 스크립트 생성
- /outputs/script/[keyword]_script.md에 구조화된 결과 저장
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 프로젝트 루트를 sys.path에 추가 (utils 모듈 임포트를 위해)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.prompt_loader import load_prompt, list_prompts
from src.utils.path_sanitizer import info_markdown_path, script_markdown_path
from src.utils.metadata import create_metadata

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 기본 설정
DEFAULT_OUTPUT_DIR = Path("outputs/script")
DEFAULT_MOCK_OUTPUT_DIR = Path("outputs/mock/script")


def _generate_dry_run_script(search_keyword: str, script_prompt_version: str) -> str:
    """
    dry_run 모드에서 사용할 고정 템플릿 스크립트 생성

    Args:
        search_keyword: 유물/장소 검색 키워드
        script_prompt_version: 스크립트 프롬프트 버전

    Returns:
        테스트용 스크립트 문자열
    """
    script = f"""# {search_keyword} 오디오 가이드

## 인사 및 소개

안녕하세요! 오늘은 {search_keyword}에 대해 함께 알아보겠습니다.

## 본문

### 역사적 배경

(따뜻하게) 이 유물은 우리나라의 찬란한 문화유산 중 하나입니다.
오랜 세월 동안 많은 이야기를 품고 있습니다.

### 시각적 특징

(천천히) 눈으로 직접 보면, 그 아름다움과 정교함에 감탄하게 됩니다.
세밀한 문양과 색감이 조화를 이루고 있습니다.

### 문화적 의미

이 유물은 단순한 물건이 아니라, 당시 사람들의 삶과 정신이 담긴
소중한 역사의 증거입니다.

## 마무리

(부드럽게) 오늘 감상해주셔서 감사합니다.
이 유물이 여러분에게 특별한 영감을 주었기를 바랍니다.

---
*[DRY RUN 모드로 생성된 테스트 스크립트 - 프롬프트 버전: {script_prompt_version}]*
"""
    return script


def run(
    search_keyword: str,
    *,
    info_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    script_prompt_version: str = "v1",
    custom_prompt: Optional[str] = None,
    dry_run: bool = False,
    temperature: float = 0.7,
    model: str = "gpt-4.1",
    output_name: Optional[str] = None
) -> Path:
    """
    스크립트 생성 파이프라인 실행

    Args:
        search_keyword: 유물/장소 검색 키워드 (예: "청자 상감운학문 매병")
        info_dir: 정보 파일이 위치한 디렉토리 (기본: outputs/info)
        output_dir: 스크립트를 저장할 디렉토리 (기본: outputs/script)
        script_prompt_version: 스크립트 프롬프트 템플릿 버전 (기본: "v1")
        custom_prompt: 사용자 커스텀 프롬프트 (선택적, 기본 프롬프트에 추가됨)
        dry_run: True이면 API 호출 없이 고정 템플릿 생성
        temperature: LLM temperature 파라미터 (0.0~1.0)
        model: 사용할 OpenAI 모델명 (기본: "gpt-4.1")
        output_name: 파일명으로 사용할 이름 (선택적, 미제공 시 search_keyword 사용)

    Returns:
        생성된 스크립트 파일의 경로 (Path 객체)

    Raises:
        FileNotFoundError: 정보 파일 또는 프롬프트 템플릿을 찾을 수 없을 때
        ValueError: API 키가 설정되지 않았을 때 (dry_run=False인 경우)
        Exception: API 호출 실패 등 기타 오류
    """
    # 환경변수 로드
    load_dotenv()

    # 기본 경로 설정
    if info_dir is None:
        info_dir = Path("outputs/info")
    if output_dir is None:
        output_dir = DEFAULT_MOCK_OUTPUT_DIR if dry_run else DEFAULT_OUTPUT_DIR

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)

    # 파일 경로 생성 (path_sanitizer 헬퍼 사용)
    info_file = info_markdown_path(search_keyword, info_dir, output_name)
    output_file = script_markdown_path(search_keyword, output_dir, output_name)

    logger.info(f"스크립트 생성 파이프라인 시작: {search_keyword}")
    logger.info(f"스크립트 프롬프트 버전: {script_prompt_version}")
    if custom_prompt:
        logger.info(f"커스텀 프롬프트 추가: 예")
    logger.info(f"입력 파일: {info_file}")
    logger.info(f"출력 파일: {output_file}")

    # 프롬프트 템플릿 로드
    try:
        prompt_template = load_prompt(script_prompt_version)
        logger.info(f"프롬프트 템플릿 로드 완료: {prompt_template.name}")
        logger.info(f"프롬프트 설명: {prompt_template.description}")
        logger.info(f"프롬프트 태그: {', '.join(prompt_template.tags)}")
    except FileNotFoundError as e:
        logger.error(f"프롬프트 템플릿 로드 실패: {e}")
        available = list_prompts()
        logger.info(f"사용 가능한 버전: {', '.join(available)}")
        raise

    # dry_run 모드 처리
    if dry_run:
        logger.info("DRY RUN 모드: 고정 템플릿 스크립트 생성")
        script_content = _generate_dry_run_script(search_keyword, script_prompt_version)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(script_content)

        logger.info(f"✅ 테스트 스크립트 생성 완료: {output_file}")

        # 메타데이터 생성
        try:
            create_metadata(
                search_keyword=search_keyword,
                pipeline="script_gen",
                output_file_path=output_file,
                mode="dry_run",
                model=None
            )
        except Exception as e:
            logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")

        return output_file

    # 정보 파일 존재 확인
    if not info_file.exists():
        error_msg = f"정보 파일을 찾을 수 없습니다: {info_file}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    # 정보 파일 읽기
    logger.info("정보 파일 읽기 중...")
    with open(info_file, "r", encoding="utf-8") as f:
        info_content = f.read()

    logger.info(f"정보 파일 로드 완료 (길이: {len(info_content)} 문자)")

    # API 키 확인
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_msg = "OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."
        logger.error(error_msg)
        raise ValueError(error_msg)

    # 프롬프트 생성
    user_prompt = prompt_template.format_user_prompt(info_content=info_content)

    # 커스텀 프롬프트가 있으면 플레인 텍스트로 추가
    if custom_prompt:
        user_prompt += f"\n\n{custom_prompt}"
        logger.info("커스텀 프롬프트가 기본 프롬프트에 추가되었습니다")

    # LLM 호출
    try:
        logger.info(f"LLM 호출 시작 (모델: {model}, temperature: {temperature})")

        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": prompt_template.system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=temperature
        )

        script_content = response.choices[0].message.content
        logger.info(f"LLM 응답 수신 완료 (길이: {len(script_content)} 문자)")

    except Exception as e:
        error_msg = f"LLM 호출 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e

    # 스크립트 저장
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(script_content)
        logger.info(f"✅ 스크립트 파일 저장 완료: {output_file}")

    except Exception as e:
        error_msg = f"스크립트 파일 저장 중 오류 발생: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e

    # 메타데이터 생성
    try:
        create_metadata(
            search_keyword=search_keyword,
            pipeline="script_gen",
            output_file_path=output_file,
            mode="production",
            model=model
        )
    except Exception as e:
        logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")

    return output_file


def main():
    """CLI 진입점"""
    import argparse

    parser = argparse.ArgumentParser(
        description="오디오 가이드 스크립트 생성 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 기본 사용 (v1 프롬프트, dry-run)
  python src/pipelines/script_gen.py --search-keyword "청자 상감운학문 매병" --dry-run

  # v2 프롬프트로 실제 생성
  python src/pipelines/script_gen.py --search-keyword "청자 상감운학문 매병" --script-prompt-version v2

  # 커스텀 프롬프트 추가
  python src/pipelines/script_gen.py --search-keyword "청자 매병" --custom-prompt "전문적인 톤 사용"

  # 사용 가능한 프롬프트 버전 확인
  python src/pipelines/script_gen.py --list-prompts
        """
    )
    parser.add_argument(
        "--search-keyword",
        type=str,
        help="유물/장소 검색 키워드 (예: '청자 상감운학문 매병')"
    )
    parser.add_argument(
        "--info-dir",
        type=Path,
        default=None,
        help="정보 파일 디렉토리 (기본: outputs/info)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="출력 디렉토리 (기본: outputs/script)"
    )
    parser.add_argument(
        "--script-prompt-version",
        type=str,
        default="v1",
        help="스크립트 프롬프트 템플릿 버전 (기본: v1)"
    )
    parser.add_argument(
        "--custom-prompt",
        type=str,
        default=None,
        help="사용자 커스텀 프롬프트 (기본 프롬프트에 추가됨)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="테스트 모드 (API 호출 없이 고정 템플릿 생성)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (0.0~1.0, 기본: 0.7)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1",
        help="OpenAI 모델명 (기본: gpt-4.1)"
    )
    parser.add_argument(
        "--list-prompts",
        action="store_true",
        help="사용 가능한 프롬프트 버전 목록 출력"
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="파일명으로 사용할 이름 (미제공 시 search_keyword 사용)"
    )

    args = parser.parse_args()

    # 프롬프트 목록 출력 모드
    if args.list_prompts:
        print("\n사용 가능한 프롬프트 버전:")
        print("="*70)
        for version in list_prompts():
            try:
                template = load_prompt(version)
                print(f"\n📝 {version}:")
                print(f"    이름: {template.name}")
                print(f"    설명: {template.description}")
                print(f"    태그: {', '.join(template.tags)}")
                if hasattr(template, 'parameters'):
                    print(f"    파라미터: {template.parameters}")
            except Exception as e:
                print(f"\n❌ {version}: (로드 실패 - {e})")
        print("\n" + "="*70)
        print("\n💡 사용 예시:")
        print("  python src/pipelines/script_gen.py --search-keyword \"청자 매병\" --script-prompt-version v1")
        print("  python src/pipelines/script_gen.py --search-keyword \"석굴암\" --script-prompt-version v2-tts")
        print("="*70)
        return

    # search_keyword 필수 체크
    if not args.search_keyword:
        parser.error("--search-keyword 인자가 필요합니다 (또는 --list-prompts 사용)")

    try:
        output_path = run(
            search_keyword=args.search_keyword,
            info_dir=args.info_dir,
            output_dir=args.output_dir,
            script_prompt_version=args.script_prompt_version,
            custom_prompt=args.custom_prompt,
            dry_run=args.dry_run,
            temperature=args.temperature,
            model=args.model,
            output_name=args.output_name
        )

        print("\n" + "="*60)
        print("✅ 스크립트 생성 완료!")
        print("="*60)
        print(f"검색 키워드: {args.search_keyword}")
        print(f"스크립트 프롬프트 버전: {args.script_prompt_version}")
        if args.custom_prompt:
            print(f"커스텀 프롬프트: 추가됨")
        print(f"출력 파일: {output_path}")
        print(f"모드: {'DRY RUN (테스트)' if args.dry_run else '실제 생성'}")
        print("="*60)

        # 생성된 스크립트 미리보기 (처음 200자)
        with open(output_path, "r", encoding="utf-8") as f:
            content = f.read()
            preview = content[:200]

        print("\n📄 스크립트 미리보기:")
        print("-"*60)
        print(preview + "..." if len(content) > 200 else preview)
        print("-"*60)

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
