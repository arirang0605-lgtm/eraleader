# ER-NC-05 — 기존 전향 WATCH 2+2 회전가설에 테마 episode·뉴스 근거 부착

선행: B00 BACKUP_READY=PASS, ER-NC-01~04 PASS. 기존 `ProspectiveRegistry`/ `watch_rotation.audit_watch_rotation`의 **명시적 2회 긍정→2회 부정·후계 2회 지속**과 최초 등록시각을 다시 계산하지 않고 직접 호출.

- 신규 `news_rotation_context.correlate_watch_rotation`: 기존 원장 SQLite를 read-only로 감사하고, 뉴스 시점별 snapshot의 `available_at`과 stage03 현재 PIT 테마 멤버 `member_first_known_at`을 그 후계 후보의 **실제 첫 WATCH 등록시각** 이전으로 제한한 뒤 `RESEARCH_ROTATION_HYPOTHESIS` 옆정보만 출력. `theme_id/episode_id/as_of/first_candidate_recorded_at/evidence_refs_sha256` 결선. 후일 수혜 확인·뉴스 정정은 기존 후보 최초 기록에 소급 금지.
- 테마 부재·주권 클래스 불완전·나중에 편입된 수혜주/테마 episode 는 매핑을 보류. 테마 휴면과 뉴스 재료 유효성/기존 후보 회전은 각기 다른 관측 사실. 대장주 교체 **공식 확정0**, `maturity_due_at=None` (단일 180일을 임의 투자 검증 라벨 정의로 승격하지 않음), 실제 전향적 성능 N/A.
- 원래 leader `states`, rank, 기존 WATCH 원장·보고/DB 입력 **무수정**. 기존 실전 평가/매수 주문/뉴스 크롤링 및 메시지 발송0.
- `PYTHONPATH=src python3 -m pytest tests/test_news_rotation_context.py tests/test_watch_rotation.py -q --tb=short` → **40/40 PASS EXIT0**, 2026-10-13. 통과: 기존 2+2 실수집 fixture 재사용, SHA 결정적 재실행, 원장 bytes 불변, 뉴스 없음/나중 뉴스/정정/미확정, 미래 테마 편입 차단, 미래 episode 차단, 뉴스·테마 장애시 공식 리더 교체0.

다음 ER-NC-06 이상 주가 변화와 확인된 뉴스 간 **분리형 진단**, 현시점에 없는 뉴스를 근거로 생성하지 않음.
