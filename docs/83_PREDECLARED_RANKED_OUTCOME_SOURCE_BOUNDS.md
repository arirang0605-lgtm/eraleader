# EraLeader 5_3/5_5 — 사전 동결 Top-K 성공기준 원문 SHA 및 후행 결과문서 감사

> 2026-10-11 KST. 실제 미래 대장주를 조기 발굴하는 성능을 **성과를 본 다음 규칙을 바꿔 과장하지 않기 위한** 로컬 연구 검증기. 제공자·문서의 실제 신뢰성 및 과거 데이터 가용성은 제3자 독립 공증되지 않았습니다. 공식 leader 인증0 / 실전 적중률 N/A. 사용자 D-017(API 연결 후순위), D-021(물리 SSD 탈착/맥 재부팅 최종 단계) 유지.

## 기존 정상 코드에서 발견한 실질 검증 공백

`ranked_discovery.py`는 당시 점수와 상위 순위·K·시장·horizon을 후행 수정할 수 없는 파일로 봉인하고 미래 라벨을 별도 읽었지만, `is_future_leader`라는 boolean이 **정확히 어떤 실적/추세/초과수익 조건을 의미하는지** 사전 봉인하지 않았습니다. 따라서 결과를 본 뒤 '대장주 정의'의 조건만 바꿔도 precision@K가 높아지는 선택적 결과 해석이 가능했습니다. 또 기존 순위 평가에는 별도 결과문서의 원문 SHA·문서 내 라벨·공개/수신 주장시각과 top-K를 결합한 정량 검열 기능이 없었습니다.

## 새 계약 — 라벨 이름뿐 아니라 정의 원문 바이트까지 동결

- `src/eraleader/ranked_discovery.py`에 기존 `freeze_ranked_snapshot(...,label_definition_id=None,label_definition_file=None)` 선택 입력을 추가. 기존 **라벨 없는** 동결·평가 파일은 계속 읽을 수 있고, **엄격한 새 결과문서 평가**에는 반드시 `label_definition_id`와 `label_definition_file` 양쪽을 요구.
- 새 `label_definition_file`은 사용자가 **실제 후보를 봉인하기 전** 작성해야 할 UTF-8 JSON. 정확히 `schema_version="eraleader.future_leader_label_definition.v1"`, `label_definition_id`, `market=KR|US`, `horizon_days`, `positive_criterion`, `measurement_method`, `universe_scope`, `delisted_handling` 8개 필드. 모든 설명 필드 필수/비어있지 않음. market/horizon/definition ID를 동결 요구와 교차검증하고 원문 **실제 바이트 SHA256**을 `label_definition_sha256`에 봉인. 한 글자라도 나중에 바뀌면 `strict audit` 거절. 이 정의는 여전히 `자기선언 연구 프로토콜`이며 머신러닝에 정답 기준을 새로 정해주는 것이 아니라 **사전 고정/변경 방지**만 수행.
- 원래의 frozen SHA, top-K order, 실제 OS seal time(이전 snapshot 대비 60분 초과 여부), `timestamp_independently_attested=false`, `source_pit_independently_authenticated=false`를 재검사. **rehashed false retrospective flag**·독립 공증되었다는 허위 필드도 읽기 단계에서 거절.
- `python3 -m eraleader.ranked_discovery freeze --label-definition-id ... --label-definition-file ...` (동결 시 최초 입력); 일단 동결하면 `O_EXCL`로 동일 파일 덮어쓰지 않음. `--prospective-ledger`, `--score-ledger`, `--features-dir`, `--require-native-computation`의 기존 WATCH/점수 재검증 옵션도 변경 없이 함께 사용 가능. 실제 leaderboard/SIGNAL의 재발행은 없음.
- 엄격한 신규 점검 `src/eraleader/ranked_outcome_receipts.py`의 `audit_ranked_outcome_receipts`, 전체 CLI `audit-ranked-outcome-receipts`: `--freeze`, 별도 `--outcomes`, `--receipt-manifest`, `--definition-file`, `--evaluated-at`이 모두 필요. **동결된 정의 원본 bytes SHA** + 순위 파일 frozen digest + outcome JSON 원문 SHA를 함께 묶어 확인. `eraleader.ranked_outcome_receipts.v1` 형태의 receipt에는 `schema_version,market,model_version,label_definition_id,ranked_snapshot_sha256,outcomes_sha256,claims[]` 정확한 필드 필요. 각 claim `security_id,publisher_id_claimed,source_id,file,sha256,published_at,retrieved_at`. `file`은 현재 receipt와 같은 디렉터리의 symlink 없는 안전 basename만 허용, 원본 문서 JSON은 기존 `eraleader.outcome_label_evidence.v1` 형태로 해당 종목의 true/false·mature/available/leader_start 시각과 정확히 일치해야 함. 보고서에 원시 라벨/문서 본문은 절대 복제하지 않음.
- 시간 계약 `mature_at <= published_at <= outcome_available_at <= retrieved_at <= evaluated_at`. 이 계약의 source claim 숫자는 **소스 스스로 선언한 시간**이며 외부 원시 출처/신뢰시각을 증명하지 않음. 실패/누락·원문 SHA/종목/라벨 불일치는 source-corroborated numerator/known denominator에서 **검열**. 본래 `evaluate_ranked_precision_at_k`의 market-local KR/US DST 음성 horizon, positive onset exact clock/lead days 및 정답 누락 censor를 재사용하며 연구용 결과 분류 자체를 바꾸지 않음.
- 연구용 metric: `top_k_selected_count` (사전 동결 순위 실제 K; 누락·검열돼도 축소 금지), `source_document_matched_early_hits`, `source_document_matched_known_failures`, `unknown_or_source_censored_count`, `precision_on_locally_documented_known` (known=0이면 null), `locally_documented_precision_full_k_floor/ceiling` (unknown이 모두 실패/성공일 수 있는 기하학적 범위, **실제 hit-rate 신뢰구간 아님**), `median_locally_documented_lead_days` (source 일치/조기 등장에 한정). 비교할 결과가 전혀 없어도 0% 실전 성과로 선언하지 않고 `null` 표시. 진짜 `recall@K`는 독립적으로 완성된 전체 시장 종목군/후행 결과가 없으므로 `null`.
- `retrospective_freeze`이거나 평가 기준일이 실제 freeze 보다 빠르면 **전향적 성과 분자·분모 계산을 모두 검열**, `CENSORED_RETROSPECTIVE_RANK_SEAL_NOT_PREDICTION`과 local precision null 기록. 특히 오늘 2026-10-11에 2026-01-01 기준 자료를 처음 봉인하고 3월 결과를 입력하면 *미리 예측했던 성적*으로 인정하지 않음.
- 출력 `ranked_outcome_receipts_research.json` 하나만 `local_backup.py` 안전 ZIP allowlist에 추가. 원본 후보 점수, 별도 outcome labels, source 문서, frozen SHA 원본 및 개인키/유료 데이터는 Git·ZIP 반출하지 않음. `PIT 독립인증=false`, `publisher 인증=false`, `real_future_leader_precision=null`, `official_leader_promotions=0`는 모든 반환값에서 고정.

