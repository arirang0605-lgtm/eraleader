# EraLeader 2_2 / 2_5 — 상폐 현금 정산 영수증의 동일 주장 발행기관·감사 중 변조 차단

2026-10-12 KST. 목적: **법적 issuer·상폐 정산·공시 원본의 독립 PIT 인증 전**, 로컬에서 서로 다른 공급자라고 주장하는 원천들이 실제로는 동일 기관의 자기확인인 문제를 최소한 식별하여 모순된 정산수익률을 성과에 넣지 않기. 외부 데이터/API 호출·실전 판정 없음.

## 실제 미완료 발견과 구현

- 기존 `cash_payment_receipts.py`는 서로 다른 claimed `source_id` 여부를 검사했지만, 현금 지급 증빙의 `publisher_id_claimed`가 **issuer lineage의 publisher와 완전히 같아도** 별도 외부 지급 증거라고 간주하는 로컬 연구 통과 경로가 있었다. 따라서 결제 영수증과 issuer 자료의 source_id가 달라도 claimed issuer publisher가 같으면 **`RECEIPT_NOT_A_DISTINCT_DECLARED_PUBLISHER`**로 해당 지급 근거를 차단한다.
- `audit_declared_cash_payment_receipt(..., issuer_publisher_id_claimed=None)`를 선택적으로 추가하고, `cash_exit_lineage.audit_dual_vintage_cash_exit`의 실제 평가 issuer `publisher_id_claimed`를 전달. `source_id_claimed`도 앞뒤 공백·대소문자만 다르게 쓴 동일 공급자 우회를 감지하도록 비교한다. 기존 source/manifest/document SHA·시장/종목/지급액/일시 검사는 유지. 다른 주장 기관인 정상 자료도 `LOCAL_*_NOT_CERTIFIED` 연구 상태에만 머문다.
- **실제 경쟁조건 결함**: 최초 `cash_file`/결정시점 issuer/평가시점 issuer를 읽고 정산 수익률을 계산한 뒤, 영수증 검사 중 파일이 바뀌어도 이전 결과를 그대로 반환할 수 있었다. 이제 보고서 반환 전에 세 입력 **원본 bytes SHA를 모두 다시 읽어 대조**하고, 현금 영수증이 제공된 경우 manifest·원문 지급 문서 전체 감사를 다시 수행해 **처음 결과와 완전 동일**해야 통과한다. 중간 source/결제 문서가 바뀌면 `ValueError`, 파생 보고서 발행 중단. 리스너/외부 API 호출 없음.
- 기존 `delist_cash.py`의 분할·배당 포함 수익 계산, 기존 `issuer_lineage.py`, 기존 PIT/주식클래스/Top-K 성과 등록, local_backup 원본 코드는 **변경·재작성 없음**.

## 실행 방법과 안전 한계

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_cash_payment_receipts.py tests/test_cash_exit_lineage.py tests/test_cash_exit_amount_claims.py tests/test_delist_cash.py -q
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
```

- 신규 테스트 총 11개: 동일 주장 publisher·대소문자/공백 우회·공급자 ID 위장·상위 caller 연결·정상 다른 publisher 연구 경로 6건 + 감사 중 cash/두 시점 issuer/manifest/document 수정 거부 5건. 각각 **TDD RED**를 확인하고 구현·GREEN 검증. 현재 Mac 실제 CLI `python3 -m eraleader audit-cash-delist` synthetic KR 두 경로: 동일 주장 publisher **CENSORED/BLOCKED**, 다른 주장 issuer/payout publisher **LOCAL_RESEARCH_NOT_CERTIFIED**, 수익률 후자는 합성 10%, 역사 실전 수익률 인증 아님. 원본 issuer/cash/증빙 SHA 불변, 파생 `cash_delisting_research.json` ZIP SHA와 새 경로 복원 일치, API0.
- 테스트용 fixture/CSV/현금 지급 문서는 `output/` ignored로 보존하며 **GitHub Public에 업로드하지 않음**. Git에는 소스/회귀/이 문서만 stage.
- **절대적 한계**: 두 *주장* 기관이 다르다는 사실만으로 공급자의 법적 신원·공시 시각·원본 진위·지급 사실을 외부 공증하지 않는다. 두 번 읽어도 Mac 로컬 파일을 동시에 위조·복제하거나 반환 직후 수정하면 독립 인증은 불가능하다. 종목군 PIT/상폐·분할·배당 completeness/실전 미래 대장주 성과 **N/A**, 공식 리더 0.

다음: KRX/DART/SEC 공식 issuer/share-class 및 실제 지급증거 첫 공시 타임스탬프 인증, 당시 상장·상폐 전체 시장 편향 없는 universe PIT, prospective Top-K 첫 실전 미래 만기 outcome. D-017 외부 API 연결과 D-021 SSD 물리분리/재연결/재부팅은 로컬 완성 후 최종 단계.

## 2026-10-12 완료 검증

- 새 회귀 **11개** (동일 주장 issuer publisher / 유사 표기 우회 / source alias / 단독 검증 / 정상 경로 6개 + 감사 중 cash/기준 issuer/후행 issuer/영수증 manifest/지급문서 변경 5개). 먼저 **5건 주장 공급자 위장 RED + 5건 경쟁조건 RED**를 실제 재현 후 모두 GREEN.
- 관련 4개 테스트 파일 **106/106 PASS**, 전체 `PYTHONPATH=src python3 -m pytest tests -q --tb=short` **1523/1523 PASS, exit0**, `pytest --collect-only` 1523, `scripts/check_handoff.py` 30 ID/40 필수 PASS, py_compile/diffcheck PASS. 전체 원격 실행 로그 ignored `output/verification_logs/cash_publisher_full_20261012.txt`.
- Mac 실제 `python3 -m eraleader audit-cash-delist` 합성 KR: issuer·지급증빙 **같은 claimed publisher / source id만 다름** → `CENSORED_UNCORROBORATED_CASH_EXIT`, 수익률 null; 서로 다른 claimed publisher / 지급문서 내용일치 → `LOCAL_DUAL_VINTAGE_CASH_EXIT_RESEARCH_NOT_CERTIFIED`(합성 0.1 수익). 두 경로 원본 SHA 불변, 파생 보고서만 기존 local-backup ZIP SHA 검증·새 경로 완전 복원. 외부 API/공식 실전 리더/개인 주문 0. 두 번째 경로도 실제 법적 지급 진실성·독립성을 인증하지 않는다.
