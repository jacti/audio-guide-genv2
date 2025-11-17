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
    search_keyword: str,
    *,
    model: str = "gpt-4.1",
    voice: str = "Zephyr",
    tts_model: str = "gemini-2.5-pro-preview-tts",
    temperature: float = 0.7,
    script_prompt_version: str = "v2-tts",
    info_prompt_version: str = "default",
    dry_run: bool = False,
    max_retries: int = 8,
    output_name: Optional[str] = None,
    stages: list = [1, 2, 3]
) -> dict:
    """
    전체 파이프라인을 순차 실행합니다.

    Args:
        search_keyword: 문화유산 검색 키워드 (예: "청자 상감운학문 매병")
        model: OpenAI 모델명 (info, script 파이프라인에 사용)
        voice: Gemini TTS 음성 이름 (audio 파이프라인, 예: Zephyr)
        tts_model: Gemini TTS 모델명 (audio 파이프라인)
        temperature: LLM temperature (script 파이프라인)
        script_prompt_version: 스크립트 생성 프롬프트 버전
        info_prompt_version: 정보 검색 프롬프트 버전
        dry_run: True일 경우 API 호출 없이 목업 데이터 사용
        max_retries: API 재시도 횟수
        output_name: 파일명으로 사용할 이름 (선택적, 미제공 시 search_keyword 사용)
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])

    Returns:
        dict: 각 파이프라인 결과 경로를 담은 딕셔너리
            {
                "info": Path (실행된 경우),
                "script": Path (실행된 경우),
                "audio": Path (실행된 경우)
            }

    Raises:
        PipelineError: 파이프라인 실행 중 오류 발생 시
    """
    results = {}
    start_time = time.time()

    mode_str = "[DRY RUN] " if dry_run else ""
    logger.info(f"\n{'='*70}")
    logger.info(f"{mode_str}오디오 가이드 생성 파이프라인 시작")
    logger.info(f"검색 키워드: {search_keyword}")
    logger.info(f"모델: {model} | 음성: {voice}")
    logger.info(f"정보 프롬프트: {info_prompt_version} | 스크립트 프롬프트: {script_prompt_version}")
    logger.info(f"Temperature: {temperature}")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}\n")

    # Pipeline 1: 정보 검색
    if 1 in stages:
        try:
            logger.info(f"[1/3] 📚 정보 검색 파이프라인 시작...")
            info_path = info_retrieval.run(
                search_keyword=search_keyword,
                model=model,
                prompt_version=info_prompt_version,
                dry_run=dry_run,
                output_name=output_name
            )
            results["info"] = info_path
            logger.info(f"✅ [1/3] 정보 검색 완료 → {info_path}\n")

        except Exception as e:
            logger.error(f"❌ [1/3] 정보 검색 실패: {e}")
            raise PipelineError("정보 검색", str(e)) from e
    else:
        logger.info(f"⊘ [1/3] 정보 검색 건너뜀 (이미 존재하는 파일 사용)\n")

    # Pipeline 2: 스크립트 생성
    if 2 in stages:
        try:
            logger.info(f"[2/3] 📝 스크립트 생성 파이프라인 시작...")
            script_path = script_gen.run(
                search_keyword=search_keyword,
                script_prompt_version=script_prompt_version,
                temperature=temperature,
                model=model,
                dry_run=dry_run,
                output_name=output_name
            )
            results["script"] = script_path
            logger.info(f"✅ [2/3] 스크립트 생성 완료 → {script_path}\n")

        except Exception as e:
            logger.error(f"❌ [2/3] 스크립트 생성 실패: {e}")
            raise PipelineError("스크립트 생성", str(e)) from e
    else:
        logger.info(f"⊘ [2/3] 스크립트 생성 건너뜀 (이미 존재하는 파일 사용)\n")

    # Pipeline 3: 오디오 생성
    if 3 in stages:
        try:
            logger.info(f"[3/3] 🎤 오디오 생성 파이프라인 시작...")
            audio_path = audio_gen.run(
                search_keyword=search_keyword,
                voice=voice,
                model=tts_model,
                max_retries=max_retries,
                dry_run=dry_run,
                output_name=output_name
            )
            results["audio"] = audio_path
            logger.info(f"✅ [3/3] 오디오 생성 완료 → {audio_path}\n")

        except Exception as e:
            logger.error(f"❌ [3/3] 오디오 생성 실패: {e}")
            raise PipelineError("오디오 생성", str(e)) from e
    else:
        logger.info(f"⊘ [3/3] 오디오 생성 건너뜀 (이미 존재하는 파일 사용)\n")

    # 완료 요약
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
사용 예시:
  # 기본 실행 (실제 API 호출)
  python -m src.main --search-keyword "청자 상감운학문 매병"

  # Dry-run 모드 (API 호출 없이 테스트)
  python -m src.main --search-keyword "사유의 방" --dry-run

  # 커스텀 설정
  python -m src.main --search-keyword "석굴암" \\
    --model gpt-4o \\
    --voice Puck \\
    --tts-model gemini-2.5-flash-preview-tts \\
    --script-prompt-version v2 \\
    --info-prompt-version detailed

  # 다른 voice 사용
  python -m src.main --search-keyword "유물명" \\
    --voice Charon

