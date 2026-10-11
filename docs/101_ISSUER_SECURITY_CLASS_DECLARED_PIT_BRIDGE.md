# EraLeader 2_2 / 2_5 — KR·US 법인ID / 주식클래스 선언 PIT 교차 대조

> 2026-10-12 KST. **공인 KRX/DART/SEC 원본 API 사용 전** 로컬 두 출처의 회사·증권 클래스 연결을 실제 코드로 확인한다. 일치하는 원천 코드나 두 개의 서로 다른 *주장* 발행기관 이름은 공식 법적 신원·첫 게시시각을 인증하지 않는다. 실전 대장주 적중률 N/A / 공식 확정 0.

## 실제 이어서 개발한 기능

기존 `provider_export_normalizer.py`는 원천 staged membership을 `KR:CORP<8digits>:ISSUE:<issue_uid>` 및 `US:CIK<10digits>:CLASS:<share_class_uid>`라는 **회사와 증권 클래스를 별도 보존하는** 중립 키로 변환했다. 기존 `issuer_lineage.py`는 별도 원천의 개정·상폐·티커 재사용을 조사했다. 하지만 두 로컬 원천 사이에서 **당시 같은 법인/증권클래스·상장기간·ticker가 전부 일치하는지** 교차 검증하는 실행 연결이 없었다. 티커만 같은 다른 법인과 클래스에 역사를 잘못 합칠 위험을 차단하기 위한 최소 읽기 전용 연결을 구현한다.

- 신규 `src/eraleader/issuer_class_bridge.py`의 `audit_staged_issuer_class(staged_manifest,issuer_lineage_file,decision_at,clock=None)`. 기존 `provider_export_normalizer._preflight`로 staged 원시 JSONL/manifest 원문 SHA·중복·법인/클래스·발표시각·해당 source ID·공시 문서 식별자를 모두 감사 후 normalized `membership/actions`을 **저장 없이 재사용**. 별도 `audit_issuer_lineage`로 원천 전체 기업계보 개정/revision/종료 이벤트·시점·ticker 충돌 검증.
- 신호일 `decision_at`은 KR Asia/Seoul, US America/New_York의 **시장 현지 거래일**로 해석하며 UTC 시각 차단도 수행. 두 공급자의 주장 `retrieved_at` 중 하나라도 결정 이후이면 matched=0의 `CENSORED_STAGED_ISSUER_CLASS_SOURCE_NOT_INDEPENDENT_OR_PIT`. 같은 주장 `publisher_id_claimed`/동일 `source_id`도 독립 자료 2개로 착각하지 않도록 동일 검열. 이는 독립적인 실제 원시 게시·수집시각을 증명하지 않는다.
- 각 source가 결정시점까지 주장한 `known_at` 최초·최신 개정과 `valid_from/valid_to` **반개구간 [상장,상폐)** 에 따라 활성 membership을 계산한다. 이미 알려진 `delist/cash_delist/merger` 효력일이 도래한 원천 증권은 active에서 제외하고, 원본에는 여전히 open interval로 남아 있으면 `STAGED_TERMINAL_EXIT_CONFLICT`·`LINEAGE_TERMINAL_EXIT_CONFLICT`로 차단. 미래 효과일의 예정 delist는 조기 제외하지 않는다.
- 양쪽 출처 각각에 똑같은 **완전한 선언 security_id(회사+주식클래스)** 가 존재하고 시장·ticker·최초상장일·상장폐지 구간이 전부 일치할 때에만 `matched_security_class_count` 증가. 동일 회사 SEC CIK에 여러 주식 클래스가 있으면 개별 클래스로 구분하고 `matched_legal_entity_count`는 회사 수만 계산한다. 동일 ticker지만 다른 클래스나 법인이라면 `TICKER_ONLY_DIFFERENT_SECURITY_CLASS` 등 blocker, 클래스를 ticker/issuer만으로 자동 병합 금지. 양쪽 원천의 중복 동시 ticker, 다른 회사/클래스에서만 존재, 개정·종료 누락도 차단.
- 최초 결과와 동일 파일들을 **2회 독립 read-only SHA/계보/정규화 재검증**해 중간 원본 변조 시 보고서 작성 전에 실패. JSON 보고서에서는 보유 종목명·법인코드·CIK·원시 파일경로·원시 문서/투자자 정보·유료 원문 제외, source SHA/시장/불일치 코드별 건수/클래스·회사 일치 수 및 항상 false인 인증 필드만 기록한다.
- 새 `scripts/audit_issuer_class_bridge.py`: opt-in CLI `--staged-manifest --issuer-lineage --decision-at --out`. `issuer_class_corroboration_research.json` 하나만 `output`에 원자 발행. `local_backup.JSON_NAMES`에는 이 **파생 JSON 파일명 하나**만 추가하며 ZIP SHA 검증·새 디렉터리 복구 지원. 기존 staged 변환·PIT SQLite·원본 법인 계보·WATCH·Top-K·시장 API 코드를 **변경하지 않는다**.
- 출력 `LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED`은 원문 숫자·시점의 **로컬 일관성** 표시일 뿐, `legal_issuer_or_class_independently_verified=false`, `historical_universe_pit_certified=false`, `official_candidate_promotion_allowed=false`, `research_watch_allowed_by_this_audit=false` 고정이다. 실제 공식 원천 수급·공시 원문 발행자 서명 및 데이터 전체성은 향후 D-017 API 연결과 별도 인증 전까지 절대 승격하지 않는다.

