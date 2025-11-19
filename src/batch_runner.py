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
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# YAML 파서
try:
    import yaml
except ImportError:
    print("❌ PyYAML이 설치되지 않았습니다. requirements.txt를 확인해주세요.")
    sys.exit(1)

# 파이프라인 모듈 임포트
from src.pipelines import info_retrieval, script_gen, audio_gen
from src.utils.path_sanitizer import (
    sanitize_keyword_for_path,
    info_markdown_path,
    script_markdown_path
)

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

        if "search_keyword" not in file_item:
            raise BatchRunnerError(f"files[{idx}]: 필수 필드 누락 - search_keyword")

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


def validate_stage_dependencies(
    stages: List[int],
    output_name: str,
    search_keyword: str,
    track_dirs: Dict[str, Path]
) -> None:
    """
    선택된 파이프라인 단계의 의존성을 검증합니다.

    이전 단계의 출력 파일이 존재하지 않으면 에러를 발생시킵니다.

    Args:
        stages: 실행할 파이프라인 단계 리스트 (1: info, 2: script, 3: audio)
        output_name: 출력 파일명
        search_keyword: 검색 키워드
        track_dirs: 트랙 디렉토리 경로 딕셔너리

    Raises:
        FileNotFoundError: 필요한 입력 파일이 존재하지 않을 때
    """
    # Stage 2 (script_gen)를 실행하려면 Stage 1 (info)의 출력이 필요
    if 2 in stages and 1 not in stages:
        info_path = info_markdown_path(search_keyword, track_dirs["info"], output_name)
        if not info_path.exists():
            raise FileNotFoundError(
                f"❌ Stage 2 (스크립트 생성)를 실행하려면 info 파일이 필요합니다.\n"
                f"   필요한 파일: {info_path}\n"
                f"   해결 방법: --stages 1,2 로 실행하거나 먼저 Stage 1을 실행하세요."
            )

    # Stage 3 (audio_gen)를 실행하려면 Stage 2 (script)의 출력이 필요
    if 3 in stages and 2 not in stages:
        script_path = script_markdown_path(search_keyword, track_dirs["script"], output_name)
        if not script_path.exists():
            raise FileNotFoundError(
                f"❌ Stage 3 (오디오 생성)을 실행하려면 script 파일이 필요합니다.\n"
                f"   필요한 파일: {script_path}\n"
                f"   해결 방법: --stages 2,3 로 실행하거나 먼저 Stage 2를 실행하세요."
            )


