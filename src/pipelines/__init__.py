"""오디오 가이드 생성 파이프라인 패키지의 공개 API.

세 단계 파이프라인(info → script → audio)의 실행 함수를 재노출해
외부 모듈이 손쉽게 사용할 수 있도록 정리했다.
"""

from .info_retrieval import run as run_info_retrieval
from .script_gen import run as run_script_generation
from .audio_gen import run as run_audio_generation

# 하위 호환을 위해 기존 이름을 유지
generate_audio = run_audio_generation

__all__ = [
    "run_info_retrieval",
    "run_script_generation",
    "run_audio_generation",
    "generate_audio",
]
