"""
프롬프트 템플릿 로더 유틸리티

YAML 형식으로 저장된 프롬프트 템플릿을 로드하는 단순한 모듈.
파일명 기반으로 버전 관리 (예: v1.yaml, v2.yaml)
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class PromptTemplate:
    """프롬프트 템플릿 클래스"""

    def __init__(self, version: str, template_data: Dict[str, Any]):
        """
        Args:
            version: 템플릿 버전 (파일명에서 추출)
            template_data: YAML에서 로드한 템플릿 데이터
        """
        self.version = version
        self.name = template_data.get("name", "")
        self.description = template_data.get("description", "")
        self.tags = template_data.get("tags", [])
        self.parameters = template_data.get("parameters", {})
        self.system_prompt = template_data.get("system_prompt", "")
        self.user_prompt_template = template_data.get("user_prompt_template", "")

    def format_user_prompt(self, **kwargs) -> str:
        """
        유저 프롬프트 템플릿에 변수 치환

        Args:
            **kwargs: 템플릿 변수 (예: info_content, duration_minutes)

        Returns:
            치환된 프롬프트 문자열
        """
        # 파라미터 기본값과 전달된 값을 병합
        params = {**self.parameters, **kwargs}
        return self.user_prompt_template.format(**params)


def load_prompt(
    version: str = "v1",
    prompt_dir: Optional[Path] = None
) -> PromptTemplate:
    """
    프롬프트 템플릿 로드

    Args:
        version: 버전 (파일명, 예: "v1", "v2")
        prompt_dir: 프롬프트 디렉토리 (기본: prompts/script_generation)

    Returns:
        PromptTemplate 객체

    Raises:
        FileNotFoundError: 템플릿 파일을 찾을 수 없을 때
    """
    if prompt_dir is None:
        prompt_dir = Path("prompts/script_generation")
    else:
        prompt_dir = Path(prompt_dir)

    # .yaml 확장자 자동 추가
    if not version.endswith(".yaml"):
        template_file = prompt_dir / f"{version}.yaml"
    else:
        template_file = prompt_dir / version

    if not template_file.exists():
        raise FileNotFoundError(
            f"프롬프트 템플릿을 찾을 수 없습니다: {template_file}"
        )

    logger.info(f"프롬프트 템플릿 로드: {template_file}")
    with open(template_file, "r", encoding="utf-8") as f:
        template_data = yaml.safe_load(f)

    return PromptTemplate(version, template_data)


def list_prompts(prompt_dir: Optional[Path] = None) -> List[str]:
    """
    사용 가능한 프롬프트 버전 목록 조회

    Args:
        prompt_dir: 프롬프트 디렉토리

    Returns:
        버전 리스트 (예: ["v1", "v2"])
    """
    if prompt_dir is None:
        prompt_dir = Path("prompts/script_generation")
    else:
        prompt_dir = Path(prompt_dir)

    if not prompt_dir.exists():
        logger.warning(f"프롬프트 디렉토리를 찾을 수 없습니다: {prompt_dir}")
        return []

    # .yaml 파일만 필터링하고 확장자 제거
    versions = [
        f.stem for f in prompt_dir.glob("*.yaml")
        if f.is_file()
    ]
    return sorted(versions)


if __name__ == "__main__":
    # 테스트 코드
    print("=== 프롬프트 로더 테스트 ===\n")

    print("사용 가능한 버전:")
    versions = list_prompts()
    for ver in versions:
        print(f"  - {ver}")

    print("\n=== v1 템플릿 로드 ===")
    template = load_prompt("v1")
    print(f"버전: {template.version}")
    print(f"이름: {template.name}")
    print(f"설명: {template.description}")
    print(f"태그: {', '.join(template.tags)}")
    print(f"파라미터: {template.parameters}")
    print(f"\n시스템 프롬프트:\n{template.system_prompt[:150]}...")

    print("\n=== 프롬프트 변수 치환 테스트 ===")
    user_prompt = template.format_user_prompt(
        info_content="[테스트 유물 정보]",
        duration_minutes=1.5
    )
    print(f"치환된 프롬프트 미리보기:\n{user_prompt[:250]}...")