def run_single_file(
    file_config: Dict[str, Any],
    track_dirs: Dict[str, Path],
    file_index: int,
    total_files: int,
    stages: List[int] = [1, 2, 3]
) -> Dict[str, Any]:
    """
    단일 파일에 대해 지정된 파이프라인 단계를 실행합니다.

    Args:
        file_config: 파일 설정 (defaults와 병합된 상태)
        track_dirs: 트랙 디렉토리 경로 딕셔너리
        file_index: 현재 파일 인덱스 (1부터 시작)
        total_files: 전체 파일 개수
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])

    Returns:
        실행 결과 딕셔너리
        {
            "output_name": str,
            "search_keyword": str,
            "status": "success" | "failed",
            "error": str (실패 시),
            "audio_path": str,
            "started_at": str,
            "completed_at": str,
            "stages_run": List[int]
        }

    Raises:
        BatchRunnerError: 파이프라인 실행 실패
    """
    output_name = file_config["output_name"]
    search_keyword = file_config["search_keyword"]
    dry_run = file_config.get("dry_run", False)

    result = {
        "output_name": output_name,
        "search_keyword": search_keyword,
        "started_at": datetime.now().isoformat(),
        "status": "pending",
        "stages_run": stages
    }

    logger.info(f"\n{'='*70}")
    logger.info(f"[{file_index}/{total_files}] {output_name}")
    logger.info(f"검색 키워드: {search_keyword}")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}")

    try:
        # 의존성 검증
        validate_stage_dependencies(stages, output_name, search_keyword, track_dirs)

        # Pipeline 1: 정보 검색
        if 1 in stages:
            logger.info("  → [Stage 1] 정보 검색 중...")
            info_path = info_retrieval.run(
                search_keyword=search_keyword,
                model=file_config.get("model", "gpt-4.1"),
                prompt_version=file_config.get("info_prompt_version", "default"),
                info_prompt=file_config.get("info_prompt", "한국 문화유산에 대한 상세한 정보를 수집해주세요."),
                max_queries=file_config.get("max_queries", None),
                output_dir=track_dirs["info"],
                dry_run=dry_run,
                output_name=output_name
            )
            logger.info(f"  ✓ [Stage 1] 정보 검색 완료: {info_path.name}")
        else:
            logger.info("  ⊘ [Stage 1] 건너뜀 (이미 존재하는 파일 사용)")

        # Pipeline 2: 스크립트 생성
        if 2 in stages:
            logger.info("  → [Stage 2] 스크립트 생성 중...")
            script_path = script_gen.run(
                search_keyword=search_keyword,
                info_dir=track_dirs["info"],
                output_dir=track_dirs["script"],
                script_prompt_version=file_config.get("script_prompt_version", "v2-tts"),
                custom_prompt=file_config.get("script_gen_prompt", None),
                temperature=file_config.get("temperature", 0.7),
                model=file_config.get("model", "gpt-4.1"),
                dry_run=dry_run,
                output_name=output_name
            )
            logger.info(f"  ✓ [Stage 2] 스크립트 생성 완료: {script_path.name}")
        else:
            logger.info("  ⊘ [Stage 2] 건너뜀 (이미 존재하는 파일 사용)")

        # Pipeline 3: 오디오 생성
        if 3 in stages:
            logger.info("  → [Stage 3] 오디오 생성 중...")
            audio_path = audio_gen.run(
                search_keyword=search_keyword,
                script_dir=track_dirs["script"],
                output_dir=track_dirs["audio"],
                voice=file_config.get("voice", "Zephyr"),
                model=file_config.get("tts_model", "gemini-2.5-flash-tts"),
                max_retries=file_config.get("max_retries", 8),
                dry_run=dry_run,
                output_name=output_name
            )
            logger.info(f"  ✓ [Stage 3] 오디오 생성 완료: {audio_path.name}")
            result["audio_path"] = str(audio_path)
        else:
            logger.info("  ⊘ [Stage 3] 건너뜀 (이미 존재하는 파일 사용)")

        result["status"] = "success"
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
    override_dry_run: Optional[bool] = None,
    stages: List[int] = [1, 2, 3]
) -> Dict[str, Any]:
    """
    트랙 전체를 배치 실행합니다.

    Args:
        track_config: 트랙 설정 딕셔너리
        override_dry_run: dry_run 모드 강제 설정 (None이면 설정 파일 따름)
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])

    Returns:
        실행 결과 요약 딕셔너리

    Raises:
        BatchRunnerError: 실행 중 오류 발생
    """
    track_name = track_config["track_name"]
    files = track_config["files"]
    defaults = track_config.get("defaults", {})

    # defaults가 None인 경우 처리
    if defaults is None:
        defaults = {}

    # dry_run 오버라이드 처리
    if override_dry_run is not None:
        defaults["dry_run"] = override_dry_run

    total_files = len(files)

    logger.info(f"\n{'='*70}")
    logger.info(f"🎬 배치 실행 시작: {track_name}")
    logger.info(f"총 {total_files}개 파일")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
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
                total_files=total_files,
                stages=stages
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