참고:
  - OPENAI_API_KEY: info/script 파이프라인용 (.env 파일)
  - GEMINI_API_KEY: audio 파이프라인용 (Gemini TTS, .env 파일)
  - dry-run 모드는 목업 데이터만 생성하므로 API 키 불필요합니다.
        """
    )

    parser.add_argument(
        "--search-keyword",
        type=str,
        required=True,
        help="문화유산 검색 키워드 (예: '청자 상감운학문 매병')"
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4.1",
        help="OpenAI 모델명 (기본값: gpt-4.1)"
    )

    parser.add_argument(
        "--voice",
        type=str,
        default="Zephyr",
        help="Gemini TTS 음성 이름 (기본값: Zephyr, 예: Puck, Charon, Kore)"
    )

    parser.add_argument(
        "--tts-model",
        type=str,
        default="gemini-2.5-pro-preview-tts",
        choices=["gemini-2.5-pro-preview-tts", "gemini-2.5-flash-preview-tts"],
        help="Gemini TTS 모델명 (기본값: gemini-2.5-pro-preview-tts)"
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="스크립트 생성 temperature (0.0 ~ 1.0, 기본값: 0.7)"
    )

    parser.add_argument(
        "--script-prompt-version",
        type=str,
        default="v2-tts",
        help="스크립트 생성 프롬프트 버전 (기본값: v2-tts)"
    )

    parser.add_argument(
        "--info-prompt-version",
        type=str,
        default="default",
        help="정보 검색 프롬프트 버전 (기본값: default)"
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

    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="파일명으로 사용할 이름 (미제공 시 keyword 사용)"
    )

    parser.add_argument(
        "--stages",
        type=str,
        default="1,2,3",
        help="실행할 파이프라인 단계 (기본값: 1,2,3). 예: '2' 또는 '2,3'"
    )

    args = parser.parse_args()

    # stages 파싱
    try:
        stages = [int(s.strip()) for s in args.stages.split(",")]
        for stage in stages:
            if stage not in [1, 2, 3]:
                logger.error(f"유효하지 않은 stage 번호: {stage}. 1, 2, 3 중 하나여야 합니다.")
                sys.exit(1)
        stages = sorted(set(stages))  # 정렬 및 중복 제거
    except ValueError:
        logger.error(f"잘못된 --stages 형식: {args.stages}. 예: '1,2,3' 또는 '2'")
        sys.exit(1)

    try:
        results = run_full_pipeline(
            search_keyword=args.search_keyword,
            model=args.model,
            voice=args.voice,
            tts_model=args.tts_model,
            temperature=args.temperature,
            script_prompt_version=args.script_prompt_version,
            info_prompt_version=args.info_prompt_version,
            dry_run=args.dry_run,
            max_retries=args.max_retries,
            output_name=args.output_name,
            stages=stages
        )

        # 성공 메시지 출력
        print("\n" + "🎉 " * 20)
        print("파이프라인 실행이 완료되었습니다!")
        print("🎉 " * 20)
        print(f"\n📍 생성된 파일:")
        if "info" in results:
            print(f"  정보: {results['info']}")
        if "script" in results:
            print(f"  스크립트: {results['script']}")
        if "audio" in results:
            print(f"  오디오: {results['audio']}")

        print(f"\n💡 다음 단계:")
        if "audio" in results:
            print(f"  - 오디오 재생: open {results['audio']}")
        if "script" in results:
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
