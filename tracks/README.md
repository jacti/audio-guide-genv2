# Tracks 디렉토리

이 디렉토리는 트랙 기반 배치 오디오 가이드 생성을 위한 YAML 설정 파일을 저장합니다.

## 트랙이란?

트랙(Track)은 여러 개의 오디오 가이드 파일을 하나의 주제나 카테고리로 묶은 단위입니다.

예시:
- **"꿀팁 가이드"** 트랙: 박물관 이용 팁 관련 파일 3개
- **"고려시대 유물"** 트랙: 고려시대 주요 유물 소개 파일 10개
- **"어린이 가이드"** 트랙: 어린이를 위한 쉬운 설명 파일 5개

## 사용 방법

### 1. YAML 설정 파일 작성

`sample_track.yaml`을 참고하여 새로운 트랙 파일을 작성합니다.

```bash
cp sample_track.yaml my_custom_track.yaml
# 파일을 편집하여 원하는 트랙 구성
```

### 2. 배치 실행

```bash
python -m src.batch_runner --track-file tracks/my_custom_track.yaml
```

### 3. 결과 확인

생성된 파일은 `outputs/tracks/[트랙명]/` 아래에 계층적으로 저장됩니다.

```
outputs/tracks/꿀팁_가이드/
├── audio/
│   ├── 1_박물관소개.mp3
│   ├── 2_전시관소개.mp3
│   └── 3_앱사용꿀팁.mp3
├── script/
│   └── ...
├── info/
│   └── ...
└── batch_report.json
```

## 파일 구조

필수 필드:
- `track_name`: 트랙 이름
- `files`: 생성할 오디오 파일 목록 (각 파일은 `output_name`과 `keyword` 필수)

선택 필드:
- `description`: 트랙 설명
- `metadata`: 작성자, 버전, 태그 등
- `defaults`: 모든 파일에 공통 적용할 설정

자세한 내용은 `sample_track.yaml`의 주석을 참고하세요.
