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

import backoff
from openai import OpenAI, RateLimitError, APIError
from dotenv import load_dotenv

from src.utils.path_sanitizer import script_markdown_path, audio_output_path

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


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
    output_path: Path,
    model: str = "gpt-4o-mini-tts",
    voice: str = "alloy",
    speed: float = 1.0,
    max_retries: int = 8,
    initial_wait: float = 1.0,
    max_wait: float = 60.0
) -> None:
    """
    OpenAI TTS API를 호출하여 음성 파일을 생성합니다.

    지수 백오프(exponential backoff)를 적용하여 Rate Limit 에러 대응.
    생성된 오디오는 output_path에 직접 저장됩니다.

    Args:
        text: 변환할 텍스트
        output_path: 출력 파일 경로 (MP3)
        model: 사용할 TTS 모델명 (기본값: "gpt-4o-mini-tts")
        voice: 음성 종류 (alloy, echo, fable, onyx, nova, shimmer 중 선택)
        speed: 말하기 속도 (0.25 ~ 4.0, 기본값: 1.0)
        max_retries: 최대 재시도 횟수 (기본값: 8)
        initial_wait: 초기 대기 시간 초 (기본값: 1.0)
        max_wait: 최대 대기 시간 초 (기본값: 60.0)

    Returns:
        None (파일에 직접 저장)

    Raises:
        ValueError: API 키가 설정되지 않았거나 파라미터가 유효하지 않을 경우
        RateLimitError: Rate Limit 초과 시 (재시도 후에도 실패)
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

    # 요청 정보 로깅
    text_length = len(text)
    estimated_tokens = text_length // 4  # 대략적인 토큰 수 추정
    logger.info(
        f"📝 TTS 요청 준비:\n"
        f"  - 텍스트 길이: {text_length} 글자\n"
        f"  - 예상 토큰 수: ~{estimated_tokens} tokens\n"
        f"  - 모델: {model}\n"
        f"  - 음성: {voice}\n"
        f"  - 속도: {speed}x"
    )

    client = OpenAI(api_key=api_key)

    # 백오프 핸들러: 재시도 시 로깅
    def on_backoff(details):
        wait_time = details['wait']
        tries = details['tries']
        logger.warning(
            f"⏳ 지수 백오프 적용: {wait_time:.2f}초 대기 중 "
            f"(재시도 {tries}/{max_retries})"
        )

    # 포기 시 핸들러: 최종 실패 로깅
    def on_giveup(details):
        logger.error(
            f"❌ 최대 재시도 횟수 초과 ({max_retries}회): API 호출 포기"
        )

    # 지수 백오프를 적용한 내부 API 호출 함수
    @backoff.on_exception(
        backoff.expo,
        (RateLimitError, APIError),
        max_tries=max_retries,
        max_value=max_wait,
        on_backoff=on_backoff,
        on_giveup=on_giveup,
        jitter=backoff.full_jitter  # 지터 추가로 동시 요청 분산
    )
    def _call_api_with_backoff():
        """지수 백오프가 적용된 실제 API 호출 함수"""
        try:
            logger.info(f"🎤 OpenAI TTS API 호출 시작...")

            # OpenAI TTS API 호출 (최신 문법: with_streaming_response 사용)
            with client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
                speed=speed
            ) as response:
                # 파일에 직접 스트리밍
                response.stream_to_file(str(output_path))

            logger.info(f"✅ 음성 생성 완료: {output_path}")

        except RateLimitError as e:
            # Rate Limit 에러 상세 분석
            error_msg = str(e)

            if "insufficient_quota" in error_msg.lower():
                logger.error(
                    f"💳 할당량 초과 (Insufficient Quota):\n"
                    f"  - OpenAI API 크레딧이 소진되었거나 요금제 한도 초과\n"
                    f"  - 조치 방법:\n"
                    f"    1. https://platform.openai.com/account/billing 에서 크레딧 충전\n"
                    f"    2. 더 높은 요금제로 업그레이드\n"
                    f"    3. 사용량 모니터링: https://platform.openai.com/usage"
                )
            else:
                logger.error(
                    f"⚠️ Rate Limit 초과:\n"
                    f"  - 분당 요청 수(RPM) 또는 분당 토큰 수(TPM) 제한 초과\n"
                    f"  - 재시도 중... (자동으로 대기 시간 증가)"
                )

            # 재시도를 위해 예외를 다시 발생
            raise

        except APIError as e:
            logger.error(f"🔴 OpenAI API 에러: {e}")
            raise

    # 실제 API 호출 실행
    try:
        _call_api_with_backoff()
    except RateLimitError as e:
        # 최종 실패 시 사용자에게 명확한 안내
        if "insufficient_quota" in str(e).lower():
            raise Exception(
                f"💳 OpenAI API 할당량 초과로 TTS 생성 실패\n"
                f"크레딧을 충전하거나 요금제를 업그레이드하세요.\n"
                f"상세 정보: {e}"
            ) from e
        else:
            raise Exception(
                f"⚠️ Rate Limit 초과로 TTS 생성 실패 ({max_retries}회 재시도)\n"
                f"호출 빈도를 낮추거나 더 높은 요금제를 사용하세요.\n"
                f"상세 정보: {e}"
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
    max_retries: int = 8,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    dry_run: bool = False
) -> Path:
    """
    오디오 생성 파이프라인 메인 진입점.

    스크립트 파일을 읽어 OpenAI TTS API를 통해 MP3 파일로 변환합니다.
    지수 백오프(exponential backoff)를 적용하여 Rate Limit 에러 자동 대응.

    Args:
        keyword: 유물 키워드 (파일명 결정에 사용)
        script_dir: 스크립트 디렉토리 경로 (기본값: outputs/script)
        output_dir: 출력 디렉토리 경로 (기본값: outputs/audio)
        voice: TTS 음성 종류 (기본값: "alloy")
        model: TTS 모델명 (기본값: "gpt-4o-mini-tts")
        speed: 말하기 속도 (기본값: 1.0)
        max_retries: API 호출 최대 재시도 횟수 (기본값: 8)
        initial_wait: 초기 대기 시간 초 (기본값: 1.0)
        max_wait: 최대 대기 시간 초 (기본값: 60.0)
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

    # 기본 경로 설정
    if script_dir is None:
        script_dir = Path("outputs/script")
    if output_dir is None:
        output_dir = Path("outputs/audio")

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
    else:
        # 실제 TTS 생성 (파일에 직접 저장됨)
        _generate_audio_openai(
            text=script_text,
            output_path=output_path,
            model=model,
            voice=voice,
            speed=speed,
            max_retries=max_retries,
            initial_wait=initial_wait,
            max_wait=max_wait
        )

        logger.info(f"✅ MP3 파일 저장 완료: {output_path.absolute()}")

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
        default=8,
        help="API 호출 최대 재시도 횟수 (기본값: 8, 지수 백오프 적용)"
    )

    parser.add_argument(
        "--initial-wait",
        type=float,
        default=1.0,
        help="초기 대기 시간 초 (기본값: 1.0, 지수 백오프 시작 값)"
    )

    parser.add_argument(
        "--max-wait",
        type=float,
        default=60.0,
        help="최대 대기 시간 초 (기본값: 60.0, 지수 백오프 상한)"
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
            initial_wait=args.initial_wait,
            max_wait=args.max_wait,
            dry_run=args.dry_run
        )

        print(f"\n🎵 오디오 파일이 생성되었습니다: {output_path}")

    except Exception as e:
        logger.error(f"❌ 오디오 생성 실패: {e}")
        raise


if __name__ == "__main__":
    main()
