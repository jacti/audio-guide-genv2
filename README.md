# Audio Guide Pipeline – Command Reference

이 문서는 파이프라인 사용자가 각 단계를 개별 실행하거나 `src/main.py`로 통합 실행할 때 필요한 CLI 명령어를 빠르게 찾을 수 있도록 정리한 안내서입니다.

## 1. 실행 전 준비
1. **가상환경 및 의존성 설치**
   ```bash
   ./setup-venv.sh
   source .venv/bin/activate
   ```
2. **환경변수(.env) 구성** – 최소 `OPENAI_API_KEY`를 정의해야 하며, 없으면 실행 전에 생성해야 합니다.

## 2. Pipeline 1 – 정보 검색 (`info_retrieval`)
문화유산 키워드를 입력하면 `/outputs/info/{keyword}.md`를 생성합니다.

```bash
python -m src.pipelines.info_retrieval --keyword "청자 상감운학문 매병"
```
주요 옵션
- `--model gpt-4o` : 사용할 OpenAI 모델 지정 (기본 `gpt-4.1`).
- `--output-dir outputs/custom-info` : 결과 저장 경로 변경.
- `--dry-run` : API 호출 없이 목업 Markdown 생성.

## 3. Pipeline 2 – 스크립트 생성 (`script_gen`)
정보 Markdown을 읽어 `/outputs/script/{keyword}_script.md`를 생성합니다.

```bash
python -m src.pipelines.script_gen --keyword "청자 상감운학문 매병" --prompt-version v1
```
주요 옵션
- `--prompt-version version` : 사용할 프롬프트 템플릿.
- `--info-dir outputs/info` / `--output-dir outputs/script` : 입·출력 디렉터리 지정.
- `--model gpt-4o-mini` , `--temperature 0.7` : LLM 파라미터 조정.
- `--dry-run` : API 호출 대신 고정 스크립트 예시 생성.
- `--list-prompts` : 사용 가능한 프롬프트 목록만 출력.

## 4. Pipeline 3 – 오디오 생성 (`audio_gen`)
스크립트를 읽어 `/outputs/audio/{keyword}.mp3`를 생성합니다.

```bash
python -m src.pipelines.audio_gen --keyword "청자 상감운학문 매병" --voice alloy
```
주요 옵션
- `--script-dir outputs/script` / `--output-dir outputs/audio` : 입·출력 경로 지정.
- `--model gpt-4o-mini-tts` , `--voice alloy|nova|...` , `--speed 1.0` : TTS 설정.
- `--max-retries 8 --initial-wait 1.0 --max-wait 60.0` : 지수 백오프 파라미터.
- `--dry-run` : 더미 MP3(112 bytes)를 생성하여 흐름만 검증.

## 5. 통합 실행 – `src/main.py`
세 파이프라인을 순차 실행해 최종 MP3까지 생성합니다.

```bash
python -m src.main --keyword "청자 상감운학문 매병"
```
자주 사용하는 옵션
- `--dry-run` : 세 단계 모두 목업 데이터를 생성.
- `--model gpt-4o-mini` : info/script 단계 공통 모델 지정.
- `--prompt-version v1|v2` : 스크립트 프롬프트 선택.
- `--voice alloy --speed 1.0` : 오디오 파라미터 조정.
- `--temperature 0.7` : 스크립트 단계 온도.
- `--max-retries 8` : 오디오 단계 재시도 횟수.

### 예시 – 커스텀 설정
```bash
python -m src.main --keyword "석굴암" \
  --model gpt-4o \
  --prompt-version v2 \
  --voice nova \
  --speed 1.1 \
  --temperature 0.6
```

## 6. 배치 실행 (트랙 기반) – `src/batch_runner.py`
여러 오디오 가이드를 하나의 트랙으로 묶어 일괄 생성합니다.

### 트랙(Track)이란?
주제나 카테고리로 묶인 여러 오디오 파일의 모음입니다.
- 예: "박물관 이용 가이드" 트랙에 "박물관 소개", "전시관 안내", "앱 사용법" 3개 파일 포함
- 트랙별로 독립적인 디렉토리 구조 유지
- YAML 설정 파일로 한 번에 관리

### 6.1. YAML 설정 파일 작성

`tracks/` 디렉토리에 YAML 파일을 생성합니다. (`tracks/sample_track.yaml` 참고)