## 실행 예 (사용자 컴퓨터에 실제 공식 원천 자료가 있다는 뜻이 아님)

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/audit_issuer_class_bridge.py \
  --staged-manifest output/local_staged_vendor/manifest.json \
  --issuer-lineage output/local_issuer_vintage/identity.json \
  --decision-at '2026-10-12T15:50:00+09:00' \
  --out output/derived_research
```

원본 staged `schema_version=eraleader.provider_staged_export.v1`과 별도 issuer `schema_version=eraleader.issuer_lineage_research.v1`을 사용. **시점 취득의 독립 증빙이 없으면 진짜 과거 PIT도 아님.** 출력은 선별 확인용이지 원본/실전 주도주 확정 신호가 아니다.

## 테스트 / 다음

- 신규 `tests/test_issuer_class_bridge.py`: KR corp_code+issue_uid / US CIK+share_class, 같은 CIK 복수 클래스, 같은 티커 다른 회사/클래스 차단, 실제 과거 주식 티커 재사용과 동시충돌 구분, 원천 시간/공시 시점·소급 자료·동일 주장 발행기관 검열, 유효일 전/후 delist/merger, KR·미국 DST, rehashed staged 원문 및 감사 중 수정, 원본 symlink/중복 필드, 명시 CLI·파생 백업 ZIP/복원 검증.
- 테스트, 최초 Git SHA, Public secret scan/푸시 결과는 `PROJECT_STATE.md` 최신 기록에서 확인.

**남은 미완료**: 공식 KRX/DART/SEC 실제 법인·증권클래스/상폐 현금/기업행동·공시 원본 최초 발행·획득시각과 전체 역사 시장 종목군 PIT 독립 증명, 실제 새 WATCH/Top-K 후보가 수개월 후 만기된 후 독립 미래 outcome. D-017 API 마지막, D-021 SSD 실제 탈착·재연결/재부팅 마지막. MarketOS/CycleOS에는 통합하지 않음.

## 2026-10-12 실제 Mac 검증 / 완료 전 증거

- 신규 `tests/test_issuer_class_bridge.py` **24/24 PASS**; 모듈 최초 ImportError RED → 신규 실제 실행 로직 작성 후 GREEN. 시간대/공시 당시 개정, issuer와 share class 누락·공급자 동일, 이미 효력된 상폐/합병, class당 ticker, 미국 DST 경계, 원문 staged/JSONL SHA 변조·후행 레퍼런스 수정, symlink/duplicate JSON key 및 기존 안전 백업/복원 포함.
- 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1547/1547 PASS(exit0)** (이전 1523+24), collect-only 1547, `python3 scripts/check_handoff.py` 번호 30 ID/40필수 PASS, py_compile/diffcheck PASS. Git ignored `output/verification_logs/issuer_class_bridge_full_20261012.txt` 로그.
- Mac 실제 Python CLI 4회 로컬 합성 E2E(인위 주장 발행·수신 날짜): 한국 법인/종목 1개 일치 → `LOCAL_STAGED_ISSUER_CLASS_CONCORDANT_NOT_CERTIFIED`; 미국 CIK 한 회사 복수 주식클래스 2개 일치; 미국 같은 티커·다른 클래스 → `BLOCKED_STAGED_ISSUER_CLASS_MISMATCH`; 과거 결정일 뒤에야 확보된 KR issuer 원본 → `CENSORED_STAGED_ISSUER_CLASS_SOURCE_NOT_INDEPENDENT_OR_PIT`. 4회 모두 원시 manifest/issuer JSON 및 staged JSONL 실행 전후 SHA 그대로, 파생 JSON-only ZIP SHA 검증 및 새 디렉터리 복원 PASS. **시장 실제 공식 원본은 0건, PIT 공증·실전 주도주 발굴 성공도 N/A.**
