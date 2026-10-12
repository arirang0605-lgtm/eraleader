# ER-NC-04 — 뉴스 상태와 독립된 테마 생존·휴면·재활성화 연구 (2026-10-13)

**선행:** B00 실제 BACKUP_READY=PASS, ER-NC-01/02/03 변경영향 테스트 EXIT0.

## 구현
- `theme_lifecycle.assess_theme_lifecycle`: ER-NC-03 PIT 시점별 테마 구성과 공급된 주가 시계열 (시장당 최소 3개 class, 완료된 공통 150개 거래일), 별도 벤치마크를 기반으로 5/20/60거래일 equal-weight 수익률·benchmark 대비 RS, 참여율(20/60일선 상단), 최근 5일 거래대금/직전 60일 평균, 상위 3개 거래대금 집중도, 상위 리더 3개 20일 성과/150일선/26일 고점 낙폭을 계산.
- `EMERGING/RISING/CONSOLIDATING/WEAKENING/DORMANT/REACTIVATING/UNKNOWN`은 시점별 가격 연구용 가설. 위 상태의 임계값은 성능 검증 전 가설이고 기존 100점 대장주 점수에 자동 반영하지 않음. 뉴스 재료의 `catalyst_state`는 별도 열; **재료 확인됨+시장 휴면**을 허용하고 뉴스 미수집이 테마 종료를 뜻하지 않음.
- 전 종목 정지, PIT 멤버십 부족, 벤치마크/개별주 가격 150 세션 부족, 멤버 거래일 불일치, 데이터 미래 공급, 잘못된 신원 = UNKNOWN/차단. 단일 종목 급등으로 테마 RISING 판정 금지.
- `ThemeEpisodeStore`는 독립 신규 research SQLite에 테마별 `as_of, episode_id, state, source_sha256, payload`를 추가 전용 기록(기존 WATCH/운영 DB 수정 0). 최초/재활성 episode는 새 ID, 휴면 전 이력 보존, 동일 스냅샷 재실행 멱등, 뒤늦은 과거재기록 거절.
- 실제 국내외 전체 PIT issuer/share class/기업행동과 시장 구성의 공인 인증은 없음; 공식 leader/성과 인증값은 **0/N/A**.

## 테스트
`PYTHONPATH=src python3 -m pytest tests/test_theme_lifecycle.py tests/test_theme_pit_catalog.py -q --tb=short` → **37/37 PASS, EXIT0**. 합성 5개 시장 상태, 뉴스 사실/가격 상태 분리, 최초 RISING→휴면→재활성 episode 리셋, 기존 episode 지속, 재실행 SHA, 단일 종목/전 종목 거래정지/시세 결손/미래 데이터/구성 거래일 불일치/공인유니버스 결손, 독립 SQLite 멱등 및 역순 보류 재오픈 PASS.

다음 ER-NC-05 기존 WATCH 회전 히스토리에 테마 episode/뉴스 근거 추가(정식 후보 승격이 아닌 연구 가설).
