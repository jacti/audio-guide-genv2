"""
YAML 기반 프롬프트 유틸리티

- YAML 파일을 Dict로 로드
- 파이프라인 타입별 기본 디렉토리 감지
- 문자열 템플릿 포맷팅 및 키 접근 헬퍼
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

import yaml

logger = logging.getLogger(__name__)

# 파이프라인별 기본 디렉토리 매핑
PIPELINE_DIRECTORIES = {
    "info_retrieval": "prompts/info_retrieval",
    "script_generation": "prompts/script_generation",
}


def _resolve_prompt_dir(prompt_dir: Optional[Path], pipeline_type: str) -> Path:
    """prompt_dir가 없으면 pipeline_type으로 기본 경로를 찾는다."""
    if prompt_dir is not None:
        return Path(prompt_dir)

    if pipeline_type not in PIPELINE_DIRECTORIES:
        raise ValueError(
            f"지원하지 않는 pipeline_type: {pipeline_type}. "
            f"가능한 값: {list(PIPELINE_DIRECTORIES.keys())}"
        )

    return Path(PIPELINE_DIRECTORIES[pipeline_type])


def _resolve_prompt_path(version: str, prompt_dir: Path) -> Path:
    """버전 문자열을 파일 경로로 변환한다."""
    file_name = version if version.endswith(".yaml") else f"{version}.yaml"
    return prompt_dir / file_name


def load_prompt(
    version: str = "v1",
    prompt_dir: Optional[Path] = None,
    pipeline_type: str = "script_generation",
) -> Dict[str, Any]:
    """
    YAML 프롬프트를 로드해 Dict를 반환한다.
    """
    resolved_dir = _resolve_prompt_dir(prompt_dir, pipeline_type)
    template_file = _resolve_prompt_path(version, resolved_dir)

    if not template_file.exists():
        raise FileNotFoundError(
            f"프롬프트 템플릿을 찾을 수 없습니다: {template_file}\n"
            f"디렉토리: {resolved_dir}\n"
            f"사용 가능한 버전: {list_prompts(prompt_dir=resolved_dir, pipeline_type=pipeline_type)}"
        )

    logger.info(f"프롬프트 템플릿 로드: {template_file}")
    with open(template_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"YAML 파일이 dict 형식이 아닙니다: {template_file}")

    data.setdefault("parameters", {})
    data["version"] = template_file.stem
    data["path"] = template_file
    data["pipeline_type"] = pipeline_type
    return data


def list_prompts(
    prompt_dir: Optional[Path] = None, pipeline_type: str = "script_generation"
) -> List[str]:
    """사용 가능한 프롬프트 버전 목록을 반환한다."""
    resolved_dir = _resolve_prompt_dir(prompt_dir, pipeline_type)

    if not resolved_dir.exists():
        logger.warning(f"프롬프트 디렉토리를 찾을 수 없습니다: {resolved_dir}")
        return []

    versions = [f.stem for f in resolved_dir.glob("*.yaml") if f.is_file()]
    return sorted(versions)


def format_prompt(
    template: str,
    *,
    parameters: Optional[Dict[str, Any]] = None,
    **overrides: Any,
) -> str:
    """문자열 템플릿을 파라미터로 포맷한다."""
    merged = {}
    if parameters:
        merged.update(parameters)
    merged.update(overrides)
    return template.format(**merged)


def get_prompt_value(prompt_config: Dict[str, Any], key: str, default=None):
    """프롬프트 Dict에서 안전하게 값을 꺼낸다."""
    return prompt_config.get(key, default)
