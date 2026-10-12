# EraLeader 2_2·2_5 → 4_2·5_5 — 최초 SHA 봉인 원자적 두 공급자 PIT 자료의 후보 WATCH 연결

**2026-10-12 KST.** 외부 API 호출 없이 기존 docs/127 원자적 KR/US 공급자 첫 수입과 docs/128 read-only SHA/as-of 전체 재감사를 **기존** `offline-integrated` 후보 게이트 앞에 연결했다. 이전에 검증된 일반 WATCH·종목 점수·첫 native Top-K·PIT DB·cold recovery 정상 코드를 다시 만들지 않는다.

## 새 기능

- 새로운 `src/eraleader/provider_pair_candidate_bridge.py`는 원래 첫 발행 시 **따로 기록해 둔 SHA-256**이 없으면 실행을 거부한다. 이미 봉인한 `first_pair_receipt.json`과 A/B 원시 스트림·manifest 전체, 최초 정규화 SHA, SQLite 첫 등록/문서 영수증, 최초 의미 대조, 요청 as-of 당시의 원본 쌍 전체 대조를 docs/128 코드로 읽기 전용 재감사한다.
- `offline-integrated`의 명시적 선택 옵션 `--provider-atomic-pair-root` 및 `--provider-first-pair-sha256`이 완비되면 A/B 등록 ledger·정규화 bundle SHA·원래 staged/normalized manifest를 **봉인 영수증에서만 파생**하여 기존 `audit_candidate_provider_gate`에 전달한다. 사용자 임의 A/B path 또는 새로운 PIN을 혼합하면 실패한다. 이전 수동 strict A/B 사용법과 opt-out 사용법은 변경하지 않았다.
- as-of가 **최초 두 공급자의 로컬 수입 시점보다 과거이면 불합격**이다. 원래 두 출처의 주장만 일치한다고 진짜 과거 당시 이용 가능했다고 소급 인증하지 않는다. KR/US 시장, 대상 WATCH의 기업군·기업행동·재무·산업과 실제 입력 DB가 다르면 기존 candidate gate가 차단한다.
- **기존 WATCH/상태/quality history/first signal 쓰기 이전**에 최초 원본과 두 DB를 다시 재검증해, 후보 비교 도중 원본을 바꾸는 경쟁 조건을 탐지하면 결과를 새로 발행하지 않는다. 원본 paired receipt SHA는 연구용 게이트 결과와 immutable `run_id` 계산에도 포함된다.
- 첫 paired private folder·staged 원시 폴더와 derived output이 같거나 어느 한쪽이 상위/하위로 겹치면 쓰기를 차단한다. private source/원시 증권 ID·secret은 공개 gate JSON에 출력하지 않는다. `offline.sqlite`는 사용자가 별도로 미리 준비한 **연구용 읽기 전용 소스**만 사용하며, 본 기능이 원본을 자동 복사·수정하지 않는다.
- 기존 추가 체크 `--require-provider-issuer-class-lineage` 및 `--require-provider-exchange-roster`는 필요 시 그대로 병행할 수 있으며, roster의 원래 강제 PIN·sticky 정책과 official promotion 차단을 유지한다.

## 실행 예시 (합성 자료 또는 비공개 오프라인 수집본만)

최초 docs/127 `onboard_provider_pair.py` 실행이 반환한 `first_pair_receipt_sha256`을 **그 최초 시점에 원본 밖에서 별도로 안전하게 저장**한 후 사용한다. `--as-of`는 첫 로컬 등록 이후의 실제 의사결정 시각이어야 한다.

```bash
cd /Volumes/T5DATA/eraleader
mkdir -p output/private_pair_research
chmod 700 output/private_pair_research
# 준비: output/private_pair_research/offline.sqlite = 해당 첫 source A와
# 일치하는 비공개 당시 오프라인 PIT SQLite (원본과 분리, Git 무시)
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR --as-of '2026-10-12T18:00:00+09:00' \
  --out output/private_pair_research \
  --provider-atomic-pair-root /PRIVATE_OWNER0700/first_pair \
  --provider-first-pair-sha256 '<발행당시_따로_저장한_실제_64자리_sha256>'
```

**성공 기준**: `provider_candidate_gate_research.json`에 `atomic_first_pair_receipt_sha256` 및 `atomic_first_pair_research_only: true`, 로컬 최초 WATCH 원장 및 immutable run 기록. 그래도 `official_candidate_promotion_allowed: false`, `pit_certified: false`, 실전 투자/자동 거래/알림 전송 0이다.

**실패 기준**: SHA 누락·잘못된 SHA·root 경로 누락/겹침, 소급 backdated cutoff, 다른 시장, 원본 첫 파일/정규화/SQLite 변조, 후보 DB 불일치, 동시 원본 변경 시 새 signal/상태/연구 결과를 승인하지 않는다. 직접 구동 실패는 exit code 2 또는 예외이며 원본을 복구/다시 PIN 하지 않는다.

## 재현·검증 및 후속

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_provider_pair_candidate_bridge.py \
  tests/test_provider_pair_asof_seal.py \
  tests/test_provider_pair_atomic_onboard.py \
  tests/test_provider_pair_original_pin_gate.py \
  tests/test_provider_candidate_gate.py \
  tests/test_exchange_roster_policy.py -q --tb=short
python3 -m py_compile src/eraleader/provider_pair_candidate_bridge.py src/eraleader/cli.py
```

테스트는 실제 Mac 파일시스템에 만든 **가상 KR/US 공급자**와 first SHA/DB/원시 파일을 사용한다. 등록→읽기전용 감사를 거쳐 WATCH 생성/중복 재실행→역산 차단/시장 혼합/경로 겹침/비정상 파일 변조/진행 중 변조를 포함한다. 전체 pytest 회귀는 사용자 결정에 따라 공식 API 연결 후 실시하며, 본 변경은 위 영향범위만 단계 검증한다.

**남은 핵심 차단점**: 공인 KRX/DART/SEC 원문 최초 발행·최초 수신시각, issuer/share class·상폐 cash·기업행동·전체 역사 종목군 PIT의 독립 원천 대조 및 실제 첫 native Top-K 1~12개월 자연 만기 실전 평가. 현 first SHA는 관리자/로컬 시각 위조 또는 외부 timestamp 신뢰를 방어하는 공증이 아니다. D-017 API·D-021 실제 SSD 분리/재연결/재부팅은 최종 단계로 유보한다.