```yaml
# 트랙 기본 정보
track_name: "꿀팁 가이드"
description: "박물관 이용에 도움이 되는 필수 가이드"

# 공통 설정 (모든 파일에 적용, 개별 오버라이드 가능)
defaults:
  model: "gpt-4.1"
  prompt_version: "v2-tts"
  voice: "alloy"
  speed: 1.0
  temperature: 0.7
  dry_run: false

# 생성할 파일 목록
files:
  - output_name: "1_박물관소개"
    keyword: "국립중앙박물관 역사와 위치 소개"

  - output_name: "2_전시관소개"
    keyword: "국립중앙박물관 전시관 구성과 주요 관 소개"

  - output_name: "3_앱사용꿀팁"
    keyword: "국립중앙박물관 앱 사용법과 오디오가이드 이용법"
    voice: "nova"      # 이 파일만 다른 목소리 사용
    temperature: 0.8   # 이 파일만 다른 온도 설정
```

**필수 필드:**
- `track_name`: 트랙 이름
- `files`: 파일 목록 (각 항목은 `output_name`, `keyword` 필수)

**선택 필드:**
- `description`: 트랙 설명
- `metadata`: 작성자, 버전, 태그 등
- `defaults`: 공통 설정 (개별 파일에서 오버라이드 가능)

### 6.2. 배치 실행 명령어

```bash
# 기본 실행
python -m src.batch_runner --track-file tracks/sample_track.yaml

# Dry-run 모드 (API 호출 없이 테스트)
python -m src.batch_runner --track-file tracks/my_track.yaml --dry-run
```

### 6.3. 출력 디렉토리 구조

```
outputs/tracks/꿀팁_가이드/
├── info/
│   ├── 1_박물관소개.md
│   ├── 2_전시관소개.md
│   └── 3_앱사용꿀팁.md
├── script/
│   ├── 1_박물관소개_script.md
│   ├── 2_전시관소개_script.md
│   └── 3_앱사용꿀팁_script.md
├── audio/                    # 최종 결과물
│   ├── 1_박물관소개.mp3
│   ├── 2_전시관소개.mp3
│   └── 3_앱사용꿀팁.mp3
└── batch_report.json         # 실행 결과 리포트
```

### 6.4. 실행 결과 리포트

배치 실행 완료 후 `batch_report.json`이 자동 생성됩니다:

```json
{
  "track_name": "꿀팁 가이드",
  "started_at": "2025-11-07T14:30:00",
  "completed_at": "2025-11-07T14:35:42",
  "duration_seconds": 342,
  "total_files": 3,
  "successful": 3,
  "failed": 0,
  "files": [
    {
      "output_name": "1_박물관소개",
      "keyword": "국립중앙박물관 역사와 위치 소개",
      "status": "success",
      "audio_path": "outputs/tracks/꿀팁_가이드/audio/1_박물관소개.mp3"
    }
    // ...
  ]
}
```

### 6.5. 사용 시나리오

```bash
# 1. 샘플 파일 복사
cp tracks/sample_track.yaml tracks/cultural_heritage.yaml

# 2. YAML 파일 편집 (원하는 트랙 구성)
# vim tracks/cultural_heritage.yaml

# 3. Dry-run으로 테스트
python -m src.batch_runner --track-file tracks/cultural_heritage.yaml --dry-run

# 4. 실제 실행
python -m src.batch_runner --track-file tracks/cultural_heritage.yaml

# 5. 결과 확인
cat outputs/tracks/[트랙명]/batch_report.json
open outputs/tracks/[트랙명]/audio/
```

### 6.6. 에러 처리

- **순차 실행**: 파일을 하나씩 처리하여 안정성 확보
- **즉시 중단**: 에러 발생 시 전체 배치 중단
- **부분 리포트**: 실패 지점까지의 결과를 리포트에 기록
- **상세 로그**: 어느 파일의 어느 단계에서 실패했는지 명확히 표시

## 7. 출력 파일 위치

**개별 실행 시:**
- 정보: `outputs/info/{keyword}.md`
- 스크립트: `outputs/script/{keyword}_script.md`
- 오디오: `outputs/audio/{keyword}.mp3`

**배치 실행 시:**
- 트랙 루트: `outputs/tracks/{track_name}/`
- 정보: `outputs/tracks/{track_name}/info/{output_name}.md`
- 스크립트: `outputs/tracks/{track_name}/script/{output_name}_script.md`
- 오디오: `outputs/tracks/{track_name}/audio/{output_name}.mp3`
- 리포트: `outputs/tracks/{track_name}/batch_report.json`

각 단계는 실행 시 파일 경로를 로그로 안내하므로, 완료 후 바로 내용을 확인할 수 있습니다.

---

필요한 추가 지시는 항상 `docs/commands/` 내 최신 YAML 명령서를 참고해 주세요.
