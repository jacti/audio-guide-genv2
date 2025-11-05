"""
오디오 생성 파이프라인 (Pipeline 3)

스크립트 파일(Markdown)을 읽어 OpenAI TTS API를 통해 음성 파일(MP3)로 변환합니다.

주요 기능:
- OpenAI TTS API 연동 (gpt-4o-mini-tts 모델 사용)
- 재시도 로직 (네트워크 오류 대응)
- dry_run 모드 (테스트용 더미 파일 생성)
- 로깅 및 예외 처리
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional
import argparse

from openai import OpenAI
from dotenv import load_dotenv

from src.utils.path_sanitizer import script_markdown_path, audio_output_path
from src.utils.metadata import create_metadata

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 기본 설정
DEFAULT_OUTPUT_DIR = Path("outputs/audio")
DEFAULT_MOCK_OUTPUT_DIR = Path("outputs/mock/audio")


def _read_script(script_path: Path) -> str:
    """
    스크립트 파일을 읽어 텍스트를 반환합니다.

    Args:
        script_path: 스크립트 파일 경로

    Returns:
        str: 스크립트 텍스트 내용

    Raises:
        FileNotFoundError: 스크립트 파일이 존재하지 않을 경우
    """
    if not script_path.exists():
        raise FileNotFoundError(
            f"스크립트 파일을 찾을 수 없습니다: {script_path}\n"
            f"스크립트 생성 파이프라인을 먼저 실행해주세요."
        )

    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        raise ValueError(f"스크립트 파일이 비어있습니다: {script_path}")

    logger.info(f"스크립트 로드 완료: {script_path} ({len(content)} 글자)")
    return content


def _generate_audio_openai(
    text: str,
    model: str = "gpt-4o-mini-tts",
    voice: str = "alloy",
    speed: float = 1.0,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> bytes:
    """
    OpenAI TTS API를 호출하여 음성 데이터를 생성합니다.

    Args:
        text: 변환할 텍스트
        model: 사용할 TTS 모델명 (기본값: "gpt-4o-mini-tts")
        voice: 음성 종류 (alloy, echo, fable, onyx, nova, shimmer 중 선택)
        speed: 말하기 속도 (0.25 ~ 4.0, 기본값: 1.0)
        max_retries: 최대 재시도 횟수
        retry_delay: 재시도 대기 시간 (초)

    Returns:
        bytes: 생성된 오디오 바이너리 데이터

    Raises:
        ValueError: API 키가 설정되지 않았거나 파라미터가 유효하지 않을 경우
        Exception: API 호출 실패 시
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY 환경변수가 설정되지 않았습니다.\n"
            ".env 파일에 API 키를 설정해주세요."
        )

    # 파라미터 검증
    valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
    if voice not in valid_voices:
        raise ValueError(f"유효하지 않은 voice 값입니다. 선택 가능: {valid_voices}")

    if not (0.25 <= speed <= 4.0):
        raise ValueError(f"speed는 0.25 ~ 4.0 사이여야 합니다. 입력값: {speed}")

    client = OpenAI(api_key=api_key)

    # 재시도 로직
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"OpenAI TTS API 호출 중 (시도 {attempt}/{max_retries}): "
                f"model={model}, voice={voice}, speed={speed}"
            )

            response = client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed
            )

            # 응답 데이터 읽기
            audio_data = response.content

            logger.info(f"음성 생성 완료 ({len(audio_data)} bytes)")
            return audio_data

        except Exception as e:
            logger.warning(f"API 호출 실패 (시도 {attempt}/{max_retries}): {e}")

            if attempt < max_retries:
                logger.info(f"{retry_delay}초 후 재시도합니다...")
                time.sleep(retry_delay)
            else:
                raise Exception(
                    f"OpenAI TTS API 호출 실패 (최대 재시도 횟수 초과): {e}"
                ) from e


def _create_dummy_audio(output_path: Path) -> None:
    """
    dry_run 모드에서 사용할 더미 MP3 파일을 생성합니다.

    Args:
        output_path: 더미 파일을 생성할 경로
    """
    # 간단한 MP3 헤더 (실제 재생은 안되지만 파일 형식은 유지)
    dummy_mp3_header = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # MP3 동기 워드와 기본 헤더
        0x00, 0x00, 0x00, 0x00,
        0x49, 0x6E, 0x66, 0x6F   # "Info" 태그
    ])

    with open(output_path, "wb") as f:
        f.write(dummy_mp3_header)
        # 더미 메타데이터 추가
        f.write(b"\x00" * 100)

    logger.info(f"더미 MP3 파일 생성 완료: {output_path}")


