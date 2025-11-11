"""
트랙 기반 배치 오디오 가이드 생성 스크립트

YAML 설정 파일을 읽어 여러 개의 오디오 가이드를 일괄 생성합니다.
트랙별로 계층적 디렉토리 구조를 유지하며, 실행 결과 리포트를 자동 생성합니다.

주요 기능:
- YAML 기반 트랙 설정 파싱
- 순차적 파이프라인 실행 (info → script → audio)
- 실시간 진행률 표시
- 트랙별 출력 디렉토리 구조 생성
- 실행 결과 JSON 리포트 생성
- 에러 발생 시 즉시 중단 및 상세 로그
"""

import sys
import json
import logging
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

# YAML 파서
try:
    import yaml
except ImportError:
    print("❌ PyYAML이 설치되지 않았습니다. requirements.txt를 확인해주세요.")
    sys.exit(1)

# 파이프라인 모듈 임포트
from src.pipelines import info_retrieval, script_gen, audio_gen
from src.utils.path_sanitizer import sanitize_keyword_for_path

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class BatchRunnerError(Exception):
    """배치 실행 중 발생하는 예외"""
    def __init__(self, message: str, file_name: Optional[str] = None, stage: Optional[str] = None):
        self.message = message
        self.file_name = file_name
        self.stage = stage
        if file_name and stage:
            super().__init__(f"[{file_name} - {stage}] {message}")
        elif file_name:
            super().__init__(f"[{file_name}] {message}")
        else:
            super().__init__(message)


def load_track_config(yaml_path: Path) -> Dict[str, Any]:
    """
    YAML 트랙 설정 파일을 로드합니다.

    Args:
        yaml_path: YAML 파일 경로

    Returns:
        파싱된 설정 딕셔너리

    Raises:
        FileNotFoundError: YAML 파일을 찾을 수 없을 때
        yaml.YAMLError: YAML 파싱 오류
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"트랙 설정 파일을 찾을 수 없습니다: {yaml_path}")

    logger.info(f"트랙 설정 파일 로드: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"YAML 파싱 오류: {e}")

    return config


def validate_track_config(config: Dict[str, Any]) -> bool:
    """
    트랙 설정 파일의 유효성을 검증합니다.

    Args:
        config: 트랙 설정 딕셔너리

    Returns:
        검증 성공 여부

    Raises:
        BatchRunnerError: 필수 필드 누락 또는 잘못된 설정
    """
    # 필수 필드 확인
    if "track_name" not in config:
        raise BatchRunnerError("필수 필드 누락: track_name")

    if "files" not in config or not isinstance(config["files"], list):
        raise BatchRunnerError("필수 필드 누락 또는 형식 오류: files (리스트여야 함)")

    if len(config["files"]) == 0:
        raise BatchRunnerError("files 리스트가 비어있습니다. 최소 1개 이상의 파일이 필요합니다.")

    # 각 파일 항목 검증
    for idx, file_item in enumerate(config["files"]):
        if not isinstance(file_item, dict):
            raise BatchRunnerError(f"files[{idx}]: 딕셔너리 형식이어야 합니다.")

        if "output_name" not in file_item:
            raise BatchRunnerError(f"files[{idx}]: 필수 필드 누락 - output_name")

        if "keyword" not in file_item:
            raise BatchRunnerError(f"files[{idx}]: 필수 필드 누락 - keyword")

    logger.info(f"✅ 설정 파일 검증 완료: {len(config['files'])}개 파일")
    return True


def create_track_directories(track_name: str, base_dir: Path = Path("outputs/tracks")) -> Dict[str, Path]:
    """
    트랙별 출력 디렉토리 구조를 생성합니다.

    Args:
        track_name: 트랙 이름
        base_dir: 기본 출력 디렉토리

    Returns:
        생성된 디렉토리 경로 딕셔너리
        {
            "track_root": Path,
            "info": Path,
            "script": Path,
            "audio": Path
        }
    """
    # 트랙 이름을 파일시스템 안전한 형태로 변환
    safe_track_name = sanitize_keyword_for_path(track_name)
    track_root = base_dir / safe_track_name

    # 디렉토리 생성
    dirs = {
        "track_root": track_root,
        "info": track_root / "info",
        "script": track_root / "script",
        "audio": track_root / "audio"
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"📁 트랙 디렉토리 생성 완료: {track_root}")

    return dirs


def merge_file_config(file_config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    개별 파일 설정과 기본 설정을 병합합니다.

    Args:
        file_config: 개별 파일 설정
        defaults: 기본 설정

    Returns:
        병합된 설정 (개별 설정이 우선)
    """
    merged = defaults.copy()
    merged.update(file_config)
    return merged


