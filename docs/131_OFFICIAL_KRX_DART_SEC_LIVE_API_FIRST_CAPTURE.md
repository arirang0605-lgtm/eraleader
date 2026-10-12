# EraLeader 1_2·2_1·2_2 — 실제 KRX/DART/SEC API 최초 원문 수신 연결

2026-10-12. 사용자 지시로 **API 연결 단계를 개시**. 기존 EraLeader PIT 정규화/first SHA/후보 WATCH의 정상 동작과 분리해, 공인 서비스의 현재 HTTP 응답을 그대로 읽고 **새로운 원시 수신본 + 최초 로컬 수신시각 + 고유 SHA 영수증**을 비공개로 저장하는 최초 얇은 연결을 구현했다. 실제 최초 API 제공자 인증, 기업의 법적 share-class identity, 모든 상장종목/기업행동 역사 등은 **별도 독립 검증**을 거쳐야 하며 통합 WATCH 자동 승격은 금지한다.

## 현재 지원 공식 엔드포인트

| 소스 | 요청 | 실제 URL | 인증 | 1회 캡처 범위 |
| --- | --- | --- | --- | --- |
| `krx-kospi` | 날짜 YYYY-MM-DD | `https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd` | 승인된 `AUTH_KEY` 헤더 | KOSPI 일별 종목 거래 1일 |
| `krx-kosdaq` | 날짜 YYYY-MM-DD | `https://data-dbg.krx.co.kr/svc/apis/sto/ksq_bydd_trd` | 승인된 `AUTH_KEY` | KOSDAQ 일별 종목 거래 1일 |
| `dart-disclosures` | 날짜 YYYY-MM-DD | `https://opendart.fss.or.kr/api/list.json` | 발급된 `crtfc_key` | 공시 목록 1일의 **첫 페이지만** |
| `sec-submissions` | 개별 CIK | `https://data.sec.gov/submissions/CIK##########.json` | **실제 운영자 연락처가 명시된 User-Agent 필수**, 별도 인증키 없음 | 최근 EDGAR 제출정보 |
| `sec-companyfacts` | 개별 CIK | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | 동일 User-Agent | EDGAR 공시 XBRL 회사별 항목 |

KRX: https://openapi.krx.co.kr/contents/OPP/USES/service/OPPUSES002_S2.cmd?BO_ID=PiwgMdTwmsenXhmqqxuj / DART: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001 / SEC: https://www.sec.gov/search-filings/edgar-application-programming-interfaces 및 https://www.sec.gov/about/webmaster-frequently-asked-questions .

**중요**: `provider_export_normalizer.py`의 KR `corp_code+issue_uid`, US `CIK+share_class_uid` 계약은 각 기관의 raw API 한 번만으로는 완성되지 않는다. `krx` 단축 종목코드나 `SEC` CIK만으로 영구 주권/클래스 ID를 만들어 기존 WATCH에 강제로 투입하지 않는다. DART `rcept_dt`는 **접수일 날짜만**이며 분 단위 최초 공개시각이나 독립 확보시각이 아니다. SEC submissions의 개별 `acceptanceDateTime`도 제공자는 공시 제출시각으로 주장하지만 우리 시스템의 최초 확보는 별도 현재 OS 시각이다. 무권한/부분 응답은 강제로 보충하거나 성공으로 위장하지 않는다.

## 비밀키 보관 — ChatGPT/GitHub에 키를 보내지 않음

현재 SSD의 `.secrets/`에서는 설정 파일이 발견되지 않았으며 EraLeader 세 환경변수도 비어 있었다(확인 시각 2026-10-12). **실제 HTTPS 인증 호출을 성공했다고 보고하지 않는다**. 실제 인증 전 사용자가 맥에서 다음 비공개 파일을 생성해야 한다. 아래는 설명용 **자리표시자**이며 실키를 코드/터미널 공유 로그에 붙이지 않는다.

```text
/Volumes/T5DATA/eraleader/.secrets/official_api.env
ERALEADER_KRX_AUTH_KEY=<발급받은 KRX 40자리 키>
ERALEADER_DART_API_KEY=<발급받은 OpenDART 40자리 키>
ERALEADER_SEC_USER_AGENT=EraLeader Research <실제 담당자 연락 이메일>
```

