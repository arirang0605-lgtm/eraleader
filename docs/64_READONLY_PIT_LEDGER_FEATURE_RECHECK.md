# 2_3 / 2_5 / 3_5 — 원본 PIT SQLite ↔ 파생 랭킹 피처 엄격 재계산

> 2026-10-10. API 연결 없이 기존 오프라인 원장을 읽기 전용으로 재계산하는 **연구 무결성 방어**입니다. 공식 역사적 PIT/기업행동/상폐·대장주 적중률 인증이 아닙니다.

## 보완한 문제

- 기존 prepare-rank-features는 offline-features JSON을 자체 기준으로 SHA256 기록했지만, JSON에 수치·티커를 조작한 뒤 새 SHA256을 계산하면 원본 SQLite와 달라도 점수 입력이 생성될 수 있었습니다.
- `--offline-ledger <existing offline.sqlite>`를 명시하면 기존 `OfflineLedger.open_readonly`가 **SQLite mode=ro / PRAGMA query_only=ON**으로 연 뒤, 해당 시장과 판단 시각의 `OfflineLedger.snapshot()`을 재생하고 `financial_snapshot()`을 처음부터 재계산합니다. 재계산된 **전체** 산업·기업·공시기간·품질 스냅샷과 제출 JSON이 한 글자라도 다른 경우 파일 출력 전에 차단합니다.
- 이 감사는 `snapshot()`의 당시 알려진 재무·산업·종목 기록만 보므로 `available_at > decision_at`인 늦은 원본 정정이 과거 결과를 변조해서는 안 됩니다. 반면 `decision_at` 이전에 공개된 재수정이 기존 제출본과 달라지면 불일치로 차단합니다.
- 원본은 새 테이블을 만들지 않고 쿼리만 하며, 기존 발표시각/기업ID/시장/수치/품질 플래그가 맞아야 합니다. 없는 원장·심볼릭 링크·다른 시장 원장도 거절합니다. 원장 변경·기존 WATCH·점수 원장 덮어쓰기는 없습니다.
- 새 결과 `_meta/source_manifest.json`에는 `recomputed_from_readonly_offline_ledger=true`와 원장 재계산 스냅샷 SHA256이 기록됩니다. **원본 파일 바이트/개인정보/키는 넣지 않습니다.** CLI 응답에도 해당 검증 여부가 표시됩니다.
- 기존 `--offline-ledger` 생략 방식은 호환성을 위해 남겨 두되 `recomputed_from_readonly_offline_ledger=false`로 명시합니다. 실제 미래 후보 신규 연구 점수에는 **엄격 원장 대조 옵션 권장**.

## 사용 예제

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader prepare-rank-features \
  --offline output/offline_kr_features.json \
  --price output/kr_latest.json \
  --offline-ledger output/offline.sqlite \
  --features-dir output/strict_rank_features_kr \
  --model-version research-native-v1 --min-peers 3
PYTHONPATH=src python3 -m pytest tests/test_rank_feature_ledger.py -q
~~~

## 검증 범위와 분리된 한계

- 집중 합성 회귀: 원장 read-only, 정상 동일 계산, 재해시된 매출/산업/종목·티커·기간·원천 provenance 조작, 새 미래정정/지난 정정 시차, 누락·심볼릭 링크 SQLite, KR↔US 혼용, CLI 옵션, 기존 비엄격 호환.
- 대조의 **진실 기준은 여전히 사용자가 로컬에 import한 데이터**입니다. 이 자료의 제3자 공시 발표시각, 공식 기업동일성, 전체 상폐/조정주가/현금정산, 데이터 누락 여부를 독립 입증하지 않습니다.
- 가격 JSON은 기존 `run_id` 내부 자기검사에 의존하며 **실제 가격 캐시 바이트에 대한 제3자 원천 교차검증이 아닙니다**. 추가 2_2/2_5 작업에서 별도 검증이 필요합니다.
- 실제 외부 API 연결 D-017과 물리 SSD 탈착/재부팅 D-021은 이후 최종 단계까지 보류합니다. 테스트 결과 및 Git SHA는 PROJECT_STATE.md 맨 끝을 우선합니다.
