# ER-NC-01 — NewsCatalystOS 사건 read-only PIT 소비 (2026-10-13)

**선행:** ER-NC-B00 백업/독립 이미지 SHA·실제 복원·SQLite 273개/오프라인 pytest EXIT0, original main/사용자 미커밋 보존 PASS. ER-NC-00 feature worktree 분리.
**코드:** `src/eraleader/news_catalyst_adapter.py`만 신규. 공식 KRX/DART/SEC, 기존 WATCH, `delivery.py`, `cli.py`, SQLite 스키마는 전혀 변경하지 않음.

## 계약
- 버전 `schema_version=1.x`, `export_id/event_id/event_version`의 시점별 합성 fixture, 업체 공개/최초 관측/실사용 가능시각 분리, 정정 `revised_at`.
- 파일 전체/각 레코드 SHA256, ID·권리 `license_profile`, 검증 근거, source URL 메타만 허용. 기사 원문/타인이 작성한 프롬프트·라이선스 불명 레코드 입력 금지.
- 조회 `NewsCatalystEvents.load(path)`, `.snapshot(as_of,mode)`, `.related_events(entity_or_theme,as_of)`.
- `LIVE_OBSERVED`: 최초 발견 이전에는 미노출; 수집 후 검증 전은 `OBSERVED_UNVERIFIED` 최소 placeholder; 가용 이후 당시 레코드 버전만 노출. 나중 정정/수혜기업 ID는 이전 버전으로 소급하지 않음.
- `HISTORICAL_PUBLIC_REPLAY`: 별도 독립 earliest-public/시점별 권리·커버리지 증빙이 없으므로 `INDEPENDENT_PUBLICATION_WITNESS_REQUIRED`와 이벤트 0건을 반환. 과거 이벤트를 실전 승률로 전용하지 않음.
- `NEWS_ENABLED=false` 기본; `attach_news_evidence(...,enabled=False)`는 원래 snapshot 객체를 그대로 반환. 실제 뉴스 미공급/오류에는 기존 모델·WATCH 유지하고 뉴스 측면 `DEGRADED_NEWS_UNAVAILABLE`. 켠 경우 확인된 이벤트만 새 `news_evidence` 사이드카에 표시하며 점수·대장주 확정/종목 상태는 미변경.

## 검증
- `PYTHONPATH=src python3 -m pytest tests/test_news_catalyst_adapter.py tests/test_pit.py tests/test_official_api_pit_bridge.py -q --tb=short`: **46/46 PASS, EXIT=0**, 2026-10-13.
- 합성 커밋 가능한 JSON fixture: `tests/fixtures/news_events/verified_research.json` (JSONL 경로는 자동 테스트의 임시 파일로만 생성하며 실제 로그/시장 JSONL을 Public에 업로드하지 않음). 09:11 미수신·09:13 관측미확정·09:15 검증, 늦은 정정/6개월 뒤 수혜주 소급 방지, 동일 버전 SHA 충돌, JSON 중복키, 권리·스키마·symlink 거부, 백필 연구 모드 차단, NEWS_OFF 웹 HTML SHA 동일, 뉴스 장애시 기존 WATCH 동일 테스트.
- 영업용 기사/유료 데이터·개인 인증정보 사용0, 외부 API 호출/실전 메시지/실주문0.

## 남은 범위
- `ER-NC-01`은 **읽기 전용 소비 계약/연구 WATCH sidecar 단계**만 구현; 실제 NewsCatalystOS 독립 공급자 서명/최초 공개시간/라이선스가 없으므로 LIVE_DATA_INTEGRATION_DONE 아님. UI/보고서 표시·테마/시장/전략/성과는 후속 02~10.
- 주권 영구ID·이력, 한국·미국 역사적 전체 PIT, 전향적 적중률 모두 N/A. 미확인 수익률/상승 성공 주장은 금지.
