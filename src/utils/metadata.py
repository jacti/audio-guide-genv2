"""
파이프라인 산출물 메타데이터 관리 유틸리티

각 파일 생성 시 실행 모드, 타임스탬프, 사용 모델 등의 정보를
JSON 형식으로 기록하여 산출물의 출처를 추적 가능하게 만든다.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PipelineMetadata:
    """파이프라인 실행 메타데이터를 관리하는 클래스"""

    def __init__(
        self,
        keyword: str,
        pipeline: str,
        mode: str = "production",
        model: Optional[str] = None,
        **extra_fields: Any
    ):
        """
        메타데이터 객체 초기화

        Args:
            keyword: 입력 키워드 (예: "청자 상감운학문 매병")
            pipeline: 파이프라인 이름 (info_retrieval, script_gen, audio_gen)
            mode: 실행 모드 ("production" 또는 "dry_run")
            model: 사용된 모델명 (예: "gpt-4o-mini")
            **extra_fields: 추가 메타데이터 필드
        """
        self.keyword = keyword
        self.pipeline = pipeline
        self.mode = mode
        self.model = model
        self.timestamp = datetime.now().isoformat()
        self.extra_fields = extra_fields

    def to_dict(self) -> Dict[str, Any]:
        """메타데이터를 딕셔너리로 변환"""
        data = {
            "keyword": self.keyword,
            "pipeline": self.pipeline,
            "mode": self.mode,
            "timestamp": self.timestamp,
        }

        if self.model:
            data["model"] = self.model

        # 추가 필드 병합
        data.update(self.extra_fields)

        return data

    def save(self, output_file_path: Path) -> Path:
        """
        메타데이터를 JSON 파일로 저장

        동일 디렉토리에 `{파일명}.metadata.json` 형식으로 저장한다.

        Args:
            output_file_path: 원본 산출물 파일 경로

        Returns:
            Path: 생성된 메타데이터 파일 경로

        Example:
            >>> meta = PipelineMetadata("석굴암", "info_retrieval", mode="dry_run")
            >>> meta_path = meta.save(Path("outputs/info/석굴암.md"))
            >>> # outputs/info/석굴암.md.metadata.json 생성됨
        """
        metadata_path = output_file_path.with_suffix(
            output_file_path.suffix + ".metadata.json"
        )

        try:
            # 파일 크기 정보 추가 (파일이 이미 생성된 경우)
            if output_file_path.exists():
                self.extra_fields["file_size"] = output_file_path.stat().st_size

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

            logger.info(f"메타데이터 저장 완료: {metadata_path}")
            return metadata_path

        except Exception as e:
            logger.error(f"메타데이터 저장 실패: {e}")
            raise

    @classmethod
    def load(cls, metadata_path: Path) -> "PipelineMetadata":
        """
        JSON 파일에서 메타데이터를 로드

        Args:
            metadata_path: 메타데이터 JSON 파일 경로

        Returns:
            PipelineMetadata: 로드된 메타데이터 객체

        Raises:
            FileNotFoundError: 파일이 존재하지 않을 경우
            json.JSONDecodeError: JSON 파싱 실패 시
        """
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 필수 필드 추출
        keyword = data.pop("keyword")
        pipeline = data.pop("pipeline")
        mode = data.pop("mode", "production")
        model = data.pop("model", None)

        # timestamp는 extra_fields로 보존
        return cls(
            keyword=keyword,
            pipeline=pipeline,
            mode=mode,
            model=model,
            **data  # 나머지 필드 전달
        )


def create_metadata(
    keyword: str,
    pipeline: str,
    output_file_path: Path,
    mode: str = "production",
    model: Optional[str] = None,
    **extra_fields: Any
) -> Path:
    """
    메타데이터를 생성하고 저장하는 헬퍼 함수

    Args:
        keyword: 입력 키워드
        pipeline: 파이프라인 이름
        output_file_path: 산출물 파일 경로
        mode: 실행 모드 ("production" 또는 "dry_run")
        model: 사용된 모델명 (선택적)
        **extra_fields: 추가 메타데이터

    Returns:
        Path: 생성된 메타데이터 파일 경로

    Example:
        >>> create_metadata(
        ...     keyword="석굴암",
        ...     pipeline="info_retrieval",
        ...     output_file_path=Path("outputs/info/석굴암.md"),
        ...     mode="dry_run",
        ...     model="gpt-4o-mini"
        ... )
    """
    metadata = PipelineMetadata(
        keyword=keyword,
        pipeline=pipeline,
        mode=mode,
        model=model,
        **extra_fields
    )
    return metadata.save(output_file_path)


def read_metadata(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    산출물 파일에 대응하는 메타데이터를 읽어온다

    Args:
        file_path: 산출물 파일 경로 (예: outputs/info/석굴암.md)

    Returns:
        Optional[Dict]: 메타데이터 딕셔너리, 없으면 None

    Example:
        >>> meta = read_metadata(Path("outputs/info/석굴암.md"))
        >>> if meta:
        ...     print(f"모드: {meta['mode']}, 시간: {meta['timestamp']}")
    """
    metadata_path = file_path.with_suffix(file_path.suffix + ".metadata.json")

    if not metadata_path.exists():
        logger.warning(f"메타데이터 파일 없음: {metadata_path}")
        return None

    try:
        metadata_obj = PipelineMetadata.load(metadata_path)
        return metadata_obj.to_dict()
    except Exception as e:
        logger.error(f"메타데이터 로드 실패: {e}")
        return None


# 사용 예시
if __name__ == "__main__":
    # 테스트용 샘플 생성
    test_file = Path("outputs/mock/info/테스트.md")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("# 테스트\n\n샘플 콘텐츠", encoding="utf-8")

    # 메타데이터 생성
    meta_path = create_metadata(
        keyword="테스트",
        pipeline="info_retrieval",
        output_file_path=test_file,
        mode="dry_run",
        model="gpt-4o-mini",
        note="This is a test"
    )

    print(f"메타데이터 생성됨: {meta_path}")

    # 메타데이터 읽기
    loaded = read_metadata(test_file)
    print(f"로드된 메타데이터: {json.dumps(loaded, ensure_ascii=False, indent=2)}")
