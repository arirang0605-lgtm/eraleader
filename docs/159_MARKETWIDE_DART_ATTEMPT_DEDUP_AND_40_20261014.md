# 2026-10-14 | EraLeader P1 공식 재무·산업 실제 40사 + 자동수집 재시도 중복 방지

- 현재 분리 브랜치 feature/core-official-factor-coverage-20261013에서 기존 KRX/DART/CFS/Industry 원형 및 첫 SHA 보존. 원본 main 미커밋 `native_first_capture.py`, 공통 API, 타 자동매매 프로젝트 수정하지 않음.
- 기존 KRX 공식 **2026-10-13 코스피941 + 코스닥1820 = 2,761** 종목, DART 해당 거래일 공식공시 456건 및 현기업 directory 재사용. 이전 연구 시장 JSON: 연간 2개년 CFS/현재 DART 산업 **30사씩**, 가격 RS 2,263사, 기관/외국인 2026-10-13 Kiwoom demo 삼성전자 1사.
- 기존 현재일 거래대금순 미수집 DART CFS 12사 자동 수집: FY2024/2025 연결 재무 **10사 완전**(금호건설·LG전자·HD현대중공업·심텍·대덕전자·LG이노텍·SK·국제약품·원익IPS·한화에어로스페이스), **2사 불완전**(KB금융·HPSP) → 값 N/A. 동일 완전 10사 공식 DART 산업코드 10/10 실측·기존 첫수신 재사용. 회사별 최신 수신을 2026-10-13 시장 관측일로 소급하지 않음.
- `extend_saved_marketwide_factors` 기존 원본 검증 증분 결합 E2E → `output/kr_20261013_marketwide_40f40i_20261014/{marketwide_kr.json,index.html}`: **KRX 2,761, CFS40, 현재산업40, 가격RS2,263, 가격+실적 50점 연구평가30사, 일치 수급1사**, 가격 WATCH20·기존 원장 원형 불변. 기존 `strategy_handoff` 프로젝트 독립 송신, 버전별 JSON SHA 검증: WATCH20, 2요소 연구 TOP20, 선정0, 주문0, 기술 WATCH 관찰 변화22건. 이는 정식 5요소100점 투자 순위/실적 예측 적중률을 뜻하지 않음.
- 기존 `official_dart_multi_company.choose_marketwide_turnover_cfs_batch` 확장과 `scripts/capture_dart_multi_company.py --skip-attempted-manifest`: 동일 거래일 원본 추적 CFS 과거 조회 배치 종목을 자동 수집 대상에서 **명시적 제외**. 신규 발행/원문 변경 없이 영구 건너뛰는 것이 아니라, 사용자가 해당 skip manifest 인자를 전달하는 경우에만 기존 실패·불완전 기업을 **중복 API 요청하지 않고 다음 후보로 이동**. 다른 세션/잘못된 대상/중복/타 API 증거는 거부.
- **실제 동일시장 queue E2E**: `output/kr_20261013_marketwide40_next12_skip_attempted.json`: 12개 후속 신규 대상을 선택, 직전 12개 회사 전부 건너뛰는 동작/원본 재활용 확인. 미래 데이터 0행을 0점으로 취급하지 않음.
- 변경 영향 pytest/소스 체크 결과 `output/verification_logs/kr_marketwide_40_and_dedup_scope_20261014.xml` 및 실 E2E 최초원본을 재확인해야 함. 기준 추후 추가 변경은 별도 결과 사용. 전체 수천 회귀·장기 역사 PIT는 정식 API 라이브 운영과 별도 최종 통합단계에서 진행.
- 다음: P1 실제 기업/섹터 데이터 범위 확대 → P2 기존 5요소 100점 실사용 기준 충족도·정식 TOP20 → P3 기존 StateHistory → P4 프로젝트 중립 송신/일·주·월 보고·알림. 완전한 영업 자료·기관/외국인·실제 경쟁력 정보가 없으면 정식 추천을 만들지 말 것.
