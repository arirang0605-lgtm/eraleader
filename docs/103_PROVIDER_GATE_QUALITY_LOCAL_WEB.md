# EraLeader 6_2 · 2_2/2_5 — 원천 검증·후보 보류 사유 로컬 웹 대시보드

> 2026-10-12. 앞선 `docs/102_FIRST_PINNED_ISSUER_CLASS_WATCH_GATE.md`의 **실제 후보 WATCH 사전 검증 결과**를 읽기 쉽게 보여주는 선택적 시각화. 현재 Mac/SQLite SHA/claimed 공급자 문자열은 **원시 거래소 증명·원문 공시 시각·독립 서명이나 실전 성능을 인증하지 않는다**. API 0 / 실전 알림 0 / 공식 확정 대장주 0.

## 실제 개발 범위

기존 `offline-integrated`는 원시 공급자 PIT 데이터, 후보 회원ID, 원본 최초 등록 시각, 법인/주식클래스 검증을 연결해 연구용 WATCH를 발행 또는 보류하되, 사용자에게는 CLI JSON `blocker_counts`만 제공했다. 공급자 쌍 연구 일치와 **원시 SHA PIN을 요구했는지**, 추가 **법인·주식클래스 식별을 확인했는지**가 웹에서 분리되지 않았다.

- 신규 `src/eraleader/provider_gate_quality_view.py`: 실제 `audit_candidate_provider_gate`의 **in-process 원본 결과**만 받아 입력 계약/개수/출처 digest/거짓 인증 플래그/모순된 allowed·blocked 상태를 엄격 확인해 안전 HTML로 렌더. 사용자 원시 issuer ID·ticker/CIK/법인코드·시장 원시 행·파일경로는 화면에 전혀 반출하지 않음. blocker 코드는 검증된 영대문자·숫자·밑줄만 허용하며 전체 코드별 건수 출력, 최대 200. XSS/위조 인증·모순 개수는 fail closed.
- 검증 카드 3개는 서로 다른 범위를 명시한다. **(1) 두 claimed 공급자 로컬 숫자 일치 (2) 초기 staged 원본 SHA 첫 등록 PIN 요청/비요청 (3) 법인+개별 클래스 PIT 추가 비교 요청/비요청/보류**. 어느 것도 공식 PIT 인증이나 실제 투자 신호가 아님. 후보 검증 실패면 `보류`만 보여주며 신규 WATCH·상태원장·joined run은 기존대로 발행하지 않는다.
- 새 `offline-integrated --show-provider-gate-quality`는 원래 두 공급자 ledger/bundle 4인수가 제공된 경우에만 허용. `--require-provider-original-pins`와 `--require-provider-issuer-class-lineage`는 이전 구현대로 별도 선택 가능하며 미요청 상태를 녹색 성공으로 표시하지 않음. 적합성이 확인되지 않은 텍스트 리포트 파일만 다시 렌더하지 않고 기존 실제 **PIT·WATCH 전단의 gate 결과 객체**를 재사용.
- 양 시장 `output/site/provider_quality_kr.html`, `output/site/provider_quality_us.html` 각 고유 파일로 원자 생성·갱신. 기존 `python -m eraleader serve`가 실행되면 `http://127.0.0.1:8765/provider_quality_kr.html` 혹은 `..._us.html`로 확인. 양호 연구 WATCH에는 기존 `research_kr.html` 등의 헤더에서 **품질·보류사유 페이지 링크** 추가. 실제 blocked 모드에서는 **품질 진단 HTML만 선택 발행**, 기존 research/state/prospective 생성 금지. 무옵션 실행에서 신규 페이지·링크·프로세스 변경 없음.
- HTML 파일은 임의 쓰기 중간 손상을 막도록 동일 폴더 임시파일 생성 후 원자적 교체; 심볼릭 링크 대상/부모는 거부. 기존 `local_backup.py`의 `site/*.html` allowlist로 정제된 화면만 local ZIP SHA 검증·원래 없는 폴더로 복원 가능. 원시 SQLite·vendor JSONL과 API 키는 백업·Git에 포함하지 않음. 모든 페이지에는 정확한 해당 결정시각, `실전 적중률 N/A`, `공식 대장주 0` 및 공급자·시간 독립 공증 부재 표시.
- 같은 `provider_candidate_gate_research.json`을 이용하는 기존 정기 가격/관찰/주문/MarketOS 로직 재작성 없음. 추가 플래그로 사용자 주도로 명시적 실행할 때만 웹 화면을 생성함.

## 재현 (합성 로컬 fixture, 공식 시장 인증 자료 아님)

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest -q tests/test_provider_gate_quality_view.py tests/test_provider_candidate_gate.py tests/test_candidate_issuer_class_gate.py tests/test_provider_pair_original_pin_gate.py tests/test_research.py --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 -m py_compile src/eraleader/provider_gate_quality_view.py src/eraleader/delivery.py src/eraleader/cli.py
```

실제 CLI 옵션 계약 예: `python3 -m eraleader offline-integrated --market KR --as-of <시각> --out output --provider-ledger-a <dbA> --provider-bundle-a <SHA_A> --provider-ledger-b <dbB> --provider-bundle-b <SHA_B> --require-provider-original-pins --provider-staged-manifest-a <...> --provider-normalized-manifest-a <...> --provider-staged-manifest-b <...> --provider-normalized-manifest-b <...> --require-provider-issuer-class-lineage --provider-issuer-lineage <별도 법인/주식클래스 계보.json> --show-provider-gate-quality`. 옵션만 제시하며 실제 원천 공급자/과거 PIT 인증을 의미하지 않는다.

## 남은 실제 미완료

원시 KRX/DART/SEC 회사/주식 클래스·전시장 역사 종목군·분할/배당/상폐 현금정산 원문 최초 공개/수신시각 **독립 증명 불가**, 첫 실전 native WATCH/Top-K future outcome 만기 후 precision/FDR/lead days **N/A**. D-017 외부 API를 로컬 완성 후, D-021 SSD 실제 물리 분리·재연결/재부팅을 마지막으로 연기. 페이지는 기록된 결정시점 연구 스냅샷이며 최신 외부 시장 상태/공식 감사 증명이 아니다.
