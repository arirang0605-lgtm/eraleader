# EraLeader 2_2·2_5·4_1~4_3 — 원본 첫 PIN 법인/주식클래스 후보 WATCH 연결

> 2026-10-12 KST. **로컬 공급자 주장을 추가 대조하는 선택적 안전 게이트**이며 실제 KRX/DART/SEC 법인ID, 공시시간, 전체 종목군 PIT 공인 증빙이 아니다. 외부 API 0, 실전 알림 0, 공식 대장주 0, 실전 precision N/A.

## 이번 기능 (기존 동작 보존)

기존 `issuer_class_bridge.py`는 원천 staged manifest 대 별도의 issuer lineage를 독립 감사할 수 있었으나, 기존 `offline-integrated`가 최초 WATCH와 상태원장에 쓰기 **전에 실제 후보ID가 그 교차대조에 포함됐는지** 강제하지 않았다. 새 opt-in 모드로 연결한다.

- 신규 `src/eraleader/issuer_candidate_evidence.py`의 `audit_candidate_issuer_class(...)`: 기존 `audit_staged_issuer_class` 전체 시장/issuer/security-class 비교를 그대로 재사용하고, 기존 staged normalizer 원본의 **판단시점 활성 완전 security_id + 시장 + ticker + 상장·상폐구간**과 현재 선택한 각각의 WATCH 후보를 정확히 대조한다. 집계 일치만으로 후보를 통과시키지 않는다.
- 호출자는 `provider_candidate_gate.audit_candidate_provider_gate`의 새 선택 인수 `issuer_lineage_file`. 이 인수가 있을 때 **반드시 기존 두 공급자 원본 staged/normalized 최초수입 SHA 핀 strict 모드**를 사용해야 한다. 별도 staged 출처 경로를 받지 않고 기존 strict pair **A 공급자와 첫 로컬 receipt로 묶인 원본 staged manifest**를 직접 재사용한다. PIN이 없거나 두 원본 출처 불일치면 연구용 WATCH도 보류한다.
- 관련 원본을 시작과 끝 두 차례 감사하고, 원본 SHA·기업/클래스 목록·blocked 이유·후보ID 비교가 바뀌면 예외로 중단. 모순, 다른 주식클래스, ticker만 같은 법인, 뒤늦게 수집한 공시·동일 claimed publisher, 실제 출처 변조는 `ISSUER_CLASS_* ` blocker와 함께 WATCH/Top-K 진입을 차단한다.
- 성공해도 오직 **research WATCH**만 허용한다. `publisher_independently_authenticated=false`, `legal_issuer_identity_independently_verified=false`, `historic_membership_pit_certified=false`, `official_candidate_promotion_allowed=false`, `official_leader_promotions=0`는 그대로 유지.
- 보고 `provider_candidate_gate_research.json`에는 추가 `issuer_class_bridge_required`, `issuer_class_bridge_status`, `issuer_class_evidence_sha256`, `issuer_class_matched_candidates` 및 blocker만 추가. 원본 기업코드, CIK, 파일/클래스 내용, 민감 vendor 원문/키는 쓰지 않는다. 결과 digest를 기존 `source_pair_digest_sha256`에 포함해 같은 점수여도 issuer 증거가 달라진 immutable joined run을 분리한다.
- `offline-integrated`의 새 선택 옵션: `--require-provider-issuer-class-lineage` 및 `--provider-issuer-lineage <별도 법인계보 JSON>` **둘 다 필수**. 함께 기존 `--require-provider-original-pins`, 공급자 ledger/bundle A+B, staged/normalized manifest A+B 4개를 반드시 제공. 그 중 하나라도 빠지면 파일 생성 전에 exit 2. 옵션이 없을 때 기존 CLI·WATCH/Top-K/정기 배치에는 영향 없음.
- 기존 `local_backup.py` allowlist의 `provider_candidate_gate_research.json`만 재사용. vendor JSONL, 개별 법인원문 및 종목 시세를 ZIP/Git에 추가하지 않음.

## 합성자료 재현

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest -q tests/test_candidate_issuer_class_gate.py tests/test_provider_pair_original_pin_gate.py tests/test_issuer_class_bridge.py --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 -m py_compile src/eraleader/issuer_candidate_evidence.py src/eraleader/provider_candidate_gate.py src/eraleader/cli.py
python3 scripts/check_handoff.py
```

새 테스트: 합성 KR 및 미국 SEC CIK·복수증권 클래스 식별, 다른 법인/티커/소급 공급자 주장 blocked, 원본 PIN 필수, 누락 CLI 옵션 제출 전 초기차단, 로컬 synthetic 실제 CLI WATCH 1개 발행/negative 0개, 감사중 원본 수정 거부, 원본 SQLite SHA 유지, **파생 요약 JSON만** ZIP 검증·새 폴더 복원.

## 남은 미완료

실제 전체 과거 PIT exchange universe, KRX/DART/SEC 법적 issuer/security-class·조정가격·상폐 현금·공시 최초 공개·수신시각의 **독립 증빙**, 미래 WATCH/native Top-K 첫 후보의 진짜 장기 평가 outcome/false discovery/lead-days 미완료. D-017 외부 API는 마지막; D-021 SSD 물리 분리/재연결·재부팅은 최종 단계. 이번 로컬 SHA/증빙은 공급자 신분·원문 최초 공개시각을 공증하지 않는다.
