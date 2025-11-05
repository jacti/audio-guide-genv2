# 스크립트 생성 파이프라인 후속 명령

## 📌 배경
- 커밋 `c992fff9ad9e2d29aa6e0aa397bd37fb7921db9a`에서 `path_sanitizer` 헬퍼를 도입하면서, 산출물 파일명이 `청자 상감운학문 매병_script.md`처럼 공백을 유지하는 형태로 변경되었습니다.
- 오디오 생성 파이프라인은 아직 언더스코어 기반 파일명(`청자_상감운학문_매병_script.md`)을 기대하고 있어 전체 파이프라인 실행 시 3단계에서 실패합니다.

## ✅ 수행할 작업
1. **호환성 유지 장치 추가**
   - `src/pipelines/script_gen.py`에서 주 산출물은 새 규칙(공백 유지)으로 저장하되, 오디오 파이프라인이 참조할 수 있도록 legacy 파일명(언더스코어 버전)도 동일 내용으로 함께 저장하세요.
   - 두 파일 저장이 모두 성공했는지 로깅을 통해 확인합니다.
2. **교차 테스트**
   - 동일 키워드로 `--dry-run` 및 실동 모드 각각 실행 후, 오디오 파이프라인까지 연속 실행해 오류가 없는지 검증합니다.
   - 테스트 키워드 예시: `청자 상감운학문 매병`, `백자 청화 "산수문" 항아리`.
3. **정리 계획 수립**
   - 오디오 파이프라인이 `path_sanitizer` 기반으로 업데이트되면 legacy 파일 저장 로직을 제거할 수 있도록 dev-log에 메모를 남기세요.
4. **커뮤니케이션**
   - 작업 완료 후 dev-log에 결과를 기록하고, 오디오 파이프라인 담당 에이전트가 언제 헬퍼 기반으로 전환할 수 있는지 협의 일정을 제안하세요.

## 🔎 검증 체크리스트
- `outputs/script/`에 공백 버전과 언더스코어 버전이 동시에 생성되는지 확인.
- 오디오 파이프라인 실행 시 `FileNotFoundError`가 더 이상 발생하지 않는지 확인.
- 로그 메시지가 한국어로 유지되고 변경 사항이 명확히 드러나는지 확인.

## 🧪 권장 실행 명령
```bash
source .venv/bin/activate
python src/pipelines/script_gen.py --keyword "청자 상감운학문 매병" --dry-run
python src/pipelines/audio_gen.py --keyword "청자 상감운학문 매병" --dry-run
python src/pipelines/script_gen.py --keyword "백자 청화 \"산수문\" 항아리" --dry-run
python src/pipelines/audio_gen.py --keyword "백자 청화 \"산수문\" 항아리" --dry-run
```

작업 완료 후 변경 사항과 테스트 결과를 main 리뷰어에게 공유해주세요.
