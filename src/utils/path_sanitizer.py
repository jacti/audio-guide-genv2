"""
파일 경로 생성을 위한 키워드 정제 유틸리티.

Pipeline 1~3이 동일한 규칙으로 파일명을 만들 수 있도록 중앙집중식으로 관리한다.
"""

from __future__ import annotations

from pathlib import Path

# 파일 시스템에서 허용되지 않는 문자를 모두 제거한다.
_INVALID_FILENAME_CHARS = '<>:"/\\|?*'


def sanitize_keyword_for_path(keyword: str) -> str:
    """파이프라인 공통 규칙에 맞춰 키워드를 파일명으로 변환한다.

    Args:
        keyword: 유물이나 장소 이름 등 원본 키워드

    Returns:
        공백은 유지하고, 운영체제에서 사용할 수 없는 특수문자를 제거한 문자열
    """
    sanitized = keyword.strip()
    for char in _INVALID_FILENAME_CHARS:
        sanitized = sanitized.replace(char, "")
    return sanitized


def info_markdown_path(keyword: str, base_dir: Path) -> Path:
    """정보 파이프라인 산출물 경로를 생성한다."""
    return Path(base_dir) / f"{sanitize_keyword_for_path(keyword)}.md"


def script_markdown_path(keyword: str, base_dir: Path) -> Path:
    """스크립트 파이프라인 산출물 경로를 생성한다."""
    return Path(base_dir) / f"{sanitize_keyword_for_path(keyword)}_script.md"


def audio_output_path(keyword: str, base_dir: Path) -> Path:
    """오디오 파이프라인 산출물 경로를 생성한다."""
    return Path(base_dir) / f"{sanitize_keyword_for_path(keyword)}.mp3"


__all__ = [
    "sanitize_keyword_for_path",
    "info_markdown_path",
    "script_markdown_path",
    "audio_output_path",
]
