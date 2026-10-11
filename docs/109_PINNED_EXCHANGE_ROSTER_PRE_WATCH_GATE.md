# EraLeader 2_2 · 2_5 · 4_1~4_3 — 제3 전체시장 PIT 명부를 최초 WATCH 게이트에 연결

> 2026-10-12 KST. 기존 2-provider + first raw ingest PIN + issuer/share-class WATCH 게이트(`docs/102`)와 제3 거래소 전체 상장 클래스 대조(`docs/108`)를 **실제 `offline-integrated` 후보 발행 전 하나로 묶는 opt-in 기능**이다. 모든 공급자와 거래소 명부는 현시점 **오프라인 자체 선언된 연구자료**이며 공식 KRX/DART/SEC 원본 인증/실제 시장 PIT/실전 미래 대장주 정확도를 주장하지 않는다. 기존 정상 코드/결정 임계값/MarketOS/CycleOS 유지.

## 기존 공백과 이번 연결

`docs/108`의 제3 명부 검사기는 독립 실행만 가능했고, 기존 `offline-integrated`가 두 공급자+issuer/class 자료만 일치시킨 후 **전체시장 명부에서 누락한 증권 클래스가 있어도** 연구용 신규 WATCH를 기록하는 위험이 남아 있었다. 이번 신규 선택 모드는 실제 WATCH 계산 당시 **같은 처음 PIN된 공급자 A 원시 스테이징 파일**, 별도 issuer lineage, 제3 전체 명부를 재검증하며, class가 하나라도 누락·과잉/유효기간 충돌 시 **WATCH 0 / 신규 run 0 / prospective SQLite 신규 입력 0**으로 차단한다.

- 최소 수정 `src/eraleader/provider_candidate_gate.py`: 기존 `audit_candidate_provider_gate`에서 추가 `exchange_roster_file`, `exchange_roster_sha256`를 **함께** 받도록 opt-in. 반드시 `require_original_pins=True`, 양 공급자 A/B 각 원시 staged+normalized 첫 ingest manifest, 별도 `issuer_lineage_file` 필요. 하나라도 빠졌으면 실패. 입력 roster JSON은 자체 구조/미래 세션·원천 최초 공개 claimed time·전체시장 scope 선언을 검증하고, 외부에서 미리 명시한 **정확한 raw bytes SHA256**과 비교한다. SHA가 바뀌었으면 후보나 게이트 파일 작성 전 예외.
- **실제 인프로세스 세 출처 비교**: 원래 `audit_provider_source_pair`로 PIT/기업행동 A+B 영수증 검증→후보 issuer/class exact membership 검증→`audit_declared_exchange_roster(original_sources[0][0],issuer_lineage_file,exchange_roster_file)`로 당시 시장 전체 share-class를 모두 감사한다. 정확한 영구ID·ticker·상장기간/종료·delist/merger 등의 계약 불일치를 `EXCHANGE_ROSTER_* ` 차단 코드와 건수로 기존 후보 게이트에 연결. 제3 source의 불일치가 후보 종목 밖에 있더라도 *그 날 전체시장 종목군이 인증되지 않았다*는 이유로 연구용 WATCH도 차단. 별도 보조 결과만 읽어 WATCH를 허용하는 우회 없음.
- 후보 자료가 정상이라도 제3 원문·시간·명부 검사가 불일치하면 `BLOCKED_PROVIDER_PIT_CANDIDATE_RESEARCH`, 신규 첫 WATCH/주간 리포트 후보/상태 이력/실행 결과를 정상 성공으로 기록하지 않음. SHA/시간 스키마 변조 시 fail closed. 기존 pair+issuer 최초/최종 검증 뒤 **제3 전체 명부 감사도 재검증**해 감사 중 원문 변경을 검출. 마지막 시점에 원본 제3 roster raw bytes pin을 다시 검사. 실제 매매/주문·실전 알림은 없다.
- gate JSON에는 **파일 경로/issuer/CIK/ticker/source name 없이** `exchange_roster_required`, `exchange_roster_sha256`, `exchange_roster_status`, `exchange_roster_evidence_sha256`, `exchange_roster_locally_matched_classes`, 고정 `exchange_roster_historical_pit_certified=false`만 추가. 이 값과 정확한 roster SHA가 기존 후보 게이트 `source_pair_digest_sha256`와 실행 run ID의 provenance에 결합되어, 다른 명부나 raw bytes만 다시 포맷한 재시도도 **이전 WATCH 판단 증거와 동일한 실행으로 덮어쓰지 못한다**. 기존 `provider_gate_quality_view.py`는 새 `EXCHANGE_ROSTER_* ` 차단코드를 기존 품질/보류 페이지에 표시한다.
- 기본 모드(세 번째 명부 미요청)의 출력 형식·WATCH/상태·순위·이전 두 공급자 검사 순서·기본 CLI는 그대로. **선택 기능을 한 번 사용했다고 모든 후속 무옵션 실행을 영구 차단하는 정책은 구현하지 않았다.** 이는 명시 옵션을 사용하는 개발 단계의 연구 게이트이며, 실제 운영에서는 외부 독립 자료 인증/설정 정책 고정이 별도로 필요하다.

