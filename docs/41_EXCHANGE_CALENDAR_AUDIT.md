# 2_2 / 2_5 — 외부 API 없이 거래소 캘린더 대비 전체시장 누락 감사

> 2026-10-10 KST. 실제 공인 캘린더는 아직 입력하지 않았음. 아래 누락 탐지 사례는 로컬에서 만든 **명시적 합성 캘린더/합성 가격**이다. API 호출, 실전 가격 재다운로드 0회. 한국·미국 실제 상장종목군/상폐/기업행동 PIT 인증 0건.

## 구현 범위

- `src/eraleader/calendar_audit.py`: `eraleader.exchange_calendar_reference.v1` 형식의 **사용자 제공 로컬 JSON**에 명시된 시장, 출처 ID/발행자(주장), 타임존을 포함한 검색/획득 시각, 달력 범위, 거래일/휴장일, completeness 주장 필드를 검사한다. 파일 SHA256을 계산하되 공신력 있는 원천·시점의 *독립 확인*이라고 주장하지 않는다.
- `src/eraleader/cli.py`의 신규 `audit-calendar --file ... --market KR|US --as-of ... --legacy ... --days ... --out ...` 명령은 기존 **read-only** 가격 어댑터로 읽은 종목별 바와 별도 입력 달력을 비교해 전체시장 관측 기간 누락 후보, 가격에만 존재하는 기간, 상세 근거/미인증 플래그를 `calendar_kr_research.json` 또는 `calendar_us_research.json`에 저장한다.
- 한국은 **일별** 세션, 미국 기존 파일은 **종목마다 다른 요일에 찍힌 주봉**이므로 Monday–Sunday **주별** 비교. 미국 주별 종가 날짜를 개별 일봉 거래일처럼 비교하지 않으며, 가격의 첫~마지막 관측 기간 *사이만* 평가한다. 범위 밖 미래 휴장/상장을 추정하지 않는다.
- 미래 가격·중복 세션·달력 기간 부적합·거래일/휴장일 중복·역순·날짜/시간대 누락·가짜 completeness 타입·다른 시장 ID 등을 fail-closed 처리한다. 미검증 공급자 주장이나 `retrieved_at > as_of`인 사후 수집 달력은 결코 PIT 인증받지 못한다.
- 기존 `continuity_audit.py`의 종목별 공백 감사와 별개. 필요시 이력 연속성 감사 연결에 사용할 `load_calendar_manifest`/`compare_calendar_periods`도 제공하되 독립 인증 플래그는 항상 false.
- `src/eraleader/local_backup.py`는 **파생 감사 결과 JSON 두 종류만** 백업 허용한다. 거래소 달력 원본, 벤더 가격 Parquet, API 키/원시 시세는 ZIP/Git에 넣지 않는다.

## 실측한 로컬 명령

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_calendar_audit.py tests/test_local_backup.py -q
PYTHONPATH=src python3 -m pytest tests -q
python3 scripts/check_handoff.py

# Git ignored output/calendar_contract_20261010/의 합성 가격 Parquet와
# 합성 거래소 캘린더. 실제 시장의 거래일/상폐 판정으로 사용 불가.
PYTHONPATH=src python3 -m eraleader audit-calendar \
  --file output/calendar_contract_20261010/kr_calendar.json \
  --market KR --as-of 2026-10-10 --days 35 \
  --legacy output/calendar_contract_20261010/synthetic_legacy \
  --out output/calendar_contract_20261010/kr_output
PYTHONPATH=src python3 -m eraleader audit-calendar \
  --file output/calendar_contract_20261010/us_calendar.json \
  --market US --as-of 2026-10-09 --days 35 \
  --legacy output/calendar_contract_20261010/synthetic_legacy \
  --out output/calendar_contract_20261010/us_output
```

- 한국 합성 가격은 Oct 05/06/08/09, 선언 캘린더는 Oct 05~09 => 10월 7일 전체시장 관측 누락 **1회 탐지**.
- 미국 합성 주봉은 Sep 22/Oct 06, 선언 캘린더는 Sep 21·28·Oct 05 => 9월 28일 시작 주 **1회 탐지**. 주간 관측 요일 불일치는 가짜 누락이 되지 않는다.
- 실제 현금주식 시장 원천의 캘린더 파일은 T5DATA 기존 엔진의 범위 제한 검사에서 별도로 발견되지 않았음. 사용자 제공 synthetic reference의 ID 문자열이나 해시만으로 거래소의 실제 거래일/공시 공개시각을 인증할 수 없음.
- 로컬에서 각 시장 파생 JSON 1개씩 ZIP SHA256 검증 및 새로운 경로로 복원 PASS. 각각 `output/continuous/calendar_contract_{kr,us}_20261010.zip`; 원시가격/비밀자료 제외.
- 테스트: 신규 캘린더 소스 계약 및 US 주봉/한국 일봉/백업 경계 사례, 전체 테스트 PASS. *동시 개발 세션의 워크포워드 코드/테스트가 작업 폴더에 있으므로 현재 전체 테스트 수는 마지막 검증 명령에서 재확인; 우리 캘린더 코드와 별도 staging 유지.*

## 남은 막힘

공신력 있는 거래소 과거 세션 캘린더 제공자 및 취득 시각의 독립 증거 확보 전에는 `calendar_pit_certified=false`. 상장/상폐 사건·합병/분할/배당 원천과 delist proceeds, 금융공시 PIT, 살아남은 미국 종목군 등도 미인증. 5단계 대장주 조기발굴 실증은 봉인된 미래 결과가 성숙할 때까지 측정할 수 없다.
