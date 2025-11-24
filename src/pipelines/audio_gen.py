"""
오디오 생성 파이프라인 (Pipeline 3)

스크립트 파일(Markdown)을 읽어 Gemini API를 통해 음성 파일(MP3/WAV)로 변환합니다.

주요 기능:
- Gemini TTS API 연동 (gemini-2.5-flash-tts 모델 사용)
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
from google.cloud import texttospeech
from dotenv import load_dotenv

from src.utils.path_sanitizer import audio_output_path
from src.utils.metadata import create_metadata

# 환경변수 로드
load_dotenv()

# 로거 설정
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 기본 설정
DEFAULT_OUTPUT_DIR = Path("outputs/audio")


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
        b"RIFF",  # ChunkID
        chunk_size,  # ChunkSize (total file size - 8 bytes)
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size (16 for PCM)
        1,  # AudioFormat (1 for PCM)
        num_channels,  # NumChannels
        sample_rate,  # SampleRate
        byte_rate,  # ByteRate
        block_align,  # BlockAlign
        bits_per_sample,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_size,  # Subchunk2Size (size of audio data)
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


def split_script_by_paragraphs(text: str, max_bytes: int = 4000) -> list[str]:
    """
    스크립트를 문단 단위로 분할하여 각 청크가 max_bytes 이하가 되도록 합니다.

    - 문단 구분: \n\n (두 줄 바꿈)
    - 문단 경계에서만 분할 (문단 중간에서 자르지 않음)
    - 각 청크는 4000 bytes 이전의 가장 큰 문단까지 포함

    Args:
        text: 분할할 전체 스크립트 텍스트
        max_bytes: 청크 최대 크기 (기본값: 4000)

    Returns:
        문단 단위로 분할된 텍스트 청크 리스트

    Raises:
        ValueError: 단일 문단이 max_bytes를 초과하는 경우
    """
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_bytes = 0

    for para in paragraphs:
        # 문단이 비어있으면 스킵
        if not para.strip():
            continue

        para_bytes = len(para.encode("utf-8"))

        # 단일 문단이 제한을 초과하는 경우
        if para_bytes > max_bytes:
            raise ValueError(
                f"단일 문단이 {max_bytes} bytes를 초과합니다 ({para_bytes} bytes).\n"
                f"스크립트를 더 짧은 문단으로 나눠주세요.\n"
                f"문단 미리보기: {para[:100]}..."
            )

        # 현재 청크에 추가 시 제한을 초과하는지 체크
        # +2는 문단 사이의 \n\n
        separator_bytes = 2 if current_chunk else 0
        if current_bytes + separator_bytes + para_bytes <= max_bytes:
            current_chunk.append(para)
            current_bytes += separator_bytes + para_bytes
        else:
            # 현재 청크 저장 (4000 bytes 이전의 가장 큰 문단까지)
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            # 새 청크 시작
            current_chunk = [para]
            current_bytes = para_bytes

    # 마지막 청크 저장
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks


def _generate_audio_gemini(
    text: str,
    output_path: Path,
    voice: str,
    tts_language: str,
    tts_system_prompt: str,
    gemini_tts_model: str,
    max_retries: int,
    initial_wait: float,
    max_wait: float,
) -> None:
    """
    Google Cloud Text-to-Speech API (Gemini TTS)를 호출하여 음성 파일을 생성합니다.

    지수 백오프(exponential backoff)를 적용하여 Rate Limit 에러 대응.
    생성된 오디오는 output_path에 직접 저장됩니다.

    인증 방법:
    1. GOOGLE_APPLICATION_CREDENTIALS 환경변수로 서비스 계정 키 파일 경로 설정
    2. 또는 gcloud CLI로 인증된 사용자 계정 사용

    Args:
        text: 변환할 텍스트
        output_path: 출력 파일 경로 (MP3/WAV)
        voice: Gemini voice 이름 (기본값: "Zephyr")
        tts_language: Gemini TTS 언어 (기본값: "ko-KR")
        tts_system_prompt: Gemini TTS 시스템 프롬프트
        gemini_tts_model: Gemini TTS 모델명 (기본값: "gemini-2.5-flash-tts")
        max_retries: 최대 재시도 횟수 (기본값: 8)
        initial_wait: 초기 대기 시간 초 (기본값: 1.0)
        max_wait: 최대 대기 시간 초 (기본값: 60.0)

    Returns:
        None (파일에 직접 저장)

    Raises:
        ValueError: 파라미터가 유효하지 않을 경우
        Exception: API 호출 실패 시 (인증 오류 포함)
    """
    # 텍스트를 청크로 분할
    text_bytes = len(text.encode("utf-8"))
    text_length = len(text)

    # 4000 bytes 초과 시 청크 분할
    if text_bytes > 4000:
        logger.info(
            f"📝 TTS 요청 준비:\n"
            f"  - 텍스트 길이: {text_length} 글자 ({text_bytes} bytes)\n"
            f"  - 4000 bytes 초과로 문단 단위 분할 시작...\n"
            f"  - 모델: {gemini_tts_model}\n"
            f"  - 음성: {voice}"
        )
        text_chunks = split_script_by_paragraphs(text, max_bytes=4000)
        logger.info(f"  - ✓ {len(text_chunks)}개 청크로 분할 완료")
    else:
        logger.info(
            f"📝 TTS 요청 준비:\n"
            f"  - 텍스트 길이: {text_length} 글자 ({text_bytes} bytes)\n"
            f"  - 모델: {gemini_tts_model}\n"
            f"  - 음성: {voice}"
        )
        text_chunks = [text]  # 단일 청크

    # Google Cloud Text-to-Speech 클라이언트 초기화
    try:
        client = texttospeech.TextToSpeechClient()
        logger.info("✓ Google Cloud Text-to-Speech API 클라이언트 초기화 완료")
    except Exception as e:
        logger.error(
            f"❌ Google Cloud Text-to-Speech API 인증 실패:\n"
            f"  - 오류: {e}\n"
            f"  - 해결 방법: GOOGLE_APPLICATION_CREDENTIALS 환경변수 확인 또는 gcloud auth login 실행"
        )
        raise

    # 백오프 핸들러: 재시도 시 로깅
    def on_backoff(details):
        wait_time = details["wait"]
        tries = details["tries"]
        logger.warning(
            f"⏳ 지수 백오프 적용: {wait_time:.2f}초 대기 중 "
            f"(재시도 {tries}/{max_retries})"
        )

    # 포기 시 핸들러: 최종 실패 로깅
    def on_giveup(details):
        logger.error(f"❌ 최대 재시도 횟수 초과 ({max_retries}회): API 호출 포기")

    # 지수 백오프를 적용한 단일 청크 API 호출 함수
    @backoff.on_exception(
        backoff.expo,
        Exception,  # Google Cloud API의 예외를 포괄적으로 처리
        max_tries=max_retries,
        max_value=max_wait,
        on_backoff=on_backoff,
        on_giveup=on_giveup,
        jitter=backoff.full_jitter,
    )
    def _call_api_for_chunk(chunk_text: str) -> bytes:
        """단일 청크에 대해 지수 백오프가 적용된 API 호출"""
        # 입력 텍스트 설정
        synthesis_input = texttospeech.SynthesisInput(
            text=chunk_text, prompt=tts_system_prompt
        )

        # 음성 설정
        voice_params = texttospeech.VoiceSelectionParams(
            # language_code="en-US",  # Gemini TTS voices는 주로 en-US
            language_code=tts_language,  # Gemini TTS voices는 주로 en-US
            name=voice,
            model_name=gemini_tts_model,
        )

        # 오디오 설정
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )

        # API 호출
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice_params, audio_config=audio_config
        )

        return response.audio_content

    # 모든 청크 처리 및 오디오 결합
    try:
        audio_chunks = []
        total_chunks = len(text_chunks)

        for i, chunk in enumerate(text_chunks, 1):
            chunk_bytes = len(chunk.encode("utf-8"))
            logger.info(
                f"🎤 청크 {i}/{total_chunks} 생성 중... ({len(chunk)} 글자, {chunk_bytes} bytes)"
            )

            audio_data = _call_api_for_chunk(chunk)
            audio_chunks.append(audio_data)

            logger.info(f"✅ 청크 {i}/{total_chunks} 완료")

        # 모든 오디오 청크 결합
        if len(audio_chunks) > 1:
            logger.info(f"🔗 {len(audio_chunks)}개 오디오 청크 결합 중...")

        combined_audio = b"".join(audio_chunks)

        # 최종 파일 저장
        with open(output_path, "wb") as out:
            out.write(combined_audio)

        if len(audio_chunks) > 1:
            logger.info(f"✅ 오디오 결합 완료")
        logger.info(f"✅ 음성 생성 완료: {output_path}")

    except Exception as e:
        logger.error(f"🔴 Gemini API 에러: {e}")
        raise Exception(
            f"⚠️ Gemini TTS 생성 실패 ({max_retries}회 재시도)\n" f"상세 정보: {e}"
        ) from e


def run(
    output_name: str,
    tts_language: str,
    tts_system_prompt: str,
    script_gen_result_file_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    voice: str = "Zephyr",
    gemini_tts_model: str = "gemini-2.5-pro-tts",
    max_retries: int = 8,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
) -> Path:
    """
    오디오 생성 파이프라인 메인 진입점.

    스크립트 파일을 읽어 Gemini TTS API를 통해 MP3/WAV 파일로 변환합니다.
    지수 백오프(exponential backoff)를 적용하여 Rate Limit 에러 자동 대응.

    Args:
        output_name: 파일명 (식별자로 사용됨)
        tts_language: Gemini TTS 언어
        tts_system_prompt: Gemini TTS 시스템 프롬프트
        script_gen_result_file_path: 스크립트 생성 결과 파일 경로 (필수)
        output_dir: 출력 디렉토리 경로 (기본값: outputs/audio)
        voice: Gemini TTS 음성 이름 (기본값: "Zephyr")
        gemini_tts_model: Gemini TTS 모델명 (기본값: "gemini-2.5-pro-tts")
        max_retries: API 호출 최대 재시도 횟수 (기본값: 8)
        initial_wait: 초기 대기 시간 초 (기본값: 1.0)
        max_wait: 최대 대기 시간 초 (기본값: 60.0)

    Returns:
        Path: 생성된 MP3/WAV 파일의 절대 경로

    Raises:
        FileNotFoundError: 스크립트 파일이 존재하지 않을 경우
        ValueError: 파라미터가 유효하지 않거나 API 키가 없을 경우
        Exception: API 호출 실패 시

    Examples:
        >>> # 기본 사용법
        >>> output_path = run("01_celadon", tts_language="ko-KR", tts_system_prompt="...")
    """
    logger.info(f"=== 오디오 생성 파이프라인 시작: '{output_name}' ===")

    # 기본 경로 설정
    if script_gen_result_file_path is None:
        raise ValueError("script_gen_result_file_path는 필수입니다.")
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    # 출력 디렉토리 생성
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"출력 디렉토리: {output_dir.absolute()}")

    # 입력 파일 경로 결정
    script_path = script_gen_result_file_path

    # 출력 파일 경로 결정
    output_path = audio_output_path(output_name, output_dir)

    # 스크립트 파일 읽기
    script_gen_result_content_text = _read_script(script_path)

    # 실제 TTS 생성 (파일에 직접 저장됨)
    _generate_audio_gemini(
        text=script_gen_result_content_text,
        output_path=output_path,
        voice=voice,
        tts_language=tts_language,
        tts_system_prompt=tts_system_prompt,
        gemini_tts_model=gemini_tts_model,
        max_retries=max_retries,
        initial_wait=initial_wait,
        max_wait=max_wait,
    )

    logger.info(f"✅ 오디오 파일 저장 완료: {output_path.absolute()}")

    # 메타데이터 생성 (production)
    try:
        create_metadata(
            output_name=output_name,
            pipeline="audio_gen",
            output_file_path=output_path,
            mode="production",
            model=gemini_tts_model,
            voice=voice,
        )
    except Exception as e:
        logger.warning(f"메타데이터 저장 실패 (파이프라인은 계속 진행): {e}")

    logger.info(
        f"=== 오디오 생성 파이프라인 완료 ===\n"
        f"  - 입력 스크립트: {script_path}\n"
        f"  - 출력 파일: {output_path.absolute()}\n"
        f"  - Model: {gemini_tts_model}\n"
        f"  - Voice: {voice}"
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
  python src/pipelines/audio_gen.py --output-name "01_celadon"

  # 다른 voice 사용
  python src/pipelines/audio_gen.py --output-name "02_seokguram" --voice Puck

  # Flash 모델 사용 (빠르고 저렴)
  python src/pipelines/audio_gen.py --output-name "03_buddha" --gemini-tts-model gemini-2.5-flash-preview-tts

  # 지원 음성 (일부):
  Zephyr, Puck, Charon, Kore, Fenrir, Aoede, Leda 등 30+ voices
        """,
    )

    parser.add_argument(
        "--output-name",
        type=str,
        required=True,
        help="식별자 (파일명)",
    )

    parser.add_argument(
        "--script-file",
        type=Path,
        required=True,
        help="스크립트 파일 경로 (필수)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="출력 디렉토리 경로 (기본값: outputs/audio)",
    )

    parser.add_argument(
        "--voice",
        type=str,
        default="Zephyr",
        help="Gemini TTS 음성 이름 (기본값: Zephyr)",
    )

    parser.add_argument(
        "--gemini-tts-model",
        type=str,
        default="gemini-2.5-flash-tts",
        choices=["gemini-2.5-flash-tts", "gemini-2.5-pro-tts"],
        help="Gemini TTS 모델명 (기본값: gemini-2.5-flash-tts)",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=8,
        help="API 호출 최대 재시도 횟수 (기본값: 8, 지수 백오프 적용)",
    )

    parser.add_argument(
        "--initial-wait",
        type=float,
        default=1.0,
        help="초기 대기 시간 초 (기본값: 1.0, 지수 백오프 시작 값)",
    )

    parser.add_argument(
        "--max-wait",
        type=float,
        default=60.0,
        help="최대 대기 시간 초 (기본값: 60.0, 지수 백오프 상한)",
    )

    parser.add_argument(
        "--tts-language",
        type=str,
        default="ko-KR",
        help="Gemini TTS 언어 (기본값: ko-KR)",
    )

    parser.add_argument(
        "--tts-system-prompt",
        type=str,
        default="당신은 박물관/미술관 도슨트입니다. 차분하지만 지루하지 않게, 약간 명랑하고 따뜻한 톤으로, 실제 전시장에서 관람객에게 설명하듯 자연스럽게 말해주세요.",
        help="Gemini TTS 프롬프트",
    )

    args = parser.parse_args()

    try:
        output_path = run(
            output_name=args.output_name,
            tts_language=args.tts_language,
            tts_system_prompt=args.tts_system_prompt,
            script_gen_result_file_path=args.script_file,
            output_dir=args.output_dir,
            voice=args.voice,
            gemini_tts_model=args.gemini_tts_model,
            max_retries=args.max_retries,
            initial_wait=args.initial_wait,
            max_wait=args.max_wait,
        )

        print(f"\n🎵 오디오 파일이 생성되었습니다: {output_path}")

    except Exception as e:
        logger.error(f"❌ 오디오 생성 실패: {e}")
        raise


if __name__ == "__main__":
    main()
