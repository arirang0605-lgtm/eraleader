# ER-NC-02 — 당시 이용 가능한 시장 국면·신규매수 연구 게이트

선행: B00 BACKUP_READY=PASS, ER-NC-00 경계 확인, ER-NC-01 read-only 뉴스 PIT **46 PASS/EXIT0**.

## 실제 구현
- `src/eraleader/market_regime_experiment.py`: `market_regime_snapshot`, `entry_permission` 독립 모듈. 원래 `states.py`/WATCH/저자 전략의 매매 신호는 변경0.
- KR_KOSPI/KR_KOSDAQ/US_SP500/US_NASDAQ100 연구 시각·거래소 시간대, **완성된 일별 종가 170세션 이상**과 150일/20일 MA, 150일선의 20세션 기울기, 20/60 MA 관계, Wilder ADX14/+DI/-DI, PIT 구성종목의 60일선 상회율을 각각 계산.
- 시장 `RISING/SIDEWAYS/FALLING/TRANSITION/UNKNOWN`으로 연구용 판정; PIT 회원목록 인증/최초 관측일/멤버 적용기간·가격/현재 세션/충분한 과거 없으면 UNKNOWN. 역사적 현재 멤버십으로 과거 breadth 소급 금지.
- 모델 입력 미래 시각·미완성 봉 제거, 거래소 현지 날짜 다르면 UNKNOWN, 데이터 관측 7일 초과 지연시 UNKNOWN. 외부 뉴스 수집과 무관하게 별도 가격 연구.
- 정책 `BASE_AUTHOR_ORIGINAL`은 원형 그대로, `GATE_STRICT_UPTREND_V1`은 RISING에서만 **신규매수 연구 허용**; 횡보/하락/전환/불명은 불허. STOP/EXIT/RISK_REDUCE는 신규매수 게이트와 독립.
- ADX25, breadth55%, MA slope1% 등은 연구 가설임. 실제 투자 우위·실거래 진입·저자 원형의 일부로 주장/강제 금지.

## 테스트
- `PYTHONPATH=src python3 -m pytest tests/test_market_regime_experiment.py tests/test_news_catalyst_adapter.py -q --tb=short`: **50/50 PASS, EXIT0**, 2026-10-13.
- 합성 4개 상태 및 UNKNOWN, 한국/미국 4개 시장, 150일 이상 종가·ADX·DI, 거래일 결측·멤버십 미래 편입·동일 종목 중복·가격 지연·미완성 봉·거래소 시각·미국 현지시장 세션·중복 세션·원형 신호 및 손절 유지.
- 기존 MarketOS/자동거래 연결0, 체결가 가정0. B00 백업·원래 `main`/native_first_capture.py 사용자 미커밋 보존.

다음은 ER-NC-03 불변 테마ID·현재 당시 issuer/security class membership와 뉴스 hint 비확정 매핑이다.
