"""
프롬프트 템플릿 로더 유틸리티

YAML 형식으로 저장된 프롬프트 템플릿을 로드하는 통합 모듈.
- 파일명 기반 버전 관리 (예: v1.yaml, v2.yaml)
- 파이프라인별 디렉토리 자동 감지 (info_retrieval, script_generation)
- 다양한 API 타입 지원 (Responses API, Chat Completions API)

사용 예시:
    # Pipeline 2 (script_gen) - 기존 방식 (하위 호환)
    template = load_prompt("v2-tts")

    # Pipeline 1 (info_retrieval) - 파이프라인 타입 명시
    template = load_prompt("default", pipeline_type="info_retrieval")
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# 파이프라인별 기본 디렉토리 매핑
PIPELINE_DIRECTORIES = {
    "info_retrieval": "prompts/info_retrieval",
    "script_generation": "prompts/script_generation"
}


class PromptTemplate:
    """
    프롬프트 템플릿 클래스 (통합 버전)

    다양한 API 타입을 지원합니다:
    - 'chat': OpenAI Chat Completions API (system_prompt + user_prompt_template)
    - 'responses': OpenAI Responses API (instructions + input_template + tools)
    """

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
        self.metadata = template_data.get("metadata", {})

        # API 타입 감지 (명시되지 않았으면 자동 감지)
        self.api_type = template_data.get("api_type", self._detect_api_type(template_data))

        # Chat Completions API용 필드
        self.system_prompt = template_data.get("system_prompt", "")
        self.user_prompt_template = template_data.get("user_prompt_template", "")

        # Responses API용 필드
        self.instructions = template_data.get("instructions", "")
        self.input_template = template_data.get("input_template", "")
        self.tools = template_data.get("tools", [])

    def _detect_api_type(self, template_data: Dict[str, Any]) -> str:
        """
        YAML 스키마를 기반으로 API 타입 자동 감지

        Returns:
            'responses' 또는 'chat' (기본값)
        """
        # instructions 또는 input_template이 있으면 Responses API
        if "instructions" in template_data or "input_template" in template_data:
            return "responses"
        # system_prompt이 있으면 Chat Completions API
        elif "system_prompt" in template_data:
            return "chat"
        # 기본값은 chat (하위 호환성)
        else:
            logger.warning("API 타입을 감지할 수 없어 'chat'으로 기본 설정합니다.")
            return "chat"

    def format_user_prompt(self, **kwargs) -> str:
        """
        유저 프롬프트 템플릿에 변수 치환 (Chat Completions API용)

        Args:
            **kwargs: 템플릿 변수 (예: info_content, duration_minutes)

        Returns:
            치환된 프롬프트 문자열
        """
        # 파라미터 기본값과 전달된 값을 병합
        params = {**self.parameters, **kwargs}
        return self.user_prompt_template.format(**params)

    def format_input(self, **kwargs) -> str:
        """
        input 템플릿에 변수 치환 (Responses API용)

        Args:
            **kwargs: 템플릿 변수 (예: search_keyword)

        Returns:
            치환된 input 문자열
        """
        # 파라미터 기본값과 전달된 값을 병합
        params = {**self.parameters, **kwargs}
        return self.input_template.format(**params)

    def is_responses_api(self) -> bool:
        """Responses API 타입인지 확인"""
        return self.api_type == "responses"

    def is_chat_api(self) -> bool:
        """Chat Completions API 타입인지 확인"""
        return self.api_type == "chat"


def load_prompt(
    version: str = "v1",
    prompt_dir: Optional[Path] = None,
    pipeline_type: str = "script_generation"
) -> PromptTemplate:
    """
    프롬프트 템플릿 로드 (통합 버전)

    Args:
        version: 버전 (파일명, 예: "v1", "v2", "default")
        prompt_dir: 프롬프트 디렉토리 (명시하지 않으면 pipeline_type으로 자동 설정)
        pipeline_type: 파이프라인 타입 ("script_generation" 또는 "info_retrieval")
                      prompt_dir이 None일 때만 사용됨

    Returns:
        PromptTemplate 객체

    Raises:
        FileNotFoundError: 템플릿 파일을 찾을 수 없을 때
        ValueError: 지원하지 않는 pipeline_type일 때

    Examples:
        # 기존 방식 (하위 호환)
        template = load_prompt("v2-tts")

        # 파이프라인 타입 명시
        template = load_prompt("default", pipeline_type="info_retrieval")

        # 커스텀 디렉토리
        template = load_prompt("custom", prompt_dir=Path("my_prompts"))
    """
    # 디렉토리 결정
    if prompt_dir is None:
        if pipeline_type not in PIPELINE_DIRECTORIES:
            raise ValueError(
                f"지원하지 않는 pipeline_type: {pipeline_type}. "
                f"가능한 값: {list(PIPELINE_DIRECTORIES.keys())}"
            )
        prompt_dir = Path(PIPELINE_DIRECTORIES[pipeline_type])
    else:
        prompt_dir = Path(prompt_dir)

    # .yaml 확장자 자동 추가
    if not version.endswith(".yaml"):
        template_file = prompt_dir / f"{version}.yaml"
    else:
        template_file = prompt_dir / version

    if not template_file.exists():
        raise FileNotFoundError(
            f"프롬프트 템플릿을 찾을 수 없습니다: {template_file}\n"
            f"디렉토리: {prompt_dir}\n"
            f"사용 가능한 버전: {list_prompts(prompt_dir=prompt_dir, pipeline_type=pipeline_type)}"
        )

    logger.info(f"프롬프트 템플릿 로드: {template_file}")
    with open(template_file, "r", encoding="utf-8") as f:
        template_data = yaml.safe_load(f)

    return PromptTemplate(version, template_data)


def list_prompts(
    prompt_dir: Optional[Path] = None,
    pipeline_type: str = "script_generation"
) -> List[str]:
    """
    사용 가능한 프롬프트 버전 목록 조회 (통합 버전)

    Args:
        prompt_dir: 프롬프트 디렉토리 (명시하지 않으면 pipeline_type으로 자동 설정)
        pipeline_type: 파이프라인 타입 ("script_generation" 또는 "info_retrieval")

    Returns:
        버전 리스트 (예: ["v1", "v2", "default"])

    Examples:
        # 기존 방식
        versions = list_prompts()

        # 파이프라인 타입 명시
        versions = list_prompts(pipeline_type="info_retrieval")
    """
    # 디렉토리 결정
    if prompt_dir is None:
        if pipeline_type not in PIPELINE_DIRECTORIES:
            logger.warning(
                f"지원하지 않는 pipeline_type: {pipeline_type}. "
                f"script_generation으로 대체합니다."
            )
            pipeline_type = "script_generation"
        prompt_dir = Path(PIPELINE_DIRECTORIES[pipeline_type])
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
    # 통합 테스트 코드
    print("=== 프롬프트 로더 통합 테스트 ===\n")

    # Pipeline 2 (script_generation) 테스트
    print("📝 Pipeline 2 (script_generation) 테스트")
    print("-" * 60)
    script_versions = list_prompts(pipeline_type="script_generation")
    print(f"사용 가능한 버전: {script_versions}")

    if script_versions:
        template = load_prompt(script_versions[0], pipeline_type="script_generation")
        print(f"\n버전: {template.version}")
        print(f"이름: {template.name}")
        print(f"API 타입: {template.api_type}")
        print(f"태그: {', '.join(template.tags)}")

        if template.is_chat_api():
            user_prompt = template.format_user_prompt(info_content="[테스트 정보]")
            print(f"\n프롬프트 미리보기:\n{user_prompt[:200]}...")

    # Pipeline 1 (info_retrieval) 테스트
    print("\n\n🔍 Pipeline 1 (info_retrieval) 테스트")
    print("-" * 60)
    info_versions = list_prompts(pipeline_type="info_retrieval")
    print(f"사용 가능한 버전: {info_versions}")

    if info_versions:
        template = load_prompt(info_versions[0], pipeline_type="info_retrieval")
        print(f"\n버전: {template.version}")
        print(f"이름: {template.name}")
        print(f"API 타입: {template.api_type}")
        print(f"태그: {', '.join(template.tags)}")

        if template.is_responses_api():
            input_text = template.format_input(search_keyword="청자 매병")
            print(f"\ninput 미리보기: {input_text}")
            print(f"tools: {template.tools}")