## 실제 실행 계약

아래는 **샘플 명령**입니다. 사용자 로컬에 실제로 `output/live/...` 원천 데이터가 있다는 주장이 아닙니다. 앞 단계에서 확보된 명시적 WATCH/수치점수의 사전등록 원장과 실제 원본 시장 데이터 없이 즉시 실전 성과를 도출할 수 없습니다.

~~~bash
cd /Volumes/T5DATA/eraleader

# 규칙 JSON을 후보 평가 시점 전에 작성/저장한 다음 당일 순위와 함께 봉인
PYTHONPATH=src python3 -m eraleader.ranked_discovery freeze \
  --input output/live/ranked_scores.json \
  --out output/live/frozen_topk.json \
  --market KR --snapshot-at '2026-10-11T15:00:00+09:00' \
  --model-version prereg-v1 --horizon-days 180 --k 20 \
  --label-definition-id LEADER_CRITERION_FIXED_V1 \
  --label-definition-file output/live/leader_rule.json

# 미래에 180일 경과·실제 분류가 가능해진 뒤 별도 결과자료만 입력
PYTHONPATH=src python3 -m eraleader audit-ranked-outcome-receipts \
  --freeze output/live/frozen_topk.json \
  --definition-file output/live/leader_rule.json \
  --outcomes output/live/future_outcomes.json \
  --receipt-manifest output/live/label_source_receipts.json \
  --evaluated-at '2027-04-30T18:00:00+09:00' \
  --out output/live/derived_reports
~~~

현재 날짜 2026-10-11 기준 미래 날짜로 위 평가 명령을 **지금 실행하면 정상적으로 차단**됩니다.

## 검증 및 한계

`tests/test_ranked_outcome_receipts.py` 신규: 사전 고정 K/market/horizon/model/label ID/정의 원문 bytes SHA, 정상 조기·음성·미성숙/누락/불일치/반복·unknown labels, claimed published/retrieved 시간순서, source 문서 일치/거짓 재해시 SHA, symlink/traversal·빈 파일, 과거 소급 봉인/독립 시각 공증 flag 재해시 조작, KR/US 기존 DST 평가 방식 재사용, CLI·파생 JSON ZIP/복원. `tests/test_ranked_discovery.py` 등 기존 랭킹 평가/원장 기반 freeze preflight의 정상 경로도 기존 그대로 PASS 확인.

**한계**: label definition JSON은 사용자/소스가 정의한 규칙을 바이트 동결할 뿐, 알고리즘이 실제 리더 기준이 옳은지 판정한 것이 아닙니다. 리더 label 문서·receipt 게시일시/원천 공급자 주장은 로컬 자기선언이고 서로 다른 실제 공식 업체 서명 및 상폐현금/재무 PIT 완전성/공식 업종 장기 투자수익 지표는 아직 미확보. 결과가 수치로 보여도 **실제 대장주 적중률을 인증하지 않습니다.** 향후 공급자 원천 API 연결(D-017) 뒤에 실제 사전등록 성숙 결과 수집/검증, 물리 SSD 탈착/재부팅(D-021) 최종 검수 필요.
