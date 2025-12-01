---
name: batch-runner
description: 오디오 가이드 배치 생성 파이프라인 실행. 정보 추출, 대본 생성, 오디오 생성 단계를 실행합니다. "00_intro 새로 만들어줘", "오디오만 다시 생성해줘", "정보추출이랑 대본 만들어줘", "트랙 재생성" 같은 요청에 사용하세요.
allowed-tools: Bash, Read, Glob, Grep
---

# Batch Runner - 오디오 가이드 배치 실행

오디오 가이드 플레이리스트의 트랙을 생성하는 파이프라인을 실행합니다.

## 필수: 가상환경 활성화

**batch_runner 실행 전에 반드시 가상환경을 활성화해야 합니다!**

```bash
source .venv/bin/activate
```

가상환경이 활성화되지 않으면 모듈을 찾을 수 없다는 에러가 발생합니다.

## 기본 명령어

```bash
# 가상환경 활성화 후 실행
source .venv/bin/activate && python -m src.batch_runner --playlist-file playlists/{playlist_filename}.yaml [options]
```

## Stages 옵션

| 요청 | stages 옵션 |
|------|-------------|
| 전부 새로 만들어줘 (기본) | (옵션 없음) |
| 정보 추출만 | `--stages 1` |
| 정보추출 + 대본 | `--stages 1,2` |
| 대본만 | `--stages 2` |
| 대본 + 오디오 | `--stages 2,3` |
| 오디오만 | `--stages 3` |

## 트랙 지정 옵션

### 단일 트랙 실행
```bash
python -m src.batch_runner --playlist-file playlists/1130_한국사완전정복.yaml --single 00_intro
```

### 범위 실행
```bash
# 22번부터 끝까지
python -m src.batch_runner --playlist-file playlists/xxx.yaml --start-from 22

# 22번부터 30번까지
python -m src.batch_runner --playlist-file playlists/xxx.yaml --start-from 22 --end 30
```

### 재시작
```bash
python -m src.batch_runner --playlist-file playlists/xxx.yaml --resume
```

## 사용자 요청 처리 방법

### 1. 플레이리스트와 트랙이 모두 지정된 경우

예: "1130_한국사완전정복.yaml의 00_intro 전부 새로 만들어줘"

```bash
python -m src.batch_runner --playlist-file playlists/1130_한국사완전정복.yaml --single 00_intro
```

### 2. 트랙만 지정된 경우

예: "00_intro 오디오만 새로 만들어줘"

**반드시 먼저** `playlists/` 디렉토리의 모든 yaml 파일에서 해당 트랙을 검색합니다:

```bash
grep -l "00_intro" playlists/*.yaml
```

- **매칭 결과가 1개**: 해당 플레이리스트로 실행
- **매칭 결과가 2개 이상**: 사용자에게 어떤 플레이리스트인지 확인 필요
- **매칭 결과 없음**: 트랙명을 확인해달라고 요청

### 3. stages 해석

사용자의 요청에서 stages를 파악합니다:

| 사용자 표현 | stages |
|------------|--------|
| "전부", "처음부터", "새로" | (없음) |
| "정보 추출", "정보만" | `--stages 1` |
| "정보랑 대본", "정보추출이랑 스크립트" | `--stages 1,2` |
| "대본만", "스크립트만" | `--stages 2` |
| "대본이랑 오디오", "스크립트랑 오디오" | `--stages 2,3` |
| "오디오만", "음성만", "mp3만" | `--stages 3` |

## 예제

### 예제 1: 특정 플레이리스트의 특정 트랙 전체 재생성
요청: "1130_한국사완전정복.yaml의 03_paleolithic_hominid 새로 만들어줘"
```bash
python -m src.batch_runner --playlist-file playlists/1130_한국사완전정복.yaml --single 03_paleolithic_hominid
```

### 예제 2: 오디오만 재생성
요청: "03_paleolithic_hominid 오디오만 다시 만들어줘"
```bash
# 먼저 어느 플레이리스트에 있는지 확인
grep -l "03_paleolithic_hominid" playlists/*.yaml
# 결과: playlists/1130_한국사완전정복.yaml

python -m src.batch_runner --playlist-file playlists/1130_한국사완전정복.yaml --single 03_paleolithic_hominid --stages 3
```

### 예제 3: 정보 추출 + 대본 생성
요청: "00_intro 정보추출이랑 대본 만들어줘"
```bash
# 플레이리스트 검색 후
python -m src.batch_runner --playlist-file playlists/{찾은_플레이리스트}.yaml --single 00_intro --stages 1,2
```

### 예제 4: 범위 실행
요청: "한국사완전정복 22번부터 30번까지 실행해줘"
```bash
python -m src.batch_runner --playlist-file playlists/1130_한국사완전정복.yaml --start-from 22 --end 30
```

## 현재 프로젝트의 플레이리스트 목록

- `playlists/1130_한국사완전정복.yaml`
- `playlists/1130_국중박꿀팁가이드.yaml`
- `playlists/1130_국중박포토스팟.yaml`
- `playlists/test.yaml`
- `playlists/universal_playlists.yaml`

## 주의사항

1. **작업 디렉토리**: 반드시 프로젝트 루트(`/Users/seungmin/Documents/GitHub/audio-guide-genv2`)에서 실행
2. **가상환경**: Python 가상환경이 활성화되어 있어야 함
3. **환경변수**: `.env` 파일에 필요한 API 키들이 설정되어 있어야 함
4. **실행 시간**: 오디오 생성(stage 3)은 시간이 오래 걸릴 수 있음
