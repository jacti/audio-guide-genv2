# 파이프라인 통합 명령 프롬프트

## 🎯 공통 목표
- `src/utils/path_sanitizer.py`의 `sanitize_keyword_for_path` 및 관련 헬퍼를 사용해 세 파이프라인의 입출력 파일명 규칙을 통일한다.
- 파일명 규칙: 특수문자를 제거하고, 공백은 유지한다. (`청자 상감운학문 매병` → `청자 상감운학문 매병`)
- info → script → audio 순으로 동일한 경로를 공유하도록 수정한다.

---

## 🧠 정보 검색 파이프라인 Agent용 프롬프트
```
당신은 정보 검색 파이프라인 담당 에이전트입니다.
다음 작업을 수행하세요:
1. `src/pipelines/info_retrieval.py`에서 `_sanitize_filename` 구현을 삭제하고 `src/utils/path_sanitizer.py`의 `info_markdown_path`를 사용하도록 리팩터링합니다.
2. `run()` 함수에서 정보 파일 저장 경로를 `info_markdown_path(keyword, output_dir)` 호출 결과로 대체합니다.
3. 필요한 경우 import 구문을 정리하고 주석/문서가 모두 한국어로 유지되는지 확인합니다.
4. `dry_run` 및 실제 실행 경로가 동일하게 동작하는지 로컬 테스트를 수행하세요.
수정 후 변경 사항을 요약하고 잠재적 영향 범위를 보고해주세요.
```

---

## 🖋️ 스크립트 생성 파이프라인 Agent용 프롬프트
```
당신은 스크립트 생성 파이프라인 담당 에이전트입니다.
다음 작업을 수행하세요:
1. `src/pipelines/script_gen.py`에서 파일명 생성 로직(`slug = keyword.replace(...)`)을 제거하고 `src/utils/path_sanitizer.py`의 `info_markdown_path`와 `script_markdown_path`를 사용하도록 수정하세요.
2. 정보 파일 존재 여부 확인, 출력 파일 저장 등 모든 경로 계산이 새 헬퍼 함수를 통해 이루어지는지 검증합니다.
3. dry-run과 실제 실행 코드를 각각 테스트하고, 필요한 경우 로그 메시지를 최신 규칙에 맞게 업데이트하세요.
4. 프롬프트 로딩/생성 로직에는 변경을 가하지 말고, 경로 관련 코드만 정리하세요.
5. 변경 내용을 요약하고 향후 통합 테스트 계획을 제안하세요.
```

---

## 🔊 오디오 생성 파이프라인 Agent용 프롬프트
```
당신은 오디오 생성 파이프라인 담당 에이전트입니다.
다음 작업을 수행하세요:
1. `src/pipelines/audio_gen.py`에서 `_normalize_filename` 및 수동 문자열 결합을 제거하고, `src/utils/path_sanitizer.py`의 `script_markdown_path`와 `audio_output_path`를 사용하세요.
2. 스크립트 파일 읽기, dry_run 더미 파일 생성, 실제 TTS 결과 저장 경로가 모두 공통 헬퍼를 거치도록 정비합니다.
3. CLI 예시, 로그, 에러 메시지가 새로운 규칙을 정확히 설명하는지 확인하고 필요 시 업데이트합니다.
4. dry_run과 실제 실행 흐름을 각각 테스트하고, 통합 단계에서 예상되는 리스크를 보고하세요.
```

---

## 📌 추가 안내
- 모든 코드 변경 시 docstring과 주석을 한국어로 유지하세요.
- 공통 헬퍼 파일(`src/utils/path_sanitizer.py`)에 새로운 요구사항이 생기면 Main 리뷰어와 상의 후 확장합니다.
- 변경 결과는 각자 `dev-log/`에 기록하고 Main 리뷰어에게 알릴 것.