def run_single_file(
    file_config: Dict[str, Any],
    track_dirs: Dict[str, Path],
    file_index: int,
    total_files: int
) -> Dict[str, Any]:
    """
    단일 파일에 대해 전체 파이프라인을 실행합니다.

    Args:
        file_config: 파일 설정 (defaults와 병합된 상태)
        track_dirs: 트랙 디렉토리 경로 딕셔너리
        file_index: 현재 파일 인덱스 (1부터 시작)
        total_files: 전체 파일 개수

    Returns:
        실행 결과 딕셔너리
        {
            "output_name": str,
            "keyword": str,
            "status": "success" | "failed",
            "error": str (실패 시),
            "audio_path": str,
            "started_at": str,
            "completed_at": str
        }

    Raises:
        BatchRunnerError: 파이프라인 실행 실패
    """
    output_name = file_config["output_name"]
    keyword = file_config["keyword"]
    dry_run = file_config.get("dry_run", False)

    result = {
        "output_name": output_name,
        "keyword": keyword,
        "started_at": datetime.now().isoformat(),
        "status": "pending"
    }

    logger.info(f"\n{'='*70}")
    logger.info(f"[{file_index}/{total_files}] {output_name}")
    logger.info(f"키워드: {keyword}")
    logger.info(f"{'='*70}")

    try:
        # Pipeline 1: 정보 검색
        logger.info("  → 정보 검색 중...")
        info_path = info_retrieval.run(
            keyword=keyword,
            model=file_config.get("model", "gpt-4.1"),
            output_dir=track_dirs["info"],
            dry_run=dry_run,
            output_name=output_name
        )
        logger.info(f"  ✓ 정보 검색 완료: {info_path.name}")

        # Pipeline 2: 스크립트 생성
        logger.info("  → 스크립트 생성 중...")
        script_path = script_gen.run(
            keyword=keyword,
            info_dir=track_dirs["info"],
            output_dir=track_dirs["script"],
            prompt_version=file_config.get("prompt_version", "v2-tts"),
            temperature=file_config.get("temperature", 0.7),
            model=file_config.get("model", "gpt-4.1"),
            dry_run=dry_run,
            output_name=output_name
        )
        logger.info(f"  ✓ 스크립트 생성 완료: {script_path.name}")

        # Pipeline 3: 오디오 생성
        logger.info("  → 오디오 생성 중...")
        audio_path = audio_gen.run(
            keyword=keyword,
            script_dir=track_dirs["script"],
            output_dir=track_dirs["audio"],
            voice=file_config.get("voice", "Zephyr"),
            model=file_config.get("tts_model", "gemini-2.5-pro-preview-tts"),
            speed=file_config.get("speed", 1.0),
            max_retries=file_config.get("max_retries", 8),
            dry_run=dry_run,
            output_name=output_name
        )
        logger.info(f"  ✓ 오디오 생성 완료: {audio_path.name}")

        result["status"] = "success"
        result["audio_path"] = str(audio_path)
        result["completed_at"] = datetime.now().isoformat()

        logger.info(f"✅ [{file_index}/{total_files}] {output_name} 완료\n")

        return result

    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ [{file_index}/{total_files}] {output_name} 실패: {error_msg}")

        result["status"] = "failed"
        result["error"] = error_msg
        result["completed_at"] = datetime.now().isoformat()

        raise BatchRunnerError(
            message=error_msg,
            file_name=output_name,
            stage="파이프라인 실행"
        ) from e


def generate_batch_report(
    track_config: Dict[str, Any],
    results: List[Dict[str, Any]],
    track_dirs: Dict[str, Path],
    started_at: str,
    completed_at: str,
    duration: float
) -> Path:
    """
    배치 실행 결과 리포트를 JSON 파일로 생성합니다.

    Args:
        track_config: 트랙 설정
        results: 각 파일 실행 결과 리스트
        track_dirs: 트랙 디렉토리 경로
        started_at: 시작 시각 (ISO format)
        completed_at: 완료 시각 (ISO format)
        duration: 소요 시간 (초)

    Returns:
        생성된 리포트 파일 경로
    """
    report = {
        "track_name": track_config["track_name"],
        "description": track_config.get("description", ""),
        "metadata": track_config.get("metadata", {}),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 2),
        "total_files": len(results),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "files": results
    }

    report_path = track_dirs["track_root"] / "batch_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 결과 리포트 생성: {report_path}")

    return report_path


