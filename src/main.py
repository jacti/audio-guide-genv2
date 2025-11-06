"""
오디오 가이드 생성 통합 파이프라인 (Main Orchestrator)

세 단계 파이프라인을 순차적으로 실행하여 문화유산 키워드로부터 MP3 오디오 가이드를 생성합니다.

Pipeline 1: 정보 검색 (info_retrieval.py)
Pipeline 2: 스크립트 생성 (script_gen.py)
Pipeline 3: 오디오 생성 (audio_gen.py)

주요 기능:
- 세 파이프라인 통합 실행 및 에러 처리
- 진행 상황 로깅 및 사용자 피드백
- 각 단계별 결과 검증
- dry_run 모드 지원
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional
import argparse

# 파이프라인 모듈 임포트
from src.pipelines import info_retrieval, script_gen, audio_gen

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """파이프라인 실행 중 발생하는 예외"""
    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"[{stage}] {message}")


def run_full_pipeline(
    keyword: str,
    *,
    model: str = "gpt-4o-mini",
    voice: str = "alloy",
    speed: float = 1.0,
    temperature: float = 0.7,
    prompt_version: str = "v1",
    dry_run: bool = False,
    max_retries: int = 8
) -> dict:
    """
    전체 파이프라인을 순차 실행합니다.

    Args:
        keyword: 문화유산 키워드 (예: "청자 상감운학문 매병")
        model: OpenAI 모델명 (info, script 공통 사용)
        voice: TTS 음성 종류 (audio 파이프라인)
        speed: TTS 말하기 속도 (audio 파이프라인)
        temperature: LLM temperature (script 파이프라인)
        prompt_version: 스크립트 프롬프트 버전
        dry_run: True일 경우 API 호출 없이 목업 데이터 사용
        max_retries: API 재시도 횟수

    Returns:
        dict: 각 파이프라인 결과 경로를 담은 딕셔너리
            {
                "info": Path,
                "script": Path,
                "audio": Path
            }

    Raises:
        PipelineError: 파이프라인 실행 중 오류 발생 시
    """
    results = {}
    start_time = time.time()

    mode_str = "[DRY RUN] " if dry_run else ""
    logger.info(f"\n{'='*70}")
    logger.info(f"{mode_str}오디오 가이드 생성 파이프라인 시작")
    logger.info(f"키워드: {keyword}")
    logger.info(f"모델: {model} | 음성: {voice} | 속도: {speed}x")
    logger.info(f"프롬프트: {prompt_version} | Temperature: {temperature}")
    logger.info(f"{'='*70}\n")

    # Pipeline 1: 정보 검색
    try:
        logger.info(f"[1/3] 📚 정보 검색 파이프라인 시작...")
        info_path = info_retrieval.run(
            keyword=keyword,
            model=model,
            dry_run=dry_run
        )
        results["info"] = info_path
        logger.info(f"✅ [1/3] 정보 검색 완료 → {info_path}\n")

    except Exception as e:
        logger.error(f"❌ [1/3] 정보 검색 실패: {e}")
        raise PipelineError("정보 검색", str(e)) from e

    # Pipeline 2: 스크립트 생성
    try:
        logger.info(f"[2/3] 📝 스크립트 생성 파이프라인 시작...")
        script_path = script_gen.run(
            keyword=keyword,
            prompt_version=prompt_version,
            temperature=temperature,
            model=model,
            dry_run=dry_run
        )
        results["script"] = script_path
        logger.info(f"✅ [2/3] 스크립트 생성 완료 → {script_path}\n")

    except Exception as e:
        logger.error(f"❌ [2/3] 스크립트 생성 실패: {e}")
        raise PipelineError("스크립트 생성", str(e)) from e

    # Pipeline 3: 오디오 생성
    try:
        logger.info(f"[3/3] 🎤 오디오 생성 파이프라인 시작...")
        audio_path = audio_gen.run(
            keyword=keyword,
            voice=voice,
            speed=speed,
            max_retries=max_retries,
            dry_run=dry_run
        )
        results["audio"] = audio_path
        logger.info(f"✅ [3/3] 오디오 생성 완료 → {audio_path}\n")

    except Exception as e:
        logger.error(f"❌ [3/3] 오디오 생성 실패: {e}")
        raise PipelineError("오디오 생성", str(e)) from e

    # 완료 요약
    elapsed = time.time() - start_time
    logger.info(f"\n{'='*70}")
    logger.info(f"🎉 전체 파이프라인 완료! (소요 시간: {elapsed:.1f}초)")
    logger.info(f"{'='*70}")
    logger.info(f"📄 정보 파일: {results['info']}")
    logger.info(f"📝 스크립트: {results['script']}")
    logger.info(f"🎵 오디오: {results['audio']}")
    logger.info(f"{'='*70}\n")

    return results


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="오디오 가이드 생성 통합 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 실행 (실제 API 호출)
  python -m src.main --keyword "청자 상감운학문 매병"

  # Dry-run 모드 (API 호출 없이 테스트)
  python -m src.main --keyword "사유의 방" --dry-run

  # 커스텀 설정
  python -m src.main --keyword "석굴암" \\
    --model gpt-4o \\
    --voice nova \\
    --speed 1.1 \\
    --prompt-version v2

참고:
  - API 키는 .env 파일에 OPENAI_API_KEY로 설정해야 합니다.
  - dry-run 모드는 목업 데이터만 생성하므로 API 키 불필요합니다.
        """
    )

    parser.add_argument(
        "--keyword",
        type=str,
        required=True,
        help="문화유산 키워드 (예: '청자 상감운학문 매병')"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI 모델명 (기본값: gpt-4o-mini)"
    )

    parser.add_argument(
        "--voice",
        type=str,
        default="alloy",
        choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        help="TTS 음성 종류 (기본값: alloy)"
    )

    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="TTS 말하기 속도 (0.25 ~ 4.0, 기본값: 1.0)"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="스크립트 생성 temperature (0.0 ~ 1.0, 기본값: 0.7)"
    )

    parser.add_argument(
        "--prompt-version",
        type=str,
        default="v1",
        help="스크립트 프롬프트 버전 (기본값: v1)"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=8,
        help="API 재시도 횟수 (기본값: 8)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="테스트 모드 (API 호출 없이 목업 데이터 생성)"
    )

    args = parser.parse_args()

    try:
        results = run_full_pipeline(
            keyword=args.keyword,
            model=args.model,
            voice=args.voice,
            speed=args.speed,
            temperature=args.temperature,
            prompt_version=args.prompt_version,
            dry_run=args.dry_run,
            max_retries=args.max_retries
        )

        # 성공 메시지 출력
        print("\n" + "🎉 " * 20)
        print("오디오 가이드 생성이 완료되었습니다!")
        print("🎉 " * 20)
        print(f"\n📍 생성된 파일:")
        print(f"  정보: {results['info']}")
        print(f"  스크립트: {results['script']}")
        print(f"  오디오: {results['audio']}")
        print(f"\n💡 다음 단계:")
        print(f"  - 오디오 재생: open {results['audio']}")
        print(f"  - 스크립트 확인: cat {results['script']}")

        sys.exit(0)

    except PipelineError as e:
        logger.error(f"\n❌ 파이프라인 실행 실패: {e.stage} 단계에서 오류 발생")
        logger.error(f"상세 오류: {e.message}")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(130)

    except Exception as e:
        logger.error(f"\n❌ 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
