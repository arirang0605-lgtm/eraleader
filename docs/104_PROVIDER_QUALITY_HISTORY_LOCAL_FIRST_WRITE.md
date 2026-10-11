# EraLeader 6_2 · 6_5 — 공급자 품질 게이트 최초 평가 이력·변화 추적

> 2026-10-12 KST. `docs/103_PROVIDER_GATE_QUALITY_LOCAL_WEB.md`의 실제 후보 WATCH 검증 결과를 **매 평가 시 로컬 기록**해 강해짐/약해짐/보류 전환을 추적한다. 외부 API 호출, 라이브 발송, 공식 대장주 확정, 실전 성과 입증은 **0건**. 실물 공인 KRX/DART/SEC 신원·공시 원문 최초 이용 시각은 여전히 인증되지 않았다.

## 구현 목적과 범위

기존 웹 `provider_quality_kr|us.html`은 해당 실행 시점의 게이트 원천 검증과 보류 사유만 보여 주며, **이전 실행에서 WATCH가 막혔는지, 본래 PIN·클래스 확인을 거치던 검증을 느슨하게 변경한 것은 아닌지** 식별하지 못했다. 이번 새 기능은 기존 `audit_candidate_provider_gate`의 결과를 **WATCH 생성 전에** in-process로 전달받아 선택적으로 로컬 OS 기록 시각에 관찰 영수증을 저장한다. 백테스트 기준시각을 로컬 기록 시각으로 소급하지 않는다.

- 신규 `src/eraleader/provider_quality_history.py`: `record_quality_snapshot(output_dir, gate, clock=None)`, `audit_quality_history(output_dir, market)`, `render_quality_history(report)`. 기존 `provider_gate_quality_view._validate` 원본 계약 재사용 후 **명시 허용된 필드만** 저장: KR/US, decision_at, 허용/차단, 두 공급자 ID 없는 다이제스트, 로컬 처음 staged 원본 SHA PIN 요구 여부, issuer+개별 주식클래스 증빙 요구 여부, 후보 전체/대조/차단 건수, blocker 코드. 법적 법인코드·SEC CIK·티커/실제 회사명·공시 원문·파일경로·개인키·가격 행 및 실전 매매 성적은 영수증/HTML/보고에 저장하지 않는다.
- 새 SQLite `output/provider_quality_history.sqlite`: 단일 전시장 순번 `event_no`, 기록 OS 시각 `recorded_at_utc`, 종전 event SHA, 현재 로컬 payload SHA, 현재 event SHA를 **연결한 완전 검사 체인**. 첫 기록에 별도 최초 생성 marker `output/provider_quality_history_genesis.json`을 O_EXCL 생성하고 DB `quality_meta`에 원문 SHA를 연결. DB 또는 marker 하나만 없어져도 기존 원장을 조용히 재시작하거나 뒤늦게 다른 원장을 그 자리에 등록하지 않는다. 온전성 감사가 전수 이벤트 수·연속번호·SHA 전후 연결·각 사건 내용·UTC 단조순서·최초 marker를 검증하고 실패하면 다음 기록/웹 발행 보류. 동시 기록에는 별도 파일잠금 + SQLite BEGIN IMMEDIATE, 새 항목은 추가 전용; 같은 시장/같은 as-of/같은 원문 다이제스트/같은 blocker는 **신규 기록 0**, 같은 결정 기준일 원문/판정 변경은 **덮어쓰기 대신 새 수정 사건**.
- 변화 유형: `FIRST_LOCAL_OBSERVATION`, `WATCH_GATE_BLOCKED`(기존 연구용 허용→신규 보류), `WATCH_GATE_REOPENED_RESEARCH_ONLY`(재허용, 공식 승격 아님), `EVIDENCE_STRENGTHENED`/`EVIDENCE_WEAKENED`(두 공급자·첫 원본 PIN·클래스 조사 단계 비교), `BLOCKERS_CHANGED`, `CLAIMED_SOURCES_CHANGED`, `REVISED_SAME_DECISION_REVIEW`, `OLDER_DECISION_REPLAY_NOT_PREDICTION`, `NEW_DECISION_SAME_GATE`. 결정시각보다 **실제 영수증 OS 기록시각이 늦으면 소급 연구 표기**(실전 당시 발굴 성공으로 계산하지 않음); 과거 결정시각보다 먼저 등록하는 미래정보 누출 방지.
- 기존 `offline-integrated`의 새 선택 플래그 `--record-provider-quality-history`는 **`--show-provider-gate-quality` 및 A+B 전체 공급자 원장/최초 bundle SHA**와 함께만 실행. 없는 경우 기존 가격/WATCH/Top-K/공시 DB/기본 화면 동작 변경 0. 원래 게이트 평가 결과의 순서체인 기록이 실패하면 신규 prospective WATCH/상태원장/성공 run 작성 이전에 실패한다. 이미 한 번 기록된 사건은 현장 시계로 다시 소급하지 않음. WATCH의 **검증 가능 여부를 기록**할 뿐 후속 실제 WATCH 저장이나 실전 발송 완료는 별도로 검증해야 하므로 `research_gate_only=true`, `independently_attested_timestamp=false`, `official_leader_promotions=0`, `real_future_leader_precision=null` 고정.
- 웹: `output/site/provider_quality_history_kr.html` 및 `_us.html`에 시장별 첫 로컬 기록시각·최근 50건의 검증 게이트 변화·차단 코드를 보여주고 기존 `provider_quality_kr|us.html`에 **명시 이력 모드일 때만 링크 추가**. 실행마다 시장별 sanitized `provider_quality_history_kr|us_research.json`도 출력. 모든 영수증/웹에는 **실전 적중률 N/A·공식 리더 0·로컬시간 비공증** 경고. 무옵션 기본 웹 변경0.
- `local_backup.py`: 새 안전 기록 SQLite 이름, 첫 생성 marker JSON 이름, KR/US 파생 JSON 파일 이름만 allowlist에 추가. `site/*.html`은 이미 allowlist. 기존 `create_backup` SQLite 온라인 백업/ZIP SHA verification/new-directory restore를 재사용. 원본 시장가격·주주명부·업체 원시 공시/PIT DB·비밀파일을 신규 allowlist에 포함시키지 않는다.

