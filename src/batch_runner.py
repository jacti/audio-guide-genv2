"""
플레이리스트 기반 배치 오디오 가이드 생성 스크립트

YAML 설정 파일을 읽어 여러 개의 오디오 트랙을 일괄 생성합니다.
플레이리스트별로 계층적 디렉토리 구조를 유지하며, 실행 결과 리포트를 자동 생성합니다.

주요 기능:
- YAML 기반 플레이리스트 설정 파싱
- 순차적 파이프라인 실행 (info → script → audio)
- 실시간 진행률 표시
- 플레이리스트별 출력 디렉토리 구조 생성
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
    script_markdown_path,
)

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class BatchRunnerError(Exception):
    """배치 실행 중 발생하는 예외"""

    def __init__(
        self, message: str, file_name: Optional[str] = None, stage: Optional[str] = None
    ):
        self.message = message
        self.file_name = file_name
        self.stage = stage
        if file_name and stage:
            super().__init__(f"[{file_name} - {stage}] {message}")
        elif file_name:
            super().__init__(f"[{file_name}] {message}")
        else:
            super().__init__(message)


def load_playlist_config(yaml_path: Path) -> Dict[str, Any]:
    """
    YAML 플레이리스트 설정 파일을 로드합니다.

    Args:
        yaml_path: YAML 파일 경로

    Returns:
        파싱된 설정 딕셔너리

    Raises:
        FileNotFoundError: YAML 파일을 찾을 수 없을 때
        yaml.YAMLError: YAML 파싱 오류
    """
    if not yaml_path.exists():
        raise FileNotFoundError(
            f"플레이리스트 설정 파일을 찾을 수 없습니다: {yaml_path}"
        )

    logger.info(f"플레이리스트 설정 파일 로드: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"YAML 파싱 오류: {e}")

    return config


def validate_playlist_config(config: Dict[str, Any]) -> bool:
    """
    플레이리스트 설정 파일의 유효성을 검증합니다.

    Args:
        config: 플레이리스트 설정 딕셔너리

    Returns:
        검증 성공 여부

    Raises:
        BatchRunnerError: 필수 필드 누락 또는 잘못된 설정
    """
    # 필수 필드 확인
    if "playlist_output_dir_name" not in config:
        raise BatchRunnerError("필수 필드 누락: playlist_output_dir_name")

    if "playlist_title" not in config:
        raise BatchRunnerError("필수 필드 누락: playlist_title")

    if "files" not in config or not isinstance(config["files"], list):
        raise BatchRunnerError("필수 필드 누락 또는 형식 오류: files (리스트여야 함)")

    if len(config["files"]) == 0:
        raise BatchRunnerError(
            "files 리스트가 비어있습니다. 최소 1개 이상의 파일이 필요합니다."
        )

    # 각 파일 항목 검증
    for idx, file_item in enumerate(config["files"]):
        if not isinstance(file_item, dict):
            raise BatchRunnerError(f"files[{idx}]: 딕셔너리 형식이어야 합니다.")

        if "output_name" not in file_item:
            raise BatchRunnerError(f"files[{idx}]: 필수 필드 누락 - output_name")

    logger.info(f"✅ 설정 파일 검증 완료: {len(config['files'])}개 파일")
    return True


def create_playlist_directories(
    playlist_name: str, base_dir: Path = Path("outputs/playlists")
) -> Dict[str, Path]:
    """
    플레이리스트별 출력 디렉토리 구조를 생성합니다.

    Args:
        playlist_name: 플레이리스트 이름
        base_dir: 기본 출력 디렉토리

    Returns:
        생성된 디렉토리 경로 딕셔너리
        {
            "playlist_root": Path,
            "info": Path,
            "script": Path,
            "audio": Path
        }
    """
    # 플레이리스트 이름을 파일시스템 안전한 형태로 변환
    safe_playlist_name = sanitize_keyword_for_path(playlist_name)
    playlist_root = base_dir / safe_playlist_name

    # 디렉토리 생성
    dirs = {
        "playlist_root": playlist_root,
        "info": playlist_root / "info",
        "script": playlist_root / "script",
        "audio": playlist_root / "audio",
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"📁 플레이리스트 디렉토리 생성 완료: {playlist_root}")

    return dirs


def merge_file_config(
    file_config: Dict[str, Any], defaults: Dict[str, Any]
) -> Dict[str, Any]:
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
    playlist_dirs: Dict[str, Path],
) -> None:
    """
    선택된 파이프라인 단계의 의존성을 검증합니다.

    이전 단계의 출력 파일이 존재하지 않으면 에러를 발생시킵니다.

    Args:
        stages: 실행할 파이프라인 단계 리스트 (1: info, 2: script, 3: audio)
        output_name: 출력 파일명
        playlist_dirs: 플레이리스트 디렉토리 경로 딕셔너리

    Raises:
        FileNotFoundError: 필요한 입력 파일이 존재하지 않을 때
    """
    # Stage 2 (script_gen)를 실행하려면 Stage 1 (info)의 출력이 필요
    if 2 in stages and 1 not in stages:
        info_path = info_markdown_path(output_name, playlist_dirs["info"])
        if not info_path.exists():
            raise FileNotFoundError(
                f"❌ Stage 2 (스크립트 생성)를 실행하려면 info 파일이 필요합니다.\n"
                f"   필요한 파일: {info_path}\n"
                f"   해결 방법: --stages 1,2 로 실행하거나 먼저 Stage 1을 실행하세요."
            )

    # Stage 3 (audio_gen)를 실행하려면 Stage 2 (script)의 출력이 필요
    if 3 in stages and 2 not in stages:
        script_path = script_markdown_path(output_name, playlist_dirs["script"])
        if not script_path.exists():
            raise FileNotFoundError(
                f"❌ Stage 3 (오디오 생성)을 실행하려면 script 파일이 필요합니다.\n"
                f"   필요한 파일: {script_path}\n"
                f"   해결 방법: --stages 2,3 로 실행하거나 먼저 Stage 2를 실행하세요."
            )


def run_single_file(
    file_config: Dict[str, Any],
    playlist_dirs: Dict[str, Path],
    file_index: int,
    total_files: int,
    stages: List[int] = [1, 2, 3],
) -> Dict[str, Any]:
    """
    단일 파일에 대해 지정된 파이프라인 단계를 실행합니다.

    Args:
        file_config: 파일 설정 (defaults와 병합된 상태)
        playlist_dirs: 플레이리스트 디렉토리 경로 딕셔너리
        file_index: 현재 파일 인덱스 (1부터 시작)
        total_files: 전체 파일 개수
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])

    Returns:
        실행 결과 딕셔너리
        {
            "output_name": str,
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

    result = {
        "output_name": output_name,
        "started_at": datetime.now().isoformat(),
        "status": "pending",
        "stages_run": stages,
    }

    logger.info(f"\n{'='*70}")
    logger.info(f"[{file_index}/{total_files}] {output_name}")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}")

    info_path = None
    script_path = None
    try:
        # 의존성 검증
        validate_stage_dependencies(stages, output_name, playlist_dirs)

        # Pipeline 1: 정보 검색
        if 1 in stages:
            logger.info("  → [Stage 1] 정보 검색 중...")
            info_path = info_retrieval.run(
                output_name=output_name,
                perplexity_model=file_config.get("perplexity_model", "sonar-pro"),
                info_retrieval_prompt_template_name=file_config.get(
                    "info_retrieval_prompt_template_name", "default"
                ),
                info_retrieval_user_content_text=file_config.get(
                    "info_retrieval_user_content_text",
                    "한국 문화유산에 대한 상세한 정보를 수집해주세요.",
                ),
                output_dir=playlist_dirs["info"],
            )
            logger.info(f"  ✓ [Stage 1] 정보 검색 완료: {info_path.name}")
        else:
            info_path = info_markdown_path(output_name, playlist_dirs["info"])
            logger.info("  ⊘ [Stage 1] 건너뜀 (이미 존재하는 파일 사용)")

        # Pipeline 2: 스크립트 생성
        if 2 in stages:
            logger.info("  → [Stage 2] 스크립트 생성 중...")
            script_path = script_gen.run(
                output_name=output_name,
                script_gen_prompt_template_name=file_config[
                    "script_gen_prompt_template_name"
                ],
                script_gen_model=file_config.get("script_gen_model", "gpt-4o"),
                info_retrieval_result_file_path=info_path,
                output_dir=playlist_dirs["script"],
                script_gen_user_content_text=file_config.get(
                    "script_gen_user_content_text"
                ),
                temperature=file_config.get("temperature", 0.7),
            )
            logger.info(f"  ✓ [Stage 2] 스크립트 생성 완료: {script_path.name}")
        else:
            script_path = script_markdown_path(output_name, playlist_dirs["script"])
            logger.info("  ⊘ [Stage 2] 건너뜀 (이미 존재하는 파일 사용)")

        # Pipeline 3: 오디오 생성
        if 3 in stages:
            logger.info("  → [Stage 3] 오디오 생성 중...")
            audio_path = audio_gen.run(
                output_name=output_name,
                tts_language=file_config.get("tts_language", "ko-KR"),
                script_gen_result_file_path=script_path,
                output_dir=playlist_dirs["audio"],
                voice=file_config.get("voice", "Zephyr"),
                gemini_tts_model=file_config.get(
                    "gemini_tts_model", "gemini-2.5-pro-tts"
                ),
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
            message=error_msg, file_name=output_name, stage="파이프라인 실행"
        ) from e


