# 스크립트 생성 프롬프트 관리 가이드

## 개요

이 디렉토리는 오디오 가이드 스크립트 생성을 위한 프롬프트 템플릿을 관리합니다.
파일명 기반 버전 관리 방식을 사용하여 단순하고 직관적입니다.

## 디렉토리 구조

```
prompts/script_generation/
├── README.md    # 이 파일
├── v1.yaml      # 기본 친절한 톤 (기본값)
├── v2.yaml      # 교육적 톤
└── v*.yaml      # 추가 버전들...
```

## 프롬프트 템플릿 형식

각 YAML 파일은 다음 구조를 따릅니다:

```yaml
# v1: 프롬프트 설명 (파일 첫 줄에 주석으로 설명)

name: "프롬프트 이름"
description: "프롬프트 설명"
tags:
  - tag1
  - tag2

parameters:
  duration_minutes: 1.0    # 기본 파라미터
  tone: "friendly"
  style: "visual_imagery"

system_prompt: |
  시스템 프롬프트 내용...
  LLM의 역할과 행동 방식을 정의합니다.

user_prompt_template: |
  유저 프롬프트 템플릿...
  {info_content}, {duration_minutes} 등의 변수를 사용할 수 있습니다.
```

## 새 프롬프트 버전 추가하기

### 1. 새 YAML 파일 생성

```bash
# v3.yaml 생성 예시
cp v1.yaml v3.yaml
```

### 2. 내용 수정

```yaml
# v3: 아동용 오디오 가이드 (쉽고 재미있는 톤)

name: "아동용 오디오 가이드"
description: "초등학생을 위한 쉽고 재미있는 스크립트"
tags:
  - children
  - fun
  - educational

parameters:
  duration_minutes: 1.0
  tone: "playful"
  style: "storytelling"

system_prompt: |
  당신은 어린이를 위한 문화유산 이야기꾼입니다.
  쉬운 단어와 재미있는 비유로 설명하며,
  호기심을 자극하는 질문을 던집니다.

user_prompt_template: |
  아래 정보를 바탕으로 초등학생이 이해하기 쉬운 {duration_minutes}분 스크립트를 작성해주세요.

  **스타일:**
  - 쉬운 단어 사용
  - 재미있는 비유와 예시
  - 질문 형식으로 호기심 유발

  {info_content}
```

### 3. 테스트

```bash
# 프롬프트 목록 확인
python3 src/pipelines/script_gen.py --list-prompts

# dry-run으로 테스트
python3 src/pipelines/script_gen.py --keyword "테스트" --prompt-version v3 --dry-run
```

## 사용 방법

### CLI에서 사용

```bash
# 기본 버전 (v1) 사용
python3 src/pipelines/script_gen.py --keyword "청자 상감운학문 매병"

# 특정 버전 지정
python3 src/pipelines/script_gen.py --keyword "청자 상감운학문 매병" --prompt-version v2

# 사용 가능한 버전 확인
python3 src/pipelines/script_gen.py --list-prompts
```

### Python 코드에서 사용

```python
from src.utils.prompt_loader import load_prompt

# 프롬프트 로드
template = load_prompt("v1")

# 프롬프트 생성
user_prompt = template.format_user_prompt(
    info_content="유물 정보...",
    duration_minutes=1.5
)

# 시스템 프롬프트 접근
system_prompt = template.system_prompt
```

## 프롬프트 엔지니어링 팁

### 1. 명확한 구조 제시

```yaml
user_prompt_template: |
  **구조:**
  1. 인사 (10초)
  2. 본문 (40초)
  3. 마무리 (10초)
```

### 2. 예시 제공

```yaml
user_prompt_template: |
  **감정 힌트 사용 예시:**
  - (따뜻하게) 이 유물은...
  - (천천히) 눈으로 보면...
```

### 3. 제약사항 명시

```yaml
user_prompt_template: |
  **제약사항:**
  - 전문 용어는 쉽게 풀어쓰기
  - 문장은 15단어 이내로 간결하게
  - Markdown 형식 엄수
```

### 4. 파라미터 활용

```yaml
parameters:
  duration_minutes: 1.0
  target_age: "성인"
  difficulty: "중급"

user_prompt_template: |
  {target_age} 대상, {difficulty} 수준으로
  약 {duration_minutes}분 분량의 스크립트 작성
```

## 버전 관리 권장사항

1. **기본 버전 유지**: v1은 안정적인 기본 버전으로 유지
2. **실험적 버전**: 새로운 시도는 v99 등 높은 번호로 시작
3. **검증 후 정식화**: 효과가 좋으면 v3, v4 등으로 정식화
4. **주석 활용**: 파일 첫 줄에 버전 의도를 명확히 기록

## 트러블슈팅

### 프롬프트가 로드되지 않을 때

```bash
# 1. 파일 존재 확인
ls -la prompts/script_generation/

# 2. YAML 문법 검증
python3 -c "import yaml; yaml.safe_load(open('prompts/script_generation/v1.yaml'))"
```

### 템플릿 변수 오류

```python
# 사용 가능한 변수 확인
template = load_prompt("v1")
print(template.parameters)  # 기본 파라미터 출력
```

## 버전 히스토리

| 버전 | 날짜 | 설명 |
|------|------|------|
| v1   | 2025-01-05 | 기본 친절한 톤 |
| v2   | 2025-01-05 | 교육적 톤 |

---

**작성일**: 2025-01-05
**관리자**: Script Gen Pipeline