def run_batch_parallel(
    track_config: Dict[str, Any],
    override_dry_run: Optional[bool] = None,
    stages: List[int] = [1, 2, 3],
    max_workers: int = 3
) -> Dict[str, Any]:
    """
    트랙 전체를 병렬로 배치 실행합니다.

    ThreadPoolExecutor를 사용하여 여러 파일을 동시에 처리합니다.
    먼저 완료된 워커가 다음 파일을 받아 처리하는 동적 할당 방식입니다.

    Args:
        track_config: 트랙 설정 딕셔너리
        override_dry_run: dry_run 모드 강제 설정 (None이면 설정 파일 따름)
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])
        max_workers: 최대 동시 워커 수 (기본값: 3, Gemini TTS 제약)

    Returns:
        실행 결과 요약 딕셔너리

    Raises:
        BatchRunnerError: 실행 중 오류 발생
        KeyboardInterrupt: 사용자 중단
    """
    track_name = track_config["track_name"]
    files = track_config["files"]
    defaults = track_config.get("defaults", {})

    # defaults가 None인 경우 처리
    if defaults is None:
        defaults = {}

    # dry_run 오버라이드 처리
    if override_dry_run is not None:
        defaults["dry_run"] = override_dry_run

    total_files = len(files)

    logger.info(f"\n{'='*70}")
    logger.info(f"🎬 병렬 배치 실행 시작: {track_name}")
    logger.info(f"총 {total_files}개 파일 | 워커 수: {max_workers}")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}\n")

    # 트랙 디렉토리 생성
    track_dirs = create_track_directories(track_name)

    # 실행 시작
    started_at = datetime.now().isoformat()
    start_time = time.time()
    results = []
    results_lock = threading.Lock()

    # 에러 플래그 (첫 에러 발생 시 다른 워커들도 중단)
    error_occurred = threading.Event()
    first_error = {"exception": None}

    def run_file_worker(file_item: Dict[str, Any], idx: int) -> Dict[str, Any]:
        """
        워커 스레드에서 실행될 단일 파일 처리 함수

        Args:
            file_item: 파일 설정
            idx: 파일 인덱스 (1부터 시작)

        Returns:
            실행 결과 딕셔너리
        """
        # 다른 워커에서 에러 발생 시 즉시 중단
        if error_occurred.is_set():
            return {
                "output_name": file_item.get("output_name", "unknown"),
                "search_keyword": file_item.get("search_keyword", "unknown"),
                "status": "cancelled",
                "error": "다른 파일 처리 중 에러 발생으로 취소됨"
            }

        try:
            # defaults와 개별 설정 병합
            file_config = merge_file_config(file_item, defaults)

            # 워커 ID를 포함한 로그
            worker_name = threading.current_thread().name
            logger.info(f"[{worker_name}] 📁 {file_config['output_name']} 처리 시작... ({idx}/{total_files})")

            # 파이프라인 실행
            result = run_single_file(
                file_config=file_config,
                track_dirs=track_dirs,
                file_index=idx,
                total_files=total_files,
                stages=stages
            )

            # 완료 카운트 업데이트 (thread-safe)
            with results_lock:
                completed = len([r for r in results if r.get("status") in ["success", "failed"]])
                logger.info(f"[{worker_name}] ✅ {file_config['output_name']} 완료 ({completed + 1}/{total_files})")

            return result

        except Exception as e:
            # 첫 번째 에러 기록
            if not error_occurred.is_set():
                error_occurred.set()
                first_error["exception"] = e
                logger.error(f"[{threading.current_thread().name}] ❌ 에러 발생! 모든 워커 중단 중...")

            raise

    try:
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Worker") as executor:
            # 모든 파일에 대한 Future 생성
            future_to_file = {
                executor.submit(run_file_worker, file_item, idx): (file_item, idx)
                for idx, file_item in enumerate(files, start=1)
            }

            # 완료된 작업부터 결과 수집
            for future in as_completed(future_to_file):
                file_item, idx = future_to_file[future]

                try:
                    result = future.result()

                    with results_lock:
                        results.append(result)

                except BatchRunnerError as e:
                    # 에러 발생 시 즉시 중단
                    logger.error(f"\n❌ 파일 처리 실패: {e.file_name}")

                    # 실행 중인 모든 작업 취소
                    for f in future_to_file:
                        f.cancel()

                    # 에러 발생 시점까지의 결과로 부분 리포트 생성
                    completed_at = datetime.now().isoformat()
                    duration = time.time() - start_time

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

                except Exception as e:
                    # 예상치 못한 에러
                    logger.error(f"\n❌ 예상치 못한 에러: {e}")

                    # 모든 작업 취소
                    for f in future_to_file:
                        f.cancel()

                    raise BatchRunnerError(
                        message=f"파일 처리 중 예상치 못한 에러: {e}",
                        file_name=file_item.get("output_name", "unknown")
                    ) from e

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자에 의해 중단되었습니다. 모든 워커를 종료합니다...")

        # 부분 리포트 생성
        completed_at = datetime.now().isoformat()
        duration = time.time() - start_time

        if results:
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
    logger.info(f"🎉 병렬 배치 실행 완료!")
    logger.info(f"{'='*70}")
    logger.info(f"트랙: {track_name}")
    logger.info(f"성공: {successful}/{total_files}")
    logger.info(f"실패: {failed}/{total_files}")
    logger.info(f"소요 시간: {duration:.1f}초")
    logger.info(f"워커 수: {max_workers}")
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
        "audio_dir": track_dirs["audio"],
        "parallel": True,
        "max_workers": max_workers
    }