def generate_batch_report(
    playlist_config: Dict[str, Any],
    results: List[Dict[str, Any]],
    playlist_dirs: Dict[str, Path],
    started_at: str,
    completed_at: str,
    duration: float,
) -> Path:
    """
    배치 실행 결과 리포트를 JSON 파일로 생성합니다.

    Args:
        playlist_config: 플레이리스트 설정
        results: 각 파일 실행 결과 리스트
        playlist_dirs: 플레이리스트 디렉토리 경로
        started_at: 시작 시각 (ISO format)
        completed_at: 완료 시각 (ISO format)
        duration: 소요 시간 (초)

    Returns:
        생성된 리포트 파일 경로
    """
    report = {
        "playlist_title": playlist_config["playlist_title"],
        "playlist_output_dir_name": playlist_config["playlist_output_dir_name"],
        "description": playlist_config.get("description", ""),
        "metadata": playlist_config.get("metadata", {}),
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 2),
        "total_files": len(results),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "files": results,
    }

    report_path = playlist_dirs["playlist_root"] / "batch_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 결과 리포트 생성: {report_path}")

    return report_path


def run_batch(
    playlist_config: Dict[str, Any],
    stages: List[int] = [1, 2, 3],
) -> Dict[str, Any]:
    """
    플레이리스트 전체를 배치 실행합니다.

    Args:
        playlist_config: 플레이리스트 설정 딕셔너리
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])

    Returns:
        실행 결과 요약 딕셔너리

    Raises:
        BatchRunnerError: 실행 중 오류 발생
    """
    playlist_title = playlist_config["playlist_title"]
    playlist_output_dir_name = playlist_config["playlist_output_dir_name"]
    files = playlist_config["files"]
    defaults = playlist_config.get("defaults", {})

    # defaults가 None인 경우 처리
    if defaults is None:
        defaults = {}

    total_files = len(files)

    logger.info(f"\n{'='*70}")
    logger.info(f"🎬 배치 실행 시작: {playlist_title}")
    logger.info(f"출력 디렉토리: {playlist_output_dir_name}")
    logger.info(f"총 {total_files}개 파일")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}\n")

    # 플레이리스트 디렉토리 생성
    playlist_dirs = create_playlist_directories(playlist_output_dir_name)

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
                playlist_dirs=playlist_dirs,
                file_index=idx,
                total_files=total_files,
                stages=stages,
            )
            results.append(result)

    except BatchRunnerError as e:
        # 에러 발생 시 부분 리포트 생성 후 재발생
        completed_at = datetime.now().isoformat()
        duration = time.time() - start_time

        logger.error(f"\n❌ 배치 실행 중단: {e}")
        logger.info("부분 실행 결과 리포트를 생성합니다...")

        generate_batch_report(
            playlist_config=playlist_config,
            results=results,
            playlist_dirs=playlist_dirs,
            started_at=started_at,
            completed_at=completed_at,
            duration=duration,
        )

        raise

    # 완료 처리
    completed_at = datetime.now().isoformat()
    duration = time.time() - start_time

    # 결과 리포트 생성
    report_path = generate_batch_report(
        playlist_config=playlist_config,
        results=results,
        playlist_dirs=playlist_dirs,
        started_at=started_at,
        completed_at=completed_at,
        duration=duration,
    )

    # 완료 요약 출력
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    logger.info(f"\n{'='*70}")
    logger.info(f"🎉 배치 실행 완료!")
    logger.info(f"{'='*70}")
    logger.info(f"플레이리스트: {playlist_title}")
    logger.info(f"출력 디렉토리: {playlist_output_dir_name}")
    logger.info(f"성공: {successful}/{total_files}")
    logger.info(f"실패: {failed}/{total_files}")
    logger.info(f"소요 시간: {duration:.1f}초")
    logger.info(f"결과 리포트: {report_path}")
    logger.info(f"오디오 파일 위치: {playlist_dirs['audio']}")
    logger.info(f"{'='*70}\n")

    return {
        "playlist_title": playlist_title,
        "playlist_output_dir_name": playlist_output_dir_name,
        "successful": successful,
        "failed": failed,
        "total": total_files,
        "duration": duration,
        "report_path": report_path,
        "audio_dir": playlist_dirs["audio"],
    }


