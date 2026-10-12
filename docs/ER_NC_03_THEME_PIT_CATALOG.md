# ER-NC-03 — 불변 테마ID/시점별 issuer·주권 클래스 멤버십 (2026-10-13)

선행: `BACKUP_READY=PASS`, ER-NC-01(뉴스 read-only PIT), ER-NC-02(시장·new-entry 연구 정책) 각각 테스트 PASS.

- 신규 `theme_pit_catalog.py`: immutable `theme_id/created_at`와 `taxonomy_version/available_at` 빈티지, 별칭 최초 확보시각, 이전/현재 산업 재분류, `member_issuer_id/member_security_id/member_first_known_at/member_effective_from/to` 및 관계 근거를 `snapshot(as_of)`에서 따로 조회.
- `relationship_type`은 직접 계약·공급망·산업 근거와 단순 공동언급을 분리. 현재 영구 share-class 식별/근거가 없거나 뉴스 공동언급뿐이면 멤버십 확정에서 **제외하고 결측 품질로 기록**, 0점/테마 종료로 해석하지 않음.
- 단일 기업의 티커 개명도 안정된 주권 클래스로 이력 보존; 별개 주권 클래스 2종은 합치지 않음. 과거 편입/탈퇴·상폐·재분류를 당시 이용 가능한 빈티지만 적용.
- `resolve_hint`는 뉴스 엔진의 분류를 **UNVERIFIED_THEME_HINT** 제안으로만 연결, 테마 마스터·종목구성 자동 덮어쓰기0. 기업행동/역사 전체시장 종목군 독립 공급원 미인증이므로 공식 대장주 확정0, `research_only=true`.
- 기존 종목 ID/PIT/SQLite, states, WATCH, 매매/리포트 모듈 **수정0**, B00 보호된 main·미커밋 수정 불변.

**검증:** `PYTHONPATH=src python3 -m pytest tests/test_theme_pit_catalog.py tests/test_market_regime_experiment.py tests/test_news_catalyst_adapter.py -q --tb=short` → **67/67 PASS, EXIT0**.
시점별 최초 테마·별칭, 6개월 후 신규 구성 종목의 소급 편입 금지, ticker 개명, 별개 class, parent 업종 개정, 테마 휴면과 상장폐지 기간 관측, 공동 언급 제외, 미확인 class, 회원·버전 중복·원문 근거 결손 차단 테스트.

다음: ER-NC-04 가격 RS/거래대금/breadth 별도 상태·episode(정식 성과 N/A).
