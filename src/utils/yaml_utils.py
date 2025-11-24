"""
YAML 유틸리티

- 지정한 경로의 YAML을 Dict로 로드
- 디렉토리 내 YAML 파일 목록 조회
- 문자열 템플릿 포맷 및 키 접근 헬퍼

이 모듈은 경로를 외부에서 주입받는 순수 유틸로만 동작합니다.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

import yaml

logger = logging.getLogger(__name__)


def load_yaml(path: Path) -> Dict[str, Any]:
    """주어진 경로의 YAML을 로드해 Dict로 반환한다."""
    if not path.exists():
        raise FileNotFoundError(f"YAML 파일을 찾을 수 없습니다: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"YAML 파일이 dict 형식이 아닙니다: {path}")

    return data


def list_yaml_files(directory: Path) -> List[str]:
    """디렉토리 내 YAML 파일 목록을 stem 리스트로 반환한다."""
    if not directory.exists():
        logger.warning(f"YAML 디렉토리를 찾을 수 없습니다: {directory}")
        return []

    return sorted([p.stem for p in directory.glob("*.yaml") if p.is_file()])


def format_template(
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


def get_value(config: Dict[str, Any], key: str, default=None):
    """Dict에서 안전하게 값을 꺼낸다."""
    return config.get(key, default)
