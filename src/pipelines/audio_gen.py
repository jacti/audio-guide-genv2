"""
오디오 생성 파이프라인 (Pipeline 3)

스크립트 파일(Markdown)을 읽어 Gemini API를 통해 음성 파일(MP3/WAV)로 변환합니다.

주요 기능:
- Gemini TTS API 연동 (gemini-2.5-pro-preview-tts 모델 사용)
- 재시도 로직 (네트워크 오류 대응)
- dry_run 모드 (테스트용 더미 파일 생성)
- 로깅 및 예외 처리
"""

import logging
import os
import time
import mimetypes
import struct
from pathlib import Path
from typing import Optional
import argparse

import backoff
from google import genai
from google.genai import types
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


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """
    주어진 오디오 데이터에 대한 WAV 파일 헤더를 생성합니다.

    Args:
        audio_data: 원시 오디오 데이터 (bytes)
        mime_type: 오디오 데이터의 MIME type

    Returns:
        bytes: WAV 파일 헤더가 포함된 bytes
    """
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size  # 36 bytes for header fields before data chunk size

    # http://soundfile.sapp.org/doc/WaveFormat/
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",          # ChunkID
        chunk_size,       # ChunkSize (total file size - 8 bytes)
        b"WAVE",          # Format
        b"fmt ",          # Subchunk1ID
        16,               # Subchunk1Size (16 for PCM)
        1,                # AudioFormat (1 for PCM)
        num_channels,     # NumChannels
        sample_rate,      # SampleRate
        byte_rate,        # ByteRate
        block_align,      # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",          # Subchunk2ID
        data_size         # Subchunk2Size (size of audio data)
    )
    return header + audio_data


def parse_audio_mime_type(mime_type: str) -> dict:
    """
    오디오 MIME type 문자열에서 bits per sample과 rate를 파싱합니다.

    Args:
        mime_type: 오디오 MIME type 문자열 (예: "audio/L16;rate=24000")

    Returns:
        dict: "bits_per_sample"과 "rate" 키를 포함하는 딕셔너리
    """
    bits_per_sample = 16
    rate = 24000

    # Extract rate from parameters
    parts = mime_type.split(";")
    for param in parts:
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate_str = param.split("=", 1)[1]
                rate = int(rate_str)
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass

    return {"bits_per_sample": bits_per_sample, "rate": rate}