터미널에서 `chmod 700 /Volumes/T5DATA/eraleader/.secrets`, `chmod 600 /Volumes/T5DATA/eraleader/.secrets/official_api.env` 필수. SEC 항목은 실제 연락처 이메일을 명시해야 한다. 해당 값 중 하나만 준비됐으면 그 공급자 **하나만 사용**할 수 있다. 이 파일은 `.gitignore`로 GitHub 업로드 제외. `--credentials-file`은 반드시 절대 경로·owner 0600 소유 파일로만 사용; 환경변수 `ERALEADER_...`도 가능. 인증키를 CLI 옵션으로 직접 입력하지 않는다. KRX 공개 *샘플 인증키*는 실운영 승인키를 대체하지 않는다.

## 실행 — 서비스 연결 전 설정 점검

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/capture_official_api.py --project /Volumes/T5DATA/eraleader \
  --source krx-kospi --market-day 2026-10-09 \
  --credentials-file /Volumes/T5DATA/eraleader/.secrets/official_api.env --check-config
```

`--check-config`는 요청 형식과 인증정보 **존재 여부만** 확인, 인증키의 진위 확인·API 호출·파일 저장 **0건**. 정상 설정 이후 `--check-config`만 제거하면 실제 HTTPS 첫 수신을 수행한다. KRX는 `--source krx-kosdaq`도 동일 날짜로 별도 실행, DART는 `--source dart-disclosures`로 실행한다.

미국은 `--source sec-submissions --cik 320193` 또는 `--source sec-companyfacts --cik 320193`. User-Agent/운영자 이메일은 환경변수 또는 비공개 설정에서 읽으며 API에는 필수 선언 헤더로만 들어간다.

응답 본문은 Git ignored `output/official_api_capture/first_<랜덤ID>/raw_response.json`, 최초 증거는 같은 0700 비공개 폴더 안의 0600 `first_receipt.json`. CLI stdout에는 원시가격/법인ID/기업명/키/원본 URL 대신 총 행수/품질/최초 수신시각/원문 SHA/영수증 SHA만 출력. 비밀번호·URL에 포함된 DART 키·비공개 원본 경로는 stderr 오류에서도 출력하지 않는다. 사용자가 첫 `first_receipt_sha256`를 **다른 신뢰 저장소**에 별도로 보관하기 전에는 독립 증명이라 주장할 수 없다.

## 안전 계약

- 네트워크 대상 URL 5개 고정, HTTPS, `timeout=18초`, 리다이렉트 거부, 바이트 최대 24 MiB, JSON 중복키/허위시장 날짜/잘못된 CIK/DART 인증오류 거부, 원본 파일 신규 O_EXCL mode0600 / private 디렉터리 원자 rename.
- DART `status=013`은 공시 없음으로 구분; `total_count > 1페이지`면 `INCOMPLETE_FIRST_PAGE_NOT_FULL_DAY` 명시. KRX 0거래행은 `NO_DAILY_ROWS`, *상장종목 0건/전수 역사 PIT 증명 아님*.
- 원본 raw API는 취득 당시 HTTP bytes 그대로 보존, 로컬 `first_local_received_at_utc`는 **실제 호출이 끝난 시점**만. 공급자가 과거에 언제 처음 제공했는지/실제 거래 가능했는지는 이 증거만으로 추론 불가.
- 한 API 정상 원문을 두 독립 공급자라고 가짜 중복해 `onboard_provider_pair`를 통과시키지 않는다. 공식 영구 ID·정정·상폐 정산 및 PIT 완성 전에는 리서치 WATCH/confirmed leaders 생성·기존 실전 워치 자동갱신 없음. API 호출은 사용자 **명시 CLI 호출**에서만, 자동 스케줄·실거래·메시지 발송0.
- 테스트 파일 `tests/test_official_api_capture.py`는 모두 가상 JSON/가짜 헤더·가짜 송수신 함수를 사용하므로 이것이 **실제 API 호출 통과**를 의미하지 않는다. 실제 인증키가 설치되면 각 공급자 1회 live 스모크→첫 원문 SHA/영수증 검증→적격 ID/공시 timestamp mapping 보강→기존 PIT 파이프라인 연결→**전체 회귀** 순서.

D-021 실제 SSD 물리 탈착/맥북 재부팅은 API가 완성된 뒤에만 시행한다. 신규 API 연결 단계 진척은 실제 인증 응답과 본격적인 주도주 미래 예측력 증명이 달성된 뒤에만 기록한다.
