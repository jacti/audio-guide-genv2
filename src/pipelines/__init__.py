"""
오디오 가이드 생성 파이프라인 모듈

세 가지 독립적인 파이프라인으로 구성:
1. info_retrieval: 정보 검색 및 요약
2. script_gen: 스크립트 생성
3. audio_gen: 오디오 파일 생성
"""

from .audio_gen import run as generate_audio

__all__ = ["generate_audio"]
"""
오디오 가이드 생성 파이프라인 모듈

이 모듈은 세 가지 독립적인 파이프라인으로 구성됩니다:
1. info_retrieval: 문화유산 정보 검색 및 Markdown 생성
2. script_gen: 오디오 가이드 스크립트 생성 (향후 구현)
3. audio_gen: TTS를 활용한 오디오 파일 생성 (향후 구현)
"""

from pathlib import Path
from typing import Optional

# Pipeline 1: 정보 검색
try:
    from .info_retrieval import run as info_retrieval_run
except ImportError:
    info_retrieval_run = None

__all__ = [
    "info_retrieval_run",
]


def run_info_retrieval(
    keyword: str,
    *,
    output_dir: Optional[Path] = None,
    model: str = "gpt-4o-mini",
    dry_run: bool = False
) -> Path:
    """
    정보 검색 파이프라인 실행 (래퍼 함수)

    Args:
        keyword: 검색할 문화유산 키워드
        output_dir: 출력 디렉토리 (기본값: outputs/info)
        model: 사용할 OpenAI 모델명
        dry_run: True일 경우 API 호출 없이 목업 데이터 사용

    Returns:
        Path: 생성된 Markdown 파일의 절대 경로
    """
    if info_retrieval_run is None:
        raise ImportError("info_retrieval 모듈을 불러올 수 없습니다.")

    return info_retrieval_run(
        keyword=keyword,
        output_dir=output_dir,
        model=model,
        dry_run=dry_run
    )