## 선택 실행 예

아래 path는 **예시**다. 해당 파일이 SSD에 실제 존재하거나 공식 거래소 원본이라는 주장이 아니다. `ROSTER_SHA`는 **처음 관측하여 따로 기록한 바로 그 파일의 원문 바이트 SHA-256**으로 제공한다. 같은 파일을 임의로 수정하고 SHA도 나중에 다시 만들어 제공하면 공식 원본/첫 이용가능시각 공증이 되지 않는다.

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR --as-of '2026-10-12T16:30:00+09:00' --out output/research \
  --provider-ledger-a <A.sqlite> --provider-bundle-a <A.bundle.sha256> \
  --provider-ledger-b <B.sqlite> --provider-bundle-b <B.bundle.sha256> \
  --require-provider-original-pins \
  --provider-staged-manifest-a <A.original.staged.json> \
  --provider-normalized-manifest-a <A.normalized.manifest.json> \
  --provider-staged-manifest-b <B.original.staged.json> \
  --provider-normalized-manifest-b <B.normalized.manifest.json> \
  --require-provider-issuer-class-lineage \
  --provider-issuer-lineage <separate_issuer_lineage.json> \
  --require-provider-exchange-roster \
  --provider-exchange-roster <third_whole_exchange_roster.json> \
  --provider-exchange-roster-sha256 <ROSTER_SHA> \
  --show-provider-gate-quality
```

원본 첫 PIN 4개 + issuer+class lineage+제3 roster와 raw PIN의 일부 옵션만 입력한 **약한 불완전 조합은** 원본 `offline.sqlite` 읽기 전에 안전 오류/실행 종료. WATCH/SHA mismatch 차단 시 감시/보류 사유만 파생 JSON/HTML로 표시하고 원래 신호/원장에 거짓 성공을 기록하지 않는다.

## 테스트 / 남은 한계

- `tests/test_candidate_exchange_roster_gate.py`: KR/US 원래 first pinned 2공급자 + 제3 전체 클래스 정상 matched→연구 WATCH 허용·공식 leader 0, 시장 전면에 가짜 클래스/누락·ticker만 일치하는 잘못된 issuer·상장기간·공시 수신 지연·동일 claimed publisher 차단, 원문 SHA 불일치/공유 manifest/issuer/PIN 누락·비정상 CLI 플래그 차단, 감사 중 roster 수정 차단, 동일 의미 데이터의 raw bytes SHA가 다르면 immutable run proof digest 변화, 품질 웹 차단 사유, 기본 CLI 호환, 기존 합성 native/우회 사후 정확도 N/A 확인.
- `PYTHONPATH=src python3 -m pytest -q tests/test_candidate_exchange_roster_gate.py tests/test_candidate_issuer_class_gate.py tests/test_provider_candidate_gate.py tests/test_provider_pair_original_pin_gate.py tests/test_exchange_roster_crosscheck.py --tb=short`
- `PYTHONPATH=src python3 -m pytest tests -q --tb=short`, `python3 scripts/check_handoff.py`, `python3 scripts/check_git_safety.py`.

**제약:** 현재 전시장 roster/issuer-class·두 supplier 이름/첫 bytes SHA는 모두 로컬로 주장된 출처다. 법적 등록증권 전체를 커버했다거나 source clock이 공식·독립 인증됐다는 증거가 아니다. 공식 KRX/DART/SEC 최초 게시·수신·상폐 현금·기업행동·역사 전체 universe와 첫 prospective 실제 미래 outcome은 미인증·미완료. 외부 API D-017 마지막, 실물 SSD 분리/재연결·재부팅 D-021 마지막, REWRITE 금지.
