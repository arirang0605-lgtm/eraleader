# EraLeader 5_5 — 전향 Top-K 만기 결과증빙 전수 후속점검

> 2026-10-12 KST. `docs/95`, `docs/96`, `docs/98`, `docs/99`의 이미 정상 동작하는 prospective census/영수증 SHA index/native WATCH first-score 감사기를 **재사용**. 외부 API·실제 메시지·실주문·원시 시세 변경 **0**. 코호트 분모 변경이나 소급 성과 추정 금지.

## 왜 필요했는가

기존 `prospective_census_research.json`은 전체 원래 K, 미성숙/누락/검열 집계와 local accuracy bounds를 집계하지만, **어느 코호트가 언제 만기되었고 어떤 종류의 독립 outcome/receipt 후속자료가 빠졌는지** 실행자가 바로 알기 어려웠다. 미래 예측의 실전 적중 검증을 위해 결과가 성숙하는 시점 이후 증빙 누락을 전수 추적하는 **후속 수집 작업표**를 구현했다. 데이터가 없거나 공급자가 누구인지 검증되지 않았으면 성공/실패로 판정하지 않는다.

## 기능 (5_5)

- 신규 `src/eraleader/prospective_due_followups.py`: `audit_prospective_due_followups(..., evaluated_at, native_config=None)`. **반드시 기존 first-write SQLite SHA receipt index 검증**. 기존 native 필수 marker가 있으면 사전 WATCH 양성원장·첫 계산점수·네 요소 feature 원본 SHA 등을 전수 확인하는 **정확한 native config 없이는 평가 거부**. 일반 무인증 census로 약화 실행 불허.
- 모든 first-written `census_*.json`을 읽어 원래 market/model/as-of/freeze SHA/horizon/label rule SHA/Top-K 원분모가 변하지 않았는지 재검증. 그 당시 KR `Asia/Seoul`, 미국 `America/New_York` 시장 현지 달력 기준 `horizon_due_utc`로 **기간 미도래 vs 도래**를 정확히 구분한다(US DST 포함). 출력 시 원래 freeze/source/issuer/ticker 경로와 실물 종목ID를 노출하지 않고 manifest SHA 기반의 별도 `REG-...` 참조ID + 코호트 순서로 연결한다.
- 만기 상태: `AWAITING_HORIZON`, `AWAITING_HORIZON_WITH_LOCAL_PAIR`(만기 전 claimed source가 있는 경우도 조기 성공 확정 금지), `DUE_BOTH_SOURCES_MISSING`, `DUE_OUTCOMES_MISSING`, `DUE_RECEIPTS_MISSING`, `DUE_PAIRED_CENSORED`(양쪽 원본은 존재하나 문서누락/미확인/충돌), `DUE_PAIRED_LOCALLY_KNOWN_NOT_CERTIFIED`. **만기+미확인** 코호트 수/원 K 합/검열 K를 산출하며 기록된 누락·검열을 실패나 실전 precision으로 바꾸지 않는다. 쌍으로 존재할 때는 기존 `audit_ranked_outcome_receipts` 원천 영수증 SHA·claim time 검증을 재사용. 전체 hit/known-failure/unknown 합이 기존 indexed/native 전수평가와 정확히 같아야 한다.
- 원본 및 입력 문서 위·변조, 미인덱스 registry/삭제·누락 항목/분모변경/미등록 native evidence/결과파일 심볼릭링크/중간 변경 모두 fail-closed. 감사 전후 indexed/native 재검증 2회 및 manifest/frozen/definition/outcome/receipt SHA 재확인. 경고 화면은 기존 원본 파일을 쓰거나 외부 실제 서비스를 호출하지 않는다.
- 전체 Top-K 집계는 **모든 코호트** 기준. 화면/JSON 상세 열은 우선순위(누락·검열 먼저) 상위 500개까지만 노출하며 초과 여부와 실제 전수분모를 별도로 명시. 원시 issuer/security/class/성능 데이터가 공인 PIT로 승격되지 않는다.

## 통합 명령과 산출물

기존 `scripts/run_prospective_census.py audit`의 추가 선택 `--due-followups`만 변경. **반드시 `--receipt-index`**, native 첫등록이면 `--native-evidence-config <현재 local JSON>` 필수. 무옵션으로 기존 audit/register stdout·JSON·원장 동작은 **그대로 유지**. 추가 옵션 시 기존 `prospective_census_research.json`은 기존 JSON 계약 그대로 출력하고, **별도** `prospective_due_followups_research.json`·`site/prospective_due_followups.html`도 원자적 작성. opt-in stdout은 `census_audit` 및 `due_followups` 두 개의 안전 요약만 포함한다.

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 scripts/run_prospective_census.py audit \
  --registry-dir output/local_census/first_write_registry \
  --receipt-index \
  --evaluated-at '2026-10-12T07:00:00+09:00' \
  --due-followups \
  --out output/local_census/due_followups_derived

# 기존 저장소가 native-mode면 동일 명령에:
# --native-evidence-config output/local_census/local_native_proofs.json
# 파일들은 예시로 실제 존재를 의미하지 않는다.

PYTHONPATH=src python3 -m pytest tests/test_prospective_due_followups.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
```

`src/eraleader/local_backup.py`의 allowlist에 신규 파생 JSON **1개만** 추가; `site/*.html`은 기존 안전 허용을 재사용한다. `create_backup` (SQLite 온라인 백업/ZIP SHA) + `verify_backup` + 새 폴더 `restore_backup`으로 원본 증거·시세 파일을 포함하지 않고 파생 JSON/HTML만 보관·복원 가능.

## 실제 Mac 로컬 실행 / 한계

- **당일 Mac OS clock**의 기존 2026-10-11 합성 KR+US first-write indexed registry로 opt-in CLI: 최초 원장 2개 / 코호트2 / 원래 K4 / 만기 전2 / 신규 후속조치0 / 실전 발송·API0.
- **기존 과거 날짜 합성 KR+US 원장**: 원장2개 / K6 / 만기2 / source pair locally matched지만 검열이 남은 코호트2 / 만기 후속조치2 / 검열 K2 / 실전 발송·API0. 과거의 합성 실적 결과를 공인 정확도로 표기하지 않았다.
- 실제 미래 처음 발견한 종목의 수개월 뒤 검증 결과는 아직 **자연적으로 도래하지 않았거나 독립 근거 미확보**. 공식 issuer/class/상폐 cash/공시 최초 공개·수집시각/과거 전체 universe PIT는 D-017 API+원천 증빙 연결 전 인증할 수 없다. 이 도구의 주된 목적은 미수집 성적표를 0 또는 성공으로 속이지 않고 운영상 누락을 노출하는 것. 외부 시각 공증/원장과 인덱스 동시 삭제/재위조, 독립 금융정보 발행인 신원 검증은 불가. D-021 물리 SSD 분리/재연결·재부팅은 마지막 단계.