def run_batch(
    track_config: Dict[str, Any],
    override_dry_run: Optional[bool] = None
) -> Dict[str, Any]:
    """
    트랙 전체를 배치 실행합니다.

    Args:
        track_config: 트랙 설정 딕셔너리
        override_dry_run: dry_run 모드 강제 설정 (None이면 설정 파일 따름)

    Returns:
        실행 결과 요약 딕셔너리

    Raises:
        BatchRunnerError: 실행 중 오류 발생
    """
    track_name = track_config["track_name"]
    files = track_config["files"]
    defaults = track_config.get("defaults", {})

    # dry_run 오버라이드 처리
    if override_dry_run is not None:
        defaults["dry_run"] = override_dry_run

    total_files = len(files)

    logger.info(f"\n{'='*70}")
    logger.info(f"🎬 배치 실행 시작: {track_name}")
    logger.info(f"총 {total_files}개 파일")
    logger.info(f"{'='*70}\n")

    # 트랙 디렉토리 생성
    track_dirs = create_track_directories(track_name)

    # 실행 시작
    started_at = datetime.now().isoformat()
    start_time = time.time()
    results = []

    try:
        for idx, file_item in enumerate(files, start=1):
            # defaults와 개별 설정 병합
            file_config = merge_file_config(file_item, defaults)

            # 파이프라인 실행
            result = run_single_file(
                file_config=file_config,
                track_dirs=track_dirs,
                file_index=idx,
                total_files=total_files
            )
            results.append(result)

    except BatchRunnerError as e:
        # 에러 발생 시 부분 리포트 생성 후 재발생
        completed_at = datetime.now().isoformat()
        duration = time.time() - start_time

        logger.error(f"\n❌ 배치 실행 중단: {e}")
        logger.info("부분 실행 결과 리포트를 생성합니다...")

        generate_batch_report(
            track_config=track_config,
            results=results,
            track_dirs=track_dirs,
            started_at=started_at,
            completed_at=completed_at,
            duration=duration
        )

        raise

    # 완료 처리
    completed_at = datetime.now().isoformat()
    duration = time.time() - start_time

    # 결과 리포트 생성
    report_path = generate_batch_report(
        track_config=track_config,
        results=results,
        track_dirs=track_dirs,
        started_at=started_at,
        completed_at=completed_at,
        duration=duration
    )

    # 완료 요약 출력
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    logger.info(f"\n{'='*70}")
    logger.info(f"🎉 배치 실행 완료!")
    logger.info(f"{'='*70}")
    logger.info(f"트랙: {track_name}")
    logger.info(f"성공: {successful}/{total_files}")
    logger.info(f"실패: {failed}/{total_files}")
    logger.info(f"소요 시간: {duration:.1f}초")
    logger.info(f"결과 리포트: {report_path}")
    logger.info(f"오디오 파일 위치: {track_dirs['audio']}")
    logger.info(f"{'='*70}\n")

    return {
        "track_name": track_name,
        "successful": successful,
        "failed": failed,
        "total": total_files,
        "duration": duration,
        "report_path": report_path,
        "audio_dir": track_dirs["audio"]
    }


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="트랙 기반 배치 오디오 가이드 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 실행
  python -m src.batch_runner --track-file tracks/sample_track.yaml

  # Dry-run 모드 (API 호출 없이 테스트)
  python -m src.batch_runner --track-file tracks/my_track.yaml --dry-run

  # 특정 트랙 실행
  python -m src.batch_runner --track-file tracks/cultural_heritage.yaml

출력 구조:
  outputs/tracks/[트랙명]/
  ├── info/       - 정보 파일
  ├── script/     - 스크립트 파일
  ├── audio/      - 오디오 파일 (최종 결과물)
  └── batch_report.json - 실행 결과 리포트
        """
    )

    parser.add_argument(
        "--track-file",
        type=Path,
        required=True,
        help="트랙 설정 YAML 파일 경로 (예: tracks/sample_track.yaml)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="테스트 모드 (API 호출 없이 목업 데이터 생성, YAML defaults 오버라이드)"
    )

    args = parser.parse_args()

    # 환경변수 로드
    load_dotenv()

    try:
        # 1. YAML 설정 로드
        track_config = load_track_config(args.track_file)

        # 2. 설정 검증
        validate_track_config(track_config)

        # 3. 배치 실행
        result = run_batch(
            track_config=track_config,
            override_dry_run=args.dry_run if args.dry_run else None
        )

        # 4. 성공 메시지
        print("\n" + "🎉 " * 20)
        print(f"배치 실행이 완료되었습니다!")
        print("🎉 " * 20)
        print(f"\n📍 결과:")
        print(f"  트랙: {result['track_name']}")
        print(f"  성공: {result['successful']}/{result['total']}")
        print(f"  오디오 파일: {result['audio_dir']}")
        print(f"  리포트: {result['report_path']}")
        print(f"\n💡 다음 단계:")
        print(f"  - 리포트 확인: cat {result['report_path']}")
        print(f"  - 오디오 재생: open {result['audio_dir']}")

        sys.exit(0)

    except FileNotFoundError as e:
        logger.error(f"\n❌ 파일을 찾을 수 없습니다: {e}")
        sys.exit(1)

    except yaml.YAMLError as e:
        logger.error(f"\n❌ YAML 파싱 오류: {e}")
        sys.exit(1)

    except BatchRunnerError as e:
        logger.error(f"\n❌ 배치 실행 실패: {e}")
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