def run_batch_parallel(
    playlist_config: Dict[str, Any],
    stages: List[int] = [1, 2, 3],
    max_workers: int = 3,
) -> Dict[str, Any]:
    """
    플레이리스트 전체를 병렬로 배치 실행합니다.

    ThreadPoolExecutor를 사용하여 여러 파일을 동시에 처리합니다.
    먼저 완료된 워커가 다음 파일을 받아 처리하는 동적 할당 방식입니다.

    Args:
        playlist_config: 플레이리스트 설정 딕셔너리
        stages: 실행할 파이프라인 단계 리스트 (기본값: [1, 2, 3])
        max_workers: 최대 동시 워커 수 (기본값: 3, Gemini TTS 제약)

    Returns:
        실행 결과 요약 딕셔너리

    Raises:
        BatchRunnerError: 실행 중 오류 발생
        KeyboardInterrupt: 사용자 중단
    """
    playlist_title = playlist_config["playlist_title"]
    playlist_output_dir_name = playlist_config["playlist_output_dir_name"]
    files = playlist_config["files"]
    defaults = playlist_config.get("defaults", {})

    # defaults가 None인 경우 처리
    if defaults is None:
        defaults = {}

    total_files = len(files)

    logger.info(f"\n{'='*70}")
    logger.info(f"🎬 병렬 배치 실행 시작: {playlist_title}")
    logger.info(f"출력 디렉토리: {playlist_output_dir_name}")
    logger.info(f"총 {total_files}개 파일 | 워커 수: {max_workers}")
    logger.info(f"실행 파이프라인: {', '.join([f'Stage {s}' for s in stages])}")
    logger.info(f"{'='*70}\n")

    # 플레이리스트 디렉토리 생성
    playlist_dirs = create_playlist_directories(playlist_output_dir_name)

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
                "status": "cancelled",
                "error": "다른 파일 처리 중 에러 발생으로 취소됨",
            }

        try:
            # defaults와 개별 설정 병합
            file_config = merge_file_config(file_item, defaults)

            # 워커 ID를 포함한 로그
            worker_name = threading.current_thread().name
            logger.info(
                f"[{worker_name}] 📁 {file_config['output_name']} 처리 시작... ({idx}/{total_files})"
            )

            # 파이프라인 실행
            result = run_single_file(
                file_config=file_config,
                playlist_dirs=playlist_dirs,
                file_index=idx,
                total_files=total_files,
                stages=stages,
            )

            # 완료 카운트 업데이트 (thread-safe)
            with results_lock:
                completed = len(
                    [r for r in results if r.get("status") in ["success", "failed"]]
                )
                logger.info(
                    f"[{worker_name}] ✅ {file_config['output_name']} 완료 ({completed + 1}/{total_files})"
                )

            return result

        except Exception as e:
            # 첫 번째 에러 기록
            if not error_occurred.is_set():
                error_occurred.set()
                first_error["exception"] = e
                logger.error(
                    f"[{threading.current_thread().name}] ❌ 에러 발생! 모든 워커 중단 중..."
                )

            raise

    try:
        with ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="Worker"
        ) as executor:
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
                        playlist_config=playlist_config,
                        results=results,
                        playlist_dirs=playlist_dirs,
                        started_at=started_at,
                        completed_at=completed_at,
                        duration=duration,
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
                        file_name=file_item.get("output_name", "unknown"),
                    ) from e

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 사용자에 의해 중단되었습니다. 모든 워커를 종료합니다...")

        # 부분 리포트 생성
        completed_at = datetime.now().isoformat()
        duration = time.time() - start_time

        if results:
            generate_batch_report(
                playlist_config=playlist_config,
                results=results,
                playlist_dirs=playlist_dirs,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration,
            )

        raise

    # 완료 처리
    completed_at = datetime.now().isoformat()
    duration = time.time() - start_time

    # 결과 리포트 생성
    report_path = generate_batch_report(
        playlist_config=playlist_config,
        results=results,
        playlist_dirs=playlist_dirs,
        started_at=started_at,
        completed_at=completed_at,
        duration=duration,
    )

    # 완료 요약 출력
    successful = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")

    logger.info(f"\n{'='*70}")
    logger.info(f"🎉 병렬 배치 실행 완료!")
    logger.info(f"{'='*70}")
    logger.info(f"플레이리스트: {playlist_title}")
    logger.info(f"출력 디렉토리: {playlist_output_dir_name}")
    logger.info(f"성공: {successful}/{total_files}")
    logger.info(f"실패: {failed}/{total_files}")
    logger.info(f"소요 시간: {duration:.1f}초")
    logger.info(f"워커 수: {max_workers}")
    logger.info(f"결과 리포트: {report_path}")
    logger.info(f"오디오 파일 위치: {playlist_dirs['audio']}")
    logger.info(f"{'='*70}\n")

    return {
        "playlist_title": playlist_title,
        "playlist_output_dir_name": playlist_output_dir_name,
        "successful": successful,
        "failed": failed,
        "total": total_files,
        "duration": duration,
        "report_path": report_path,
        "audio_dir": playlist_dirs["audio"],
        "parallel": True,
        "max_workers": max_workers,
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
            raise ValueError(
                f"유효하지 않은 stage 번호: {stage}. 1, 2, 3 중 하나여야 합니다."
            )

    # 정렬 및 중복 제거
    stages = sorted(set(stages))

    return stages


def get_resume_start_index(
    playlist_config: Dict[str, Any],
    playlist_output_dir_name: str,
    base_dir: Path = Path("outputs/playlists"),
) -> int:
    """
    batch_report.json을 읽어 재시작할 인덱스를 계산합니다.

    마지막 성공 항목의 output_name을 원본 playlist의 files에서 찾아
    그 다음 인덱스를 반환합니다.

    Args:
        playlist_config: 원본 플레이리스트 설정
        playlist_output_dir_name: 출력 디렉토리 이름
        base_dir: 기본 출력 디렉토리

    Returns:
        재시작할 인덱스 (1-based)

    Raises:
        FileNotFoundError: batch_report.json이 없을 때
        BatchRunnerError: 재시작 인덱스를 계산할 수 없을 때
    """
    # batch_report.json 경로 구성
    safe_dir_name = sanitize_keyword_for_path(playlist_output_dir_name)
    report_path = base_dir / safe_dir_name / "batch_report.json"

    if not report_path.exists():
        raise FileNotFoundError(
            f"batch_report.json을 찾을 수 없습니다: {report_path}\n"
            f"   --resume 옵션은 이전 실행 기록이 있어야 사용할 수 있습니다."
        )

    # batch_report.json 읽기
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    # 성공한 파일 목록 확인
    successful_files = [
        f for f in report.get("files", []) if f.get("status") == "success"
    ]

    if not successful_files:
        # 성공한 파일이 없으면 처음부터 시작
        logger.info("이전 실행에서 성공한 파일이 없습니다. 처음부터 시작합니다.")
        return 1

    # 마지막 성공 항목의 output_name
    last_success_name = successful_files[-1].get("output_name")

    # 원본 playlist에서 해당 output_name의 인덱스 찾기
    files = playlist_config.get("files", [])
    for idx, file_item in enumerate(files, start=1):
        if file_item.get("output_name") == last_success_name:
            resume_index = idx + 1
            if resume_index > len(files):
                raise BatchRunnerError(
                    f"모든 파일이 이미 성공적으로 완료되었습니다.\n"
                    f"   마지막 성공 항목: {last_success_name} ({idx}/{len(files)})"
                )
            logger.info(
                f"📍 마지막 성공 항목: {last_success_name} ({idx}번째)\n"
                f"   → {resume_index}번부터 재시작합니다."
            )
            return resume_index

    # output_name을 찾지 못한 경우
    raise BatchRunnerError(
        f"마지막 성공 항목 '{last_success_name}'을(를) 현재 플레이리스트에서 찾을 수 없습니다.\n"
        f"   플레이리스트 파일이 변경되었을 수 있습니다."
    )


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="플레이리스트 기반 배치 오디오 가이드 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 실행 (순차 처리, 모든 파이프라인)
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml

  # 병렬 실행 (3개 워커, 속도 향상)
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --parallel

  # 병렬 실행 + 워커 수 지정
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --parallel --max-workers 2

  # 스크립트 생성만 재실행 (info 파일은 이미 존재)
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --stages 2

  # 스크립트 + 오디오만 병렬 재생성
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --stages 2,3 --parallel

  # 오디오만 재생성 (script 파일은 이미 존재)
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --stages 3

재시작/범위 지정 실행:
  # 마지막 성공 항목 다음부터 자동 재시작 (batch_report.json 기반)
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --resume

  # 22번부터 끝까지 실행
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --start-from 22

  # 22번부터 30번까지만 실행
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --start-from 22 --end 30

  # 재시작 + 병렬 처리 조합
  python -m src.batch_runner --playlist-file playlists/sample_playlist.yaml --resume --parallel

출력 구조:
  outputs/playlists/[플레이리스트명]/
  ├── info/       - 정보 파일 (Stage 1)
  ├── script/     - 스크립트 파일 (Stage 2)
  ├── audio/      - 오디오 파일 (Stage 3, 최종 결과물)
  └── batch_report.json - 실행 결과 리포트

주의사항:
  - 병렬 처리는 API quota를 빠르게 소진할 수 있습니다
  - Gemini TTS API는 약 3개 동시 요청만 지원하므로 max-workers=3 권장
  - 에러 발생 시 모든 워커가 즉시 중단되며 부분 리포트가 생성됩니다
  - --resume은 batch_report.json의 마지막 성공 항목을 기준으로 다음 항목부터 재시작합니다
        """,
    )

    parser.add_argument(
        "--playlist-file",
        type=Path,
        required=True,
        help="플레이리스트 설정 YAML 파일 경로 (예: playlists/sample_playlist.yaml)",
    )

    parser.add_argument(
        "--stages",
        type=str,
        default="1,2,3",
        help="실행할 파이프라인 단계 (기본값: 1,2,3). 예: '2' 또는 '2,3'",
    )

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="병렬 처리 모드 활성화 (3개 워커 동시 실행, 기본값: 순차 처리)",
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="병렬 처리 시 최대 워커 수 (기본값: 3, Gemini TTS API 제약)",
    )

    parser.add_argument(
        "--single",
        type=str,
        default=None,
        help="단일 항목만 실행 (output_name 지정). 예: --single 02_visit_tips",
    )

    parser.add_argument(
        "--start-from",
        type=int,
        default=None,
        help="특정 인덱스부터 시작 (1-based). 예: --start-from 22",
    )

    parser.add_argument(
        "--end",
        type=int,
        default=None,
        help="특정 인덱스까지만 실행 (1-based, 선택적). 예: --end 30",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="이전 실행의 마지막 성공 항목 다음부터 자동 재시작 (batch_report.json 기반)",
    )

    args = parser.parse_args()

    # 환경변수 로드
    load_dotenv()

    try:
        # 1. stages 파싱
        stages = parse_stages(args.stages)
        logger.info(f"실행할 파이프라인 단계: {stages}")

        # 2. YAML 설정 로드
        playlist_config = load_playlist_config(args.playlist_file)

        # 3. 설정 검증
        validate_playlist_config(playlist_config)

        # 3.5. 단일 항목 필터링 (--single 옵션)
        if args.single:
            target_output_name = args.single
            matching_files = [
                f
                for f in playlist_config["files"]
                if f.get("output_name") == target_output_name
            ]

            if not matching_files:
                available_names = [
                    f.get("output_name") for f in playlist_config["files"]
                ]
                raise BatchRunnerError(
                    f"output_name '{target_output_name}'을(를) 찾을 수 없습니다.\n"
                    f"   사용 가능한 output_name 목록:\n"
                    f"   {', '.join(available_names)}"
                )

            playlist_config["files"] = matching_files
            logger.info(f"🎯 단일 항목 모드: {target_output_name}")

        # 3.6. 범위 지정 실행 (--start-from, --end, --resume 옵션)
        else:
            total_files = len(playlist_config["files"])
            start_idx = 1
            end_idx = total_files

            # --resume 옵션: batch_report.json에서 재시작 인덱스 계산
            if args.resume:
                start_idx = get_resume_start_index(
                    playlist_config=playlist_config,
                    playlist_output_dir_name=playlist_config[
                        "playlist_output_dir_name"
                    ],
                )

            # --start-from 옵션: 명시적 시작 인덱스 (--resume보다 우선)
            if args.start_from is not None:
                if args.start_from < 1 or args.start_from > total_files:
                    raise BatchRunnerError(
                        f"--start-from 값이 범위를 벗어났습니다: {args.start_from}\n"
                        f"   유효한 범위: 1 ~ {total_files}"
                    )
                start_idx = args.start_from

            # --end 옵션: 종료 인덱스
            if args.end is not None:
                if args.end < 1 or args.end > total_files:
                    raise BatchRunnerError(
                        f"--end 값이 범위를 벗어났습니다: {args.end}\n"
                        f"   유효한 범위: 1 ~ {total_files}"
                    )
                if args.end < start_idx:
                    raise BatchRunnerError(
                        f"--end ({args.end})가 시작 인덱스 ({start_idx})보다 작습니다."
                    )
                end_idx = args.end

            # 범위가 지정된 경우에만 슬라이싱
            if start_idx > 1 or end_idx < total_files:
                original_files = playlist_config["files"]
                playlist_config["files"] = original_files[start_idx - 1 : end_idx]
                logger.info(
                    f"📋 범위 지정 실행: {start_idx}번 ~ {end_idx}번 "
                    f"(총 {len(playlist_config['files'])}개 / 전체 {total_files}개)"
                )

        # 4. 배치 실행 (병렬 또는 순차)
        if args.parallel:
            logger.info(f"🔄 병렬 처리 모드 (워커 수: {args.max_workers})")
            result = run_batch_parallel(
                playlist_config=playlist_config,
                stages=stages,
                max_workers=args.max_workers,
            )
        else:
            logger.info(f"➡️  순차 처리 모드")
            result = run_batch(
                playlist_config=playlist_config,
                stages=stages,
            )

        # 5. 성공 메시지
        print("\n" + "🎉 " * 20)
        print(f"배치 실행이 완료되었습니다!")
        print("🎉 " * 20)
        print(f"\n📍 결과:")
        print(f"  플레이리스트: {result['playlist_title']}")
        print(f"  출력 디렉토리: {result['playlist_output_dir_name']}")
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