def run(
    keyword: str,
    *,
    script_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    voice: str = "alloy",
    model: str = "gpt-4o-mini-tts",
    speed: float = 1.0,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    dry_run: bool = False
) -> Path:
    """
    오디오 생성 파이프라인 메인 진입점.

    스크립트 파일을 읽어 OpenAI TTS API를 통해 MP3 파일로 변환합니다.

    Args:
        keyword: 유물 키워드 (파일명 결정에 사용)
        script_dir: 스크립트 디렉토리 경로 (기본값: outputs/script)
        output_dir: 출력 디렉토리 경로 (기본값: outputs/audio)
        voice: TTS 음성 종류 (기본값: "alloy")
        model: TTS 모델명 (기본값: "gpt-4o-mini-tts")
        speed: 말하기 속도 (기본값: 1.0)
        max_retries: API 호출 최대 재시도 횟수 (기본값: 3)
        retry_delay: 재시도 대기 시간(초) (기본값: 2.0)
        dry_run: True일 경우 API 호출 없이 더미 파일 생성 (기본값: False)

    Returns:
        Path: 생성된 MP3 파일의 절대 경로

    Raises:
        FileNotFoundError: 스크립트 파일이 존재하지 않을 경우
        ValueError: 파라미터가 유효하지 않거나 API 키가 없을 경우
        Exception: API 호출 실패 시

    Examples:
        >>> # 기본 사용법 (공백이 유지됨)
        >>> output_path = run("청자 상감운학문 매병")
        >>> print(output_path)
        /path/to/outputs/audio/청자 상감운학문 매병.mp3

        >>> # dry_run 모드
        >>> output_path = run("테스트", dry_run=True)
    """
    logger.info(f"=== 오디오 생성 파이프라인 시작: '{keyword}' ===")

    # 기본 경로 설정: dry_run 모드일 때 입력/출력 모두 mock 디렉토리 사용
    if script_dir is None:
        script_dir = Path("outputs/mock/script") if dry_run else Path("outputs/script")
    if output_dir is None:
        output_dir = DEFAULT_MOCK_OUTPUT_DIR if dry_run else DEFAULT_OUTPUT_DIR

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {output_dir.absolute()}")

    # 공통 헬퍼를 사용해 경로 생성 (공백 유지, 특수문자 제거)
    script_path = script_markdown_path(keyword, script_dir)
    output_path = audio_output_path(keyword, output_dir)

    # 스크립트 파일 읽기
    script_text = _read_script(script_path)

    if dry_run:
        logger.info("🧪 DRY RUN 모드: 실제 API 호출 없이 더미 파일 생성")
        _create_dummy_audio(output_path)

        # 메타데이터 생성 (dry_run)
        try:
            create_metadata(
                keyword=keyword,
                pipeline="audio_gen",
                output_file_path=output_path,
                mode="dry_run",
                model=None,
                voice=voice
            )
        except Exception as e:
            logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")
    else:
        # 실제 TTS 생성
        audio_data = _generate_audio_openai(
            text=script_text,
            model=model,
            voice=voice,
            speed=speed,
            max_retries=max_retries,
            retry_delay=retry_delay
        )

        # 파일 저장
        with open(output_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"✅ MP3 파일 저장 완료: {output_path.absolute()}")

        # 메타데이터 생성 (production)
        try:
            create_metadata(
                keyword=keyword,
                pipeline="audio_gen",
                output_file_path=output_path,
                mode="production",
                model=model,
                voice=voice
            )
        except Exception as e:
            logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")

    logger.info(
        f"=== 오디오 생성 파이프라인 완료 ===\n"
        f"  - 입력 스크립트: {script_path}\n"
        f"  - 출력 파일: {output_path.absolute()}\n"
        f"  - Voice: {voice}\n"
        f"  - Model: {model}\n"
        f"  - Speed: {speed}x"
    )

    return output_path.absolute()


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="스크립트 파일을 음성 파일(MP3)로 변환하는 오디오 생성 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python src/pipelines/audio_gen.py --keyword "청자 상감운학문 매병"
  python src/pipelines/audio_gen.py --keyword "테스트" --dry-run
  python src/pipelines/audio_gen.py --keyword "유물명" --voice nova --speed 1.2
        """
    )

    parser.add_argument(
        "--keyword",
        type=str,
        required=True,
        help="유물 키워드 (파일명 결정에 사용)"
    )

    parser.add_argument(
        "--script-dir",
        type=Path,
        default=None,
        help="스크립트 디렉토리 경로 (기본값: outputs/script)"
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="출력 디렉토리 경로 (기본값: outputs/audio)"
    )

    parser.add_argument(
        "--voice",
        type=str,
        default="alloy",
        choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        help="TTS 음성 종류 (기본값: alloy)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini-tts",
        help="TTS 모델명 (기본값: gpt-4o-mini-tts)"
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="말하기 속도 (0.25 ~ 4.0, 기본값: 1.0)"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="API 호출 최대 재시도 횟수 (기본값: 3)"
    )

    parser.add_argument(
        "--retry-delay",
        type=float,
        default=2.0,
        help="재시도 대기 시간(초) (기본값: 2.0)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API 호출 없이 더미 파일만 생성 (테스트용)"
    )

    args = parser.parse_args()

    try:
        output_path = run(
            keyword=args.keyword,
            script_dir=args.script_dir,
            output_dir=args.output_dir,
            voice=args.voice,
            model=args.model,
            speed=args.speed,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            dry_run=args.dry_run
        )

        print(f"\n🎵 오디오 파일이 생성되었습니다: {output_path}")

    except Exception as e:
        logger.error(f"❌ 오디오 생성 실패: {e}")
        raise


if __name__ == "__main__":
    main()
