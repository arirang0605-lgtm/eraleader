# EraLeader 2_2 / 2_5 / 4_1~4_3 — 두 공급자 최초 원본문서 PIN을 WATCH 게이트에 연결

2026-10-11 KST. 오프라인 로컬 연구용 엄격 게이트. 법적 issuer/share class, 공식 KRX/DART/SEC 원천·타임스탬프, 실제 미래 대장주 발굴 적중률 인증은 아니다. 사용자 D-017 외부 API 연결 후순위, D-021 물리 SSD 재연결·재부팅 최종 단계 유지.

## 보완한 실제 공백

직전 개발의 provider_dual_source_audit 및 provider_candidate_gate는 두 공급자 PIT 내용과 후보 WATCH의 정합성을 확인했지만, 최초 raw staged source 및 claimed source_document_id/witness의 수입 당시 PIN을 필수로 요구하지 않았다. 서로 일치한 정규화 숫자만 가지고 과거에 원본 공시를 확보했었다고 오인할 수 있는 구조였다.

## 이번 변경

- 신규 provider_pair_original_pins.py: 두 공급자의 raw staged manifest와 normalized manifest **각각 2개, 총 4개**를 필수로 받고, 기존 audit_staged_source_lineage의 require_original_first_ingest_pin=true 호출을 재사용. 원본 행/document ID/witness 원문 바이트부터 normalized manifest/JSONL까지 전수 재계산, 최초 SQLite 수입 receipt/원본 SHA PIN, claimed retrieval, 시장/공급자·vintage/bundle SHA와 판단 시각을 교차검증. 하나라도 누락·위변조·후행 수입이면 ValueError로 중단한다.
- audit_provider_source_pair에는 require_original_pins / original_sources 선택 인수를 추가. 기존 기본 동작은 정상 보존. 엄격 옵션에서는 두 공급자의 원본 최초 PIN 모두 통과해야 연구용 pair 비교가 가능하다. 비교 전과 끝에 증빙을 다시 검사하여 감사 중 변경 감지. 보고서는 local_original_first_ingest_pins_required 및 original_source_pair_witness_sha256을 보유하되 publisher_independently_authenticated=false/official leader0.
- audit_candidate_provider_gate는 이 옵션을 전달하고 실제 영구 연구 security_id·업종·실적·기업행동 비교를 그대로 수행. 출처 쌍 digest에는 원본 PIN pair SHA도 결합하여 근거가 다른 WATCH run이 과거의 고정 run ID를 재사용하는 것을 막는다. 엄격 실패 시 신규 WATCH, state_history, joined run, 웹 발행 전에 중단한다.
- offline-integrated 신규 옵트인: --require-provider-original-pins, --provider-staged-manifest-a, --provider-normalized-manifest-a, --provider-staged-manifest-b, --provider-normalized-manifest-b. 기존 provider-ledger-a/b, provider-bundle-a/b도 4개 전부 필요. 모두 제공하지 않거나 source path만 조용히 제출하면 명확히 거부.
- audit-provider-source-pair 직접 CLI도 --require-original-pins 및 --staged-manifest-a/b, --normalized-manifest-a/b 네 파일 모두 있어야 엄격 검사.
- 기존 원본 SQLite/비밀키/시세/소스 JSONL 수정·복제·Git/ZIP 업로드 금지. 파생 JSON만 기존 safe backup 사용; 기존 성능·대시보드/알림/백테스트 모듈 변경 없음.

## 실행 예시 (경로·SHA는 설명용이며 실전 공식 데이터 존재를 주장하지 않음)

~~~bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR --as-of '2026-10-11T18:00:00+09:00' \
  --out output/research \
  --provider-ledger-a output/provider_a/pit.sqlite \
  --provider-bundle-a REAL_IMPORTED_SHA_A \
  --provider-ledger-b output/provider_b/pit.sqlite \
  --provider-bundle-b REAL_IMPORTED_SHA_B \
  --require-provider-original-pins \
  --provider-staged-manifest-a output/provider_a/raw/manifest.json \
  --provider-normalized-manifest-a output/provider_a/normalized/manifest.json \
  --provider-staged-manifest-b output/provider_b/raw/manifest.json \
  --provider-normalized-manifest-b output/provider_b/normalized/manifest.json
~~~

두 first raw-source PIN은 각 공급자 최초 import-provider-pit --staged-manifest 옵션으로 **당시 같은 SQLite transaction에 기록**되어 있어야 한다. 오래전에 normalized-only로 수입한 자료를 오늘 raw 증빙과 함께 제출하더라도 소급 승격은 하지 않는다.

## 검증과 남은 문제

합성 KR/US 별도 source 2개 첫 원시 증빙 import 후 pair/원장/실제 offline-integrated 신규 WATCH 1건 및 로컬 ZIP SHA restore; 한쪽 PIN 없음·삭제, 원문 ID 및 witness 자기 재해시 공격, 시간 역전, A/B manifest 혼용, 부분 옵션, 원본 DB SHA 보존/공식 leader0를 집중 검증한다. 정확한 테스트·Git 증빙은 최신 PROJECT_STATE.md를 기준으로 한다.

한계: 모든 로컬 OS timestamp와 SQLite/SHA 원본은 제3자 공증이 아니므로 실제 공급자 신원·법적 issuer/security class·상폐 현금정산/기업행동·전체 시장 PIT를 확정할 수 없다. 현재 미래 대장주 공식 승격0/실전 precision N/A. 다음은 독립 원문·시장 전체 coverage 확보와 5_5 전향 WATCH→native Top-K→실제 horizon 성숙 outcome 실측. 정상 코드 REWRITE 금지.