def _generate_audio_gemini(
    text: str,
    output_path: Path,
    voice: str = "Zephyr",
    model: str = "gemini-2.5-pro-preview-tts",
    speed: float = 1.0,
    max_retries: int = 8,
    initial_wait: float = 1.0,
    max_wait: float = 60.0
) -> None:
    """
    Gemini API를 호출하여 음성 파일을 생성합니다.

    지수 백오프(exponential backoff)를 적용하여 Rate Limit 에러 대응.
    생성된 오디오는 output_path에 직접 저장됩니다.

    인증 방법:
    1. GEMINI_API_KEY 환경변수 설정 (필수)

    Args:
        text: 변환할 텍스트
        output_path: 출력 파일 경로 (MP3/WAV)
        voice: Gemini voice 이름 (기본값: "Zephyr")
        model: Gemini TTS 모델명 (기본값: "gemini-2.5-pro-preview-tts")
        speed: 말하기 속도 (현재 Gemini API에서 미지원, 파라미터만 유지)
        max_retries: 최대 재시도 횟수 (기본값: 8)
        initial_wait: 초기 대기 시간 초 (기본값: 1.0)
        max_wait: 최대 대기 시간 초 (기본값: 60.0)

    Returns:
        None (파일에 직접 저장)

    Raises:
        ValueError: API 키가 설정되지 않았거나 파라미터가 유효하지 않을 경우
        Exception: API 호출 실패 시 (인증 오류 포함)
    """
    # API Key 검증
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY 환경변수가 설정되지 않았습니다.\n"
            ".env 파일에 API 키를 설정해주세요."
        )

    # 요청 정보 로깅
    text_length = len(text)
    logger.info(
        f"📝 TTS 요청 준비:\n"
        f"  - 텍스트 길이: {text_length} 글자\n"
        f"  - 모델: {model}\n"
        f"  - 음성: {voice}\n"
        f"  - 속도: {speed}x (주의: Gemini API는 speed 미지원)"
    )

    # Gemini 클라이언트 초기화
    try:
        client = genai.Client(api_key=api_key)
        logger.info("✓ Gemini API 클라이언트 초기화 완료")
    except Exception as e:
        logger.error(
            f"❌ Gemini API 인증 실패:\n"
            f"  - 오류: {e}\n"
            f"  - 해결 방법: GEMINI_API_KEY 환경변수 확인"
        )
        raise

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
        Exception,  # Gemini API의 예외를 포괄적으로 처리
        max_tries=max_retries,
        max_value=max_wait,
        on_backoff=on_backoff,
        on_giveup=on_giveup,
        jitter=backoff.full_jitter
    )
    def _call_api_with_backoff():
        """지수 백오프가 적용된 실제 API 호출 함수"""
        try:
            logger.info(f"🎤 Gemini TTS API 호출 시작...")

            # Contents 구성
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=text)]
                )
            ]

            # Config 구성
            generate_content_config = types.GenerateContentConfig(
                temperature=1,
                response_modalities=["audio"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                )
            )

            # 스트리밍 호출 및 오디오 데이터 수집
            audio_chunks = []
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue

                part = chunk.candidates[0].content.parts[0]
                if part.inline_data and part.inline_data.data:
                    inline_data = part.inline_data
                    data_buffer = inline_data.data

                    # WAV 변환이 필요한 경우
                    file_extension = mimetypes.guess_extension(inline_data.mime_type)
                    if file_extension is None:
                        file_extension = ".wav"
                        data_buffer = convert_to_wav(inline_data.data, inline_data.mime_type)

                    audio_chunks.append(data_buffer)

            # 모든 청크를 합쳐서 파일로 저장
            if not audio_chunks:
                raise Exception("API로부터 오디오 데이터를 받지 못했습니다.")

            final_audio = b"".join(audio_chunks)
            with open(output_path, "wb") as out:
                out.write(final_audio)

            logger.info(f"✅ 음성 생성 완료: {output_path}")

        except Exception as e:
            logger.error(f"🔴 Gemini API 에러: {e}")
            raise

    # 실제 API 호출 실행
    try:
        _call_api_with_backoff()
    except Exception as e:
        raise Exception(
            f"⚠️ Gemini TTS 생성 실패 ({max_retries}회 재시도)\n"
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
    voice: str = "Zephyr",
    model: str = "gemini-2.5-pro-preview-tts",
    speed: float = 1.0,
    max_retries: int = 8,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    dry_run: bool = False,
    output_name: Optional[str] = None
) -> Path:
    """
    오디오 생성 파이프라인 메인 진입점.

    스크립트 파일을 읽어 Gemini TTS API를 통해 MP3/WAV 파일로 변환합니다.
    지수 백오프(exponential backoff)를 적용하여 Rate Limit 에러 자동 대응.

    Args:
        keyword: 유물 키워드 (파일명 결정에 사용)
        script_dir: 스크립트 디렉토리 경로 (기본값: outputs/script)
        output_dir: 출력 디렉토리 경로 (기본값: outputs/audio)
        voice: Gemini TTS 음성 이름 (기본값: "Zephyr")
        model: Gemini TTS 모델명 (기본값: "gemini-2.5-pro-preview-tts")
        speed: 말하기 속도 (현재 Gemini API 미지원, 기본값: 1.0)
        max_retries: API 호출 최대 재시도 횟수 (기본값: 8)
        initial_wait: 초기 대기 시간 초 (기본값: 1.0)
        max_wait: 최대 대기 시간 초 (기본값: 60.0)
        dry_run: True일 경우 API 호출 없이 더미 파일 생성 (기본값: False)
        output_name: 파일명으로 사용할 이름 (선택적, 미제공 시 keyword 사용)

    Returns:
        Path: 생성된 MP3/WAV 파일의 절대 경로

    Raises:
        FileNotFoundError: 스크립트 파일이 존재하지 않을 경우
        ValueError: 파라미터가 유효하지 않거나 API 키가 없을 경우
        Exception: API 호출 실패 시

    Examples:
        >>> # 기본 사용법
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
    script_path = script_markdown_path(keyword, script_dir, output_name)
    output_path = audio_output_path(keyword, output_dir, output_name)

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
                model=model,
                voice=voice
            )
        except Exception as e:
            logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")
    else:
        # 실제 TTS 생성 (파일에 직접 저장됨)
        _generate_audio_gemini(
            text=script_text,
            output_path=output_path,
            voice=voice,
            model=model,
            speed=speed,
            max_retries=max_retries,
            initial_wait=initial_wait,
            max_wait=max_wait
        )

        logger.info(f"✅ 오디오 파일 저장 완료: {output_path.absolute()}")

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
        f"  - Model: {model}\n"
        f"  - Voice: {voice}\n"
        f"  - Speed: {speed}x (주의: Gemini API 미지원)"
    )

    return output_path.absolute()


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="스크립트 파일을 음성 파일(MP3/WAV)로 변환하는 오디오 생성 파이프라인 (Gemini TTS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 실행 (Zephyr voice)
  python src/pipelines/audio_gen.py --keyword "청자 상감운학문 매병"

  # 다른 voice 사용
  python src/pipelines/audio_gen.py --keyword "석굴암" --voice Puck

  # Flash 모델 사용 (빠르고 저렴)
  python src/pipelines/audio_gen.py --keyword "유물명" --model gemini-2.5-flash-preview-tts

  # Dry-run 모드
  python src/pipelines/audio_gen.py --keyword "테스트" --dry-run

지원 음성 (일부):
  Zephyr, Puck, Charon, Kore, Fenrir, Aoede, Leda 등 30+ voices

주의:
  - speed 파라미터는 현재 Gemini API에서 지원하지 않습니다.
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
        default="Zephyr",
        help="Gemini TTS 음성 이름 (기본값: Zephyr)"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-pro-preview-tts",
        choices=["gemini-2.5-pro-preview-tts", "gemini-2.5-flash-preview-tts"],
        help="Gemini TTS 모델명 (기본값: gemini-2.5-pro-preview-tts)"
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="말하기 속도 (현재 Gemini API 미지원, 기본값: 1.0)"
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

    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="파일명으로 사용할 이름 (미제공 시 keyword 사용)"
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
            dry_run=args.dry_run,
            output_name=args.output_name
        )

        print(f"\n🎵 오디오 파일이 생성되었습니다: {output_path}")

    except Exception as e:
        logger.error(f"❌ 오디오 생성 실패: {e}")
        raise


if __name__ == "__main__":
    main()
