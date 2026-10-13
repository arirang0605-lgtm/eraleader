# 156 — 한국시장 2,765개 종목 실사용 검색·상세 화면

**2026-10-14 KST · 개발 ID 1_1·3_3·3_4·3_5·6_2 · 사용자 D-027/D-030**

## 문제와 구현된 실제 사용 기능

기존 `official_marketwide_coverage.py`의 사이트는 KRX 전체 관측 2,765개 종목의 **결측현황과 상위 가격 WATCH20/연구 TOP20만 표시**했다. 사용자가 임의의 종목을 검색하거나 시장별·재무 이용가능성·기존 상대강도를 확인하는 화면이 없었다.

- 새 `src/eraleader/marketwide_live_search.py`, `scripts/publish_marketwide_search.py`: 기존 **완료된 SHA 기반 `marketwide_kr.json` 파일만** 읽어 코드·회사명 검색/코스피·코스닥 필터/과거 주가 강도·실적·2요소 점수 자료충족 필터/연구 점수·거래대금·종목코드 정렬/50행 페이지네이션/개별 종목 상세 보기를 지원한다.
- **결측 대응:** 매출·영업익·가격·산업 정보가 없으면 N/A, 정식 100점 리더·기관외국인 수급·매수 우선순위는 생성하지 않는다. 기존 부분요소 0~50 연구점수는 해당 2가지 데이터가 있는 종목에만 표시하고, 2765개 전종목의 실제 매수 1~20위가 아님을 명시한다.
- **날짜:** KRX 실제 가격 관측일, 최신 소스 분석·발행시각, 사용자가 요청한 날짜를 분리. 공식 거래소 휴장 달력은 미인증이므로 평일 간격을 추정·경고만 하며 2026-10-08 관측을 2026-10-14의 시세/투자판단으로 소급하지 않는다.
- UI 내부 데이터는 `script type=application/json`로 HTML 자체에 포함되어 인터넷 없이 파일로 열어도 코드/종목명·자료충족·검색/정렬/상세가 작동한다. 사용자 공급 데이터는 HTML 태그가 아닌 `textContent`로 출력하고 script 탈출문자를 유니코드로 안전 이스케이프한다.
- **원본 보존:** 기존 KRX·DART SHA, 시장 가격/WATCH 원장/StateHistory/해당 날짜 기존 사이트/중립 strategy outbox, 타 프로젝트 코드는 전혀 수정하지 않는다. 원본 1.6MB 캐시를 읽기 전용으로 교차 검증하며 **새 로컬 output 폴더에만** HTML+manifest 두 파일을 원자적으로 생성한다. API/키움 추가 조회·주문·수신 프로젝트 선택 0.

## 실사용 명령

이전 공식 보관본을 재수집하지 않고 검색 사이트를 새로 생성하는 예시:

```sh
cd "/Volumes/T5DATA/2.EraLeader_통합관리/02_개발워크트리/eraleader-marketwide-search-20261014"
python3 scripts/publish_marketwide_search.py \
  --source "/Volumes/T5DATA/eraleader-core-factor-coverage-20261013/output/marketwide_kr_33f33i_fullprice_20261014/marketwide_kr.json" \
  --day today \
  --out "$PWD/output/marketwide_search_new_$(date +%Y%m%d)"
```

실제 검증된 결과는 `output/marketwide_kr_search_20261014/index.html` 및 `manifest.json`이다. 다른 날짜나 새 정보가 들어오면 **원본 전시장 보고서가 먼저 갱신된 이후** 새 디렉터리로 발행하며, 이전 날짜·SHA 파일을 덮어쓰지 않는다. 이 UI 구현만으로 매일 KRX 실수신/정식 5요소 선정이 자동화된 것으로 주장하지 않는다.

## 실제 Mac/T5DATA 실측

- 기존 공식 **2026-10-08 KRX 가격 관측 2,765**개 (코스피 942/코스닥 1,823), 2026-10-14 로컬에서 확보된 3FY/2FY CFS+업종 **33개**, 기존 read-only marcap 과거 가격 강도 **2,261**개, 가격+실적 **2요소 연구점수 25개**, 정식 공인 100점/선정 **0개**. 같은 시점 자료라고 섞지 않음.
- 원본 `marketwide_kr.json` canonical SHA, 각 종목6자리/중복/정식점수 미승격·TOP20 실제 정렬·자료충족 숫자를 확인한 뒤 생성 성공. 신규 결과 `index.html` 약 1.1 MiB + `manifest.json` 841 bytes. `manifest.json` content SHA 재검증 PASS, 브라우저 렌더용 2,765개 JSON 파싱·25개 2요소 평가 수 확인.
- 로컬만 열어 본 HTTP `index.html`, `manifest.json` **각 200**; HTML inline JavaScript 추출 후 Mac `node --check` PASS.
- 신규 `tests/test_marketwide_live_search.py` **17/17 PASS**, 기존 시장전체 결합·기업 상세 조회 포함 변경 영향 **3모듈 43/43 PASS EXIT0**. 원본 SHA 변조·중복ID·미래날짜·결측점수·정식 확정위조/HTML 주입·출력 덮어쓰기 거부 포함. 시험 증거 Git 제외 `output/verification_logs/marketwide_search_final_scoped_20261014.xml`.
- 원본 main `/Volumes/T5DATA/eraleader`의 미커밋 `native_first_capture.py` 및 다른 프로젝트/공식 수집기 파일 보존. **병행 기능개발과 충돌을 피하도록** 최신 확인된 `fa78c82` SHA 기준 별도 feature/kr-marketwide-search-20261014 worktree 안에서만 새 기능을 구현했다.

## 다음 구현

1. 이 검색사이트를 기존 EraLeader 메인 대시보드의 종목검색 메뉴로 연결하고, 최신 원본 수신이 가능한 날에는 자동으로 최신 보관된 시장·실적 자료를 표시한다.
2. 공식 기관·외국인 수급 동일 거래일, 산업 성장·기업 경쟁력, 성과 가속을 5요소 점수에 실제 연결한다. 모자라는 요소는 N/A로 보고하며 임의 성과/정식 선정 승격하지 않는다.
3. 실제 대장주 상태 이력이 준비되면 기존 **프로젝트 중립 JSON 송신** 기능으로 연결한다. 수신 프로젝트 선정·어댑터 구현은 사용자 별도 결정 후 수행한다.

- **기존 부분 보고와 호환:** 전시장 과거 주가 일괄 조회가 없던 시장전체 28사 보고서도 정상 검색 발행 PASS (2요소 평가 20종목). 과거 WATCH의 가격강도 관측값을 전체 2,765개 가격강도 검증으로 부풀리지 않음.