## 실행

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest -q tests/test_provider_quality_history.py tests/test_provider_gate_quality_view.py tests/test_local_backup.py --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 -m py_compile src/eraleader/provider_quality_history.py src/eraleader/cli.py src/eraleader/provider_gate_quality_view.py src/eraleader/local_backup.py
python3 scripts/check_handoff.py
```

선택 CLI: 기존 `offline-integrated --market KR|US --as-of <대상시각> --out output --provider-ledger-a <dbA> --provider-bundle-a <SHA_A> --provider-ledger-b <dbB> --provider-bundle-b <SHA_B> --show-provider-gate-quality --record-provider-quality-history`. 추가 `--require-provider-original-pins`(4 manifest) 및 `--require-provider-issuer-class-lineage --provider-issuer-lineage`는 기존 **독립 선택 계약 그대로 유지**하며, 미요청 확인을 실전 증거 완료로 간주하지 않는다.

## 테스트·제약

신규 TDD는 모듈 ImportError RED 후 개발. KR/US 신규/중복 등록, 시장별 분리 글로벌 체인, 전향적 평가시각 소급 판별, 시장 품질 약화·강화·보류 전환·동일 결정시각 수정을 신규 이벤트로 보존, SQLite 행 값·순번·marker 유실/변조·원장 삭제 후 다운그레이드 감지, 시각 역행·미래 신호 차단, 동시 쓰기 4회 idempotent, 유해 HTML/가짜 인증 플래그 거부, 기존 기본 파이프라인 회귀, 실제 synthetic CLI positive/blocked, derived backup ZIP/restore를 시험한다. **모든 테스트는 합성 claimed 원천**이며 실전 첫 WATCH·Top-K의 실제 미래 검증 결과는 없다.

**무결성 범위 한계:** 본 SHA 체인과 생성 marker는 로컬 실수·부분 변경을 발견할 수 있어도 장치를 장악한 사람이 DB와 marker를 모두 삭제하거나 재작성하면 신원·시간을 공증하지 못한다. 독립 공개원천 당시 수집/발행 timestamp, 서명, 역사 전체 시장 구성은 D-017 외부 API 단계 및 실제 원천 증거 확보 뒤 별도 검증. D-021 SSD 물리 탈착·재연결/맥 재부팅은 그 뒤 최종. 한 번 생성된 후에 marker를 삭제했다면 자동 재작성하지 않고 사람이 검증 백업을 확인해야 한다.
