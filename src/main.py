"""
오디오 가이드 생성 통합 파이프라인 (Main Orchestrator)

- 입력: output_name, info_retrieval_user_content_text, optional script_gen_user_content_text
- 프롬프트: prompts/info_retrieval/universal_retrieval.yaml, prompts/script_generation/unniversal_script_gen.yaml
- 모델/음성: CLI 인자 또는 기본값 사용
"""

import argparse
import logging
import time
from pathlib import Path
from typing import Optional, List

from src.pipelines import info_retrieval, script_gen, audio_gen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """파이프라인 실행 중 발생하는 예외"""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"[{stage}] {message}")


def run_full_pipeline(
    output_name: str,
    info_retrieval_user_content_text: str,
    *,
    perplexity_model: str = "sonar-pro",
    info_retrieval_prompt_template_name: str = "universal_retrieval",
    script_gen_prompt_template_name: str = "unniversal_script_gen",
    script_gen_model: str = "gpt-4o",
    script_gen_user_content_text: Optional[str] = None,
    voice: str = "Zephyr",
    gemini_tts_model: str = "gemini-2.5-pro-tts",
    tts_language: str = "ko-KR",
    tts_system_prompt: str = "당신은 박물관/미술관 도슨트입니다. 차분하지만 지루하지 않게, 약간 명랑하고 따뜻한 톤으로, 실제 전시장에서 관람객에게 설명하듯 자연스럽게 말해주세요.",
    temperature: float = 0.7,
    max_retries: int = 8,
    stages: List[int] = (1, 2, 3),
) -> dict:
    """
    전체 파이프라인을 순차 실행합니다.

    Args:
        output_name: 결과 식별자 (파일명)
        info_retrieval_user_content_text: 정보 검색 요구사항 텍스트
        perplexity_model: Perplexity 모델 (정보 검색)
        info_retrieval_prompt_template_name: prompts/info_retrieval YAML 이름
        script_gen_prompt_template_name: prompts/script_generation YAML 이름
        script_gen_model: 스크립트 생성 모델 (gpt-* or gemini-*)
        script_gen_user_content_text: 스크립트 생성용 사용자 지시사항
        voice: Gemini TTS 음성 이름
        gemini_tts_model: Gemini TTS 모델명
        tts_language: TTS 언어 코드
        tts_system_prompt: TTS 시스템 프롬프트
        temperature: LLM temperature (스크립트 생성)
        max_retries: TTS 재시도 횟수
        stages: 실행할 파이프라인 단계
    """
    results = {}
    start_time = time.time()

    logger.info(f"\n{'='*70}")
    logger.info("오디오 가이드 생성 파이프라인 시작")
    logger.info(f"출력 이름: {output_name}")
    logger.info(
        "정보 모델: %s | 스크립트 모델: %s | TTS: %s | Voice: %s",
        perplexity_model,
        script_gen_model,
        gemini_tts_model,
        voice,
    )
    logger.info(
        "프롬프트(info/script): %s / %s",
        info_retrieval_prompt_template_name,
        script_gen_prompt_template_name,
    )
    logger.info(f"Temperature: {temperature}")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}\n")

    info_path: Optional[Path] = None
    script_path: Optional[Path] = None

    # Pipeline 1: 정보 검색
    if 1 in stages:
        try:
            logger.info("[1/3] 📚 정보 검색 파이프라인 시작...")
            info_path = info_retrieval.run(
                output_name=output_name,
                perplexity_model=perplexity_model,
                info_retrieval_prompt_template_name=info_retrieval_prompt_template_name,
                info_retrieval_user_content_text=info_retrieval_user_content_text,
            )
            results["info"] = info_path
            logger.info(f"✅ [1/3] 정보 검색 완료 → {info_path}\n")
        except Exception as e:
            logger.error(f"❌ [1/3] 정보 검색 실패: {e}")
            raise PipelineError("정보 검색", str(e)) from e
    else:
        logger.info("⊘ [1/3] 정보 검색 건너뜀 (이미 존재하는 파일 사용)\n")

    # Pipeline 2: 스크립트 생성
    if 2 in stages:
        try:
            logger.info("[2/3] 📝 스크립트 생성 파이프라인 시작...")
            script_path = script_gen.run(
                output_name=output_name,
                script_gen_prompt_template_name=script_gen_prompt_template_name,
                script_gen_model=script_gen_model,
                info_retrieval_result_file_path=info_path,
                script_gen_user_content_text=script_gen_user_content_text,
                temperature=temperature,
            )
            results["script"] = script_path
            logger.info(f"✅ [2/3] 스크립트 생성 완료 → {script_path}\n")
        except Exception as e:
            logger.error(f"❌ [2/3] 스크립트 생성 실패: {e}")
            raise PipelineError("스크립트 생성", str(e)) from e
    else:
        logger.info("⊘ [2/3] 스크립트 생성 건너뜀 (이미 존재하는 파일 사용)\n")

    # Pipeline 3: 오디오 생성
    if 3 in stages:
        try:
            logger.info("[3/3] 🎤 오디오 생성 파이프라인 시작...")
            audio_path = audio_gen.run(
                output_name=output_name,
                script_gen_result_file_path=script_path,
                voice=voice,
                tts_language=tts_language,
                tts_system_prompt=tts_system_prompt,
                gemini_tts_model=gemini_tts_model,
                max_retries=max_retries,
            )
            results["audio"] = audio_path
            logger.info(f"✅ [3/3] 오디오 생성 완료 → {audio_path}\n")
        except Exception as e:
            logger.error(f"❌ [3/3] 오디오 생성 실패: {e}")
            raise PipelineError("오디오 생성", str(e)) from e
    else:
        logger.info("⊘ [3/3] 오디오 생성 건너뜀 (이미 존재하는 파일 사용)\n")

    elapsed = time.time() - start_time
    logger.info(f"\n{'='*70}")
    logger.info(f"🎉 파이프라인 완료! (소요 시간: {elapsed:.1f}초)")
    logger.info(f"{'='*70}")
    if "info" in results:
        logger.info(f"📄 정보 파일: {results['info']}")
    if "script" in results:
        logger.info(f"📝 스크립트: {results['script']}")
    if "audio" in results:
        logger.info(f"🎵 오디오: {results['audio']}")
    logger.info(f"{'='*70}\n")

    return results


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="오디오 가이드 생성 통합 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m src.main \\
    --output-name "01_celadon" \\
    --info-user-text "신라 금관을 조사해줘" \\
    --script-user-text "따뜻하고 이야기처럼"
        """,
    )

    parser.add_argument(
        "--output-name",
        required=True,
        type=str,
        help="결과 식별자 (파일명)",
    )
    parser.add_argument(
        "--info-user-text",
        required=True,
        type=str,
        help="정보 검색 요구사항 텍스트",
    )
    parser.add_argument(
        "--script-user-text",
        type=str,
        default=None,
        help="스크립트 생성 사용자 지시사항 (선택)",
    )
    parser.add_argument(
        "--perplexity-model",
        type=str,
        default="sonar-pro",
        help="Perplexity 모델 (기본: sonar-pro)",
    )
    parser.add_argument(
        "--info-prompt",
        type=str,
        default="universal_retrieval",
        help="info 프롬프트 YAML 이름",
    )
    parser.add_argument(
        "--script-prompt",
        type=str,
        default="unniversal_script_gen",
        help="script 프롬프트 YAML 이름",
    )
    parser.add_argument(
        "--script-model",
        type=str,
        default="gpt-4o",
        help="스크립트 생성 모델명 (gpt-* 또는 gemini-*)",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="Zephyr",
        help="Gemini TTS 음성 이름",
    )
    parser.add_argument(
        "--gemini-tts-model",
        type=str,
        default="gemini-2.5-pro-tts",
        help="Gemini TTS 모델명",
    )
    parser.add_argument(
        "--tts-language",
        type=str,
        default="ko-KR",
        help="TTS 언어 코드",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="LLM temperature (스크립트 생성)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=8,
        help="TTS 재시도 횟수",
    )
    parser.add_argument(
        "--stages",
        type=str,
        default="1,2,3",
        help="실행할 파이프라인 단계 (예: 1,2,3 또는 2,3)",
    )

    args = parser.parse_args()
    try:
        stages = sorted({int(s) for s in args.stages.split(",") if s.strip()})
    except Exception:
        raise ValueError("stages는 예: 1,2,3 형태로 입력하세요.")

    run_full_pipeline(
        output_name=args.output_name,
        info_retrieval_user_content_text=args.info_user_text,
        perplexity_model=args.perplexity_model,
        info_retrieval_prompt_template_name=args.info_prompt,
        script_gen_prompt_template_name=args.script_prompt,
        script_gen_model=args.script_model,
        script_gen_user_content_text=args.script_user_text,
        voice=args.voice,
        gemini_tts_model=args.gemini_tts_model,
        tts_language=args.tts_language,
        temperature=args.temperature,
        max_retries=args.max_retries,
        stages=stages,
    )


if __name__ == "__main__":
    main()
