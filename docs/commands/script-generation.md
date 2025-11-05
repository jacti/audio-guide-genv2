# 스크립트 생성 파이프라인 후속 명령

## 📌 배경
- 커밋 `c992fff9ad9e2d29aa6e0aa397bd37fb7921db9a`에서 `path_sanitizer` 헬퍼를 도입하면서 산출물 파일명이 공백을 유지하는 형태로 정규화되었습니다.
- 오디오 생성 파이프라인도 동일 헬퍼(`script_markdown_path`, `audio_output_path`)를 사용하도록 업데이트되었으므로, 임시 호환성(legacy 언더스코어 파일) 로직을 정리할 수 있습니다.

## ✅ 수행할 작업
1. **임시 호환성 로직 제거**
   - `src/pipelines/script_gen.py`에 legacy 파일명을 병행 저장하던 코드가 남아 있다면 삭제하고, `script_markdown_path` 기준 단일 파일만 생성하도록 유지하세요.
   - 기존 테스트 산출물 중 언더스코어 버전(`*_script.md`)이 남아 있으면 정리하거나 `.gitignore`를 통해 혼선을 방지합니다.
2. **경로 헬퍼 활용 점검**
   - `info_markdown_path`와 `script_markdown_path` 사용 위치를 재검토하여, 하드코딩된 경로 조합이 남아 있지 않은지 확인하세요.
   - 필요 시 주석/로그에 “공백 유지” 규칙을 명확히 기재합니다.
3. **교차 테스트**
   - 정보 → 스크립트 → 오디오 파이프라인을 연속 실행하여 파일이 순차적으로 연결되는지 확인합니다.
   - dry-run과 실제 모드 각각에서 동일 키워드(`청자 상감운학문 매병`, `백자 청화 "산수문" 항아리`)로 테스트하고, 파일 경로를 출력 로그에서 검증하세요.
4. **출력 디렉토리 정리**
   - `outputs/script/` 내에 과거 규칙으로 생성된 파일이 있다면 보관 경로를 바꾸거나 삭제하여 새 규칙만 남도록 정리하고, dev-log에 조치 내용을 기록하세요.
5. **커뮤니케이션**
   - 작업 완료 후 dev-log에 테스트 결과와 남은 리스크를 요약하고, 다른 파이프라인 담당자와 공유할 필요 사항이 있는지 확인합니다.

## 🔎 검증 체크리스트
- `outputs/info/`, `outputs/script/`, `outputs/audio/`가 모두 동일 키워드로 공백을 유지한 파일명을 사용하고 있는지.
- 로그에 출력되는 경로가 `path_sanitizer` 규칙과 일치하는지.
- dry-run/실모드 모두에서 예외가 발생하지 않고, 오디오 단계까지 실행되는지.

## 🧪 권장 실행 명령
```bash
source .venv/bin/activate
python src/pipelines/info_retrieval.py --keyword "청자 상감운학문 매병" --dry-run
python src/pipelines/script_gen.py --keyword "청자 상감운학문 매병" --dry-run
python src/pipelines/audio_gen.py --keyword "청자 상감운학문 매병" --dry-run

python src/pipelines/info_retrieval.py --keyword "백자 청화 \"산수문\" 항아리" --dry-run
python src/pipelines/script_gen.py --keyword "백자 청화 \"산수문\" 항아리" --dry-run
python src/pipelines/audio_gen.py --keyword "백자 청화 \"산수문\" 항아리" --dry-run
```

작업 완료 후 변경 사항과 테스트 결과를 main 리뷰어에게 공유해주세요.