def parse_stages(stages_str: str) -> List[int]:
    """
    쉼표로 구분된 스테이지 문자열을 정수 리스트로 파싱합니다.

    Args:
        stages_str: "1,2,3" 또는 "2" 같은 형식의 문자열

    Returns:
        정수 리스트 (예: [1, 2, 3])

    Raises:
        ValueError: 잘못된 형식이거나 유효하지 않은 스테이지 번호
    """
    try:
        stages = [int(s.strip()) for s in stages_str.split(",")]
    except ValueError:
        raise ValueError(f"잘못된 stages 형식: {stages_str}. 예: '1,2,3' 또는 '2'")

    # 유효성 검증
    for stage in stages:
        if stage not in [1, 2, 3]:
            raise ValueError(f"유효하지 않은 stage 번호: {stage}. 1, 2, 3 중 하나여야 합니다.")

    # 정렬 및 중복 제거
    stages = sorted(set(stages))

    return stages


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="트랙 기반 배치 오디오 가이드 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 실행 (순차 처리, 모든 파이프라인)
  python -m src.batch_runner --track-file tracks/sample_track.yaml

  # 병렬 실행 (3개 워커, 속도 향상)
  python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel

  # 병렬 실행 + 워커 수 지정
  python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel --max-workers 2

  # Dry-run 모드 (API 호출 없이 테스트)
  python -m src.batch_runner --track-file tracks/my_track.yaml --dry-run

  # 병렬 + Dry-run (테스트)
  python -m src.batch_runner --track-file tracks/sample_track.yaml --parallel --dry-run

  # 스크립트 생성만 재실행 (info 파일은 이미 존재)
  python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2

  # 스크립트 + 오디오만 병렬 재생성
  python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 2,3 --parallel

  # 오디오만 재생성 (script 파일은 이미 존재)
  python -m src.batch_runner --track-file tracks/sample_track.yaml --stages 3

출력 구조:
  outputs/tracks/[트랙명]/
  ├── info/       - 정보 파일 (Stage 1)
  ├── script/     - 스크립트 파일 (Stage 2)
  ├── audio/      - 오디오 파일 (Stage 3, 최종 결과물)
  └── batch_report.json - 실행 결과 리포트

주의사항:
  - 병렬 처리는 API quota를 빠르게 소진할 수 있습니다
  - Gemini TTS API는 약 3개 동시 요청만 지원하므로 max-workers=3 권장
  - 에러 발생 시 모든 워커가 즉시 중단되며 부분 리포트가 생성됩니다
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

    parser.add_argument(
        "--stages",
        type=str,
        default="1,2,3",
        help="실행할 파이프라인 단계 (기본값: 1,2,3). 예: '2' 또는 '2,3'"
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="병렬 처리 모드 활성화 (3개 워커 동시 실행, 기본값: 순차 처리)"
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="병렬 처리 시 최대 워커 수 (기본값: 3, Gemini TTS API 제약)"
    )

    args = parser.parse_args()

    # 환경변수 로드
    load_dotenv()

    try:
        # 1. stages 파싱
        stages = parse_stages(args.stages)
        logger.info(f"실행할 파이프라인 단계: {stages}")

        # 2. YAML 설정 로드
        track_config = load_track_config(args.track_file)

        # 3. 설정 검증
        validate_track_config(track_config)

        # 4. 배치 실행 (병렬 또는 순차)
        if args.parallel:
            logger.info(f"🔄 병렬 처리 모드 (워커 수: {args.max_workers})")
            result = run_batch_parallel(
                track_config=track_config,
                override_dry_run=args.dry_run if args.dry_run else None,
                stages=stages,
                max_workers=args.max_workers
            )
        else:
            logger.info(f"➡️  순차 처리 모드")
            result = run_batch(
                track_config=track_config,
                override_dry_run=args.dry_run if args.dry_run else None,
                stages=stages
            )

        # 5. 성공 메시지
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
