# 스크립트 생성 파이프라인 후속 명령

## 📌 배경
- `path_sanitizer` 전환과 legacy 산출물 정리는 완료되었습니다.
- 실제 실행(`dry_run=False`) 시 OpenAI API 연결 실패가 발생하면 즉시 예외로 종료되고, 후속 파이프라인이 중단됩니다.
- dry_run 템플릿은 정상 작동하지만, 정보 파이프라인의 최신 Markdown 내용을 활용한 스크립트 품질 검증이 아직 부족합니다.

## ✅ 수행할 작업
1. **API 연결 실패 대응**
   - `openai.APIConnectionError`, `TimeoutError` 등 네트워크 예외를 잡아 사용자에게 친절한 안내 메시지를 제공하고, 선택적으로 `_generate_dry_run_script` 결과를 반환하도록 fall-back 옵션(`--fallback-dry-run` 등) 도입을 검토하세요.
   - 재시도 로직이 이미 존재하므로, 최종 실패 시에도 로그와 예외 메시지에 "네트워크 환경"/"API 상태" 점검 항목을 명확히 안내합니다.
2. **콘텐츠 품질 검증**
   - LLM 응답을 저장하기 전에 Markdown 섹션(`#`, `##`)이 필수 구조를 만족하는지 검증하고, 비어 있거나 누락된 섹션이 있으면 예외 또는 경고를 발생시키세요.
   - 입력 정보(`info_markdown_path`)에서 핵심 키워드가 스크립트 본문에 포함됐는지 간단한 검사(예: 키워드 존재 여부, 요약 길이)를 추가하여 정보-스크립트 간 일관성을 확인합니다.
3. **통합 테스트 자동화**
   - `tests/` 또는 `scripts/` 디렉토리에 info→script→audio 드라이런 시나리오를 실행하는 테스트 스크립트를 추가하고, 주요 로그/산출물 경로를 검증하세요.
   - dry_run과 실모드(네트워크/키 존재 시) 모두를 다룰 수 있도록 테스트 파라미터를 분리하고, CI에서 dry_run 시나리오는 항상 통과하도록 구성합니다.
4. **문서 및 커뮤니케이션**
   - 위 개선 사항을 적용한 뒤 결과와 잔여 리스크를 `dev-log/[script-agent]YYYY-MM-DD_HH-MM-SS.md` 형식으로 기록하고, 다른 파이프라인 담당자에게 공유하세요.

## 🔎 검증 체크리스트
- 네트워크 장애 시에도 사용자에게 의미 있는 가이드가 제공되고, 옵션에 따라 템플릿 기반 스크립트를 돌려주는지 확인.
- 생성된 Markdown에 모든 필수 섹션(개요/역사/특징/추가 정보/참고 자료)이 포함되어 있는지 자동 검증.
- 동일 키워드로 info→script→audio 파이프라인을 dry_run 실행했을 때 파일 경로와 로그가 일관성 있게 남는지 확인.
- 실제 API 실행 환경에서 스크립트가 정상 생성되면 해당 결과를 `outputs/script/`에 저장하고, 이전 dry_run 산출물과 혼동되지 않도록 로그를 남길 것.

## 🧪 권장 실행 명령
```bash
source .venv/bin/activate
# 네트워크 장애 시 fallback 결과 확인
device_offline=1 python src/pipelines/script_gen.py --keyword "청자 상감운학문 매병" --fallback-dry-run

# 통합 드라이런 시나리오
python scripts/run_pipeline_dry_run.py --keyword "청자 상감운학문 매병"
python scripts/run_pipeline_dry_run.py --keyword "백자 청화 \"산수문\" 항아리"

# 실제 API 테스트 (환경 가능 시)
python src/pipelines/script_gen.py --keyword "청자 상감운학문 매병" --model gpt-4o-mini --temperature 0.7
```

작업 완료 후 변경 사항과 테스트 결과를 메인 리뷰어에게 보고하세요.
