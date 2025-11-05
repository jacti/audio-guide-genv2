# 🎧 오디오 가이드 생성 파이프라인 (v0.1 설계안)

## 개요
이 프로젝트는 문화유산(유물 또는 장소)의 이름을 입력하면 자동으로 오디오 가이드 파일을 생성하는 세 단계 파이프라인으로 구성된다.  
핵심 목표는 **빠른 프로토타입 완성**과 **독립적 확장성**이다.

---

## 🧩 전체 구조

```
[유물 키워드 입력]
      │
      ▼
[Pipeline 1: 정보 검색]
  → LLM 또는 검색 API를 이용해 정리된 md 파일 생성
      │
      ▼
[Pipeline 2: 스크립트 생성]
  → md 파일을 기반으로 오디오 가이드용 스크립트 생성
      │
      ▼
[Pipeline 3: 오디오 변환]
  → 스크립트를 TTS API로 변환하여 mp3 파일 출력
```

---

## 1️⃣ Pipeline 1: 정보 검색 및 요약

**목표:**  
입력된 키워드를 기반으로 문화유산 정보를 Markdown으로 정리한다.

**입력:**  
- 유물 이름 (예: “청자 상감운학문 매병”)

**출력:**  
- `/outputs/info/[keyword].md`

**기능:**  
- GPT 또는 LangChain + Exa.ai 검색을 통해 웹 정보 요약  
- 응답을 Markdown으로 저장  
- 추후 확장: 도메인별 retriever 교체 가능

---

## 2️⃣ Pipeline 2: 스크립트 생성

**목표:**  
1단계 md 파일을 기반으로 오디오가이드용 스크립트를 생성한다.

**입력:**  
- `/outputs/info/[keyword].md`

**출력:**  
- `/outputs/script/[keyword]_script.md`

**LLM 프롬프트 예시:**
```
아래의 유물 정보를 바탕으로 1분 내외의 오디오 가이드 스크립트를 작성해줘.
형식은 친절하고 시각적 이미지를 유도하도록 해줘.
```

**확장:**  
- tone/style 지정, 길이 조절, 세션 구분 등 추가 가능

---

## 3️⃣ Pipeline 3: 오디오 파일 생성

**목표:**  
스크립트를 음성 파일(mp3)로 변환한다.

**입력:**  
- `/outputs/script/[keyword]_script.md`

**출력:**  
- `/outputs/audio/[keyword].mp3`

**예시 코드 (OpenAI TTS):**
```python
from openai import OpenAI
client = OpenAI()
with open(script_path) as f:
    text = f.read()
res = client.audio.speech.create(model="gpt-4o-mini-tts", voice="alloy", input=text)
with open(f"outputs/audio/{keyword}.mp3", "wb") as f:
    f.write(res.audio)
```

---

## 📁 기본 디렉토리 구조

```
script_gen_v2/
├── dev-log/
├── docs/
│   └── plan.md
├── src/
│   ├── main.py
│   └── pipelines/
│       ├── info_retrieval.py
│       ├── script_gen.py
│       └── audio_gen.py
└── outputs/
    ├── info/
    ├── script/
    └── audio/
```

---

## 🚀 실행 예시

```bash
python src/main.py --keyword "청자 상감운학문 매병"
```

**출력 예시:**
```
[1/3] 정보 검색 완료 → outputs/info/청자 상감운학문 매병.md
[2/3] 스크립트 생성 완료 → outputs/script/청자 상감운학문 매병_script.md
[3/3] 오디오 생성 완료 → outputs/audio/청자 상감운학문 매병.mp3
✅ 전체 파이프라인 완료!
```

---

## 🔧 향후 개선 계획 (v0.2 이후)

| 영역 | 개선 내용 | 기대 효과 |
|------|------------|------------|
| 검색 | Exa.ai → Wikipedia → museum.go.kr API 확장 | 더 정확한 정보 |
| 스크립트 | 감성/교육/아동용 tone 추가 | 사용자 맞춤 콘텐츠 |
| 오디오 | BGM 자동 합성 (Suno 등) | 완성도 향상 |
| 관리 | 메타데이터 JSON 기록 | 유물별 검색/관리 용이 |
| UI | Streamlit/Next.js 인터페이스 | 비개발자 접근성 향상 |

---

**요약:**  
현재 버전(v0.1)은 최소 기능 제품(MVP)으로,  
‘입력 → md 정보 → 스크립트 → mp3 오디오’ 전체 흐름을 빠르게 검증하는 데 초점을 둔다.
