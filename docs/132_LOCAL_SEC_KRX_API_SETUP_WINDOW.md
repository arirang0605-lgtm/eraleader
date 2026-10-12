# EraLeader 1_2 — SEC 실연결과 로컬 KRX/DART API 키 입력창

2026-10-12. 사용자 요청에 따라 기존 `official_api_capture.py`/CLI를 **재작성하지 않고**, 현재 맥북의 SEC 무료 API를 실제 실행하고 KRX/DART 키를 채팅·GitHub에 노출하지 않고 설정하기 위한 로컬 입력 UI를 추가했다.

## 1. SEC 무료 공식 API 실연결 증거

- 미국 SEC 공식 `data.sec.gov`는 인증키/유료 가입이 필요하지 않다. 요청에 **연락 가능한 User-Agent 이메일**만 필요하다. 이번 실행에서는 Mac 로컬 Git 설정에 있던 유효한 연락처를 헤더로 선언했다. 연락처의 실제 값은 채팅·로그·GitHub에 복사하지 않는다.
- 실제 HTTP로 `sec-submissions`, CIK `0000320193`의 최신 1,001개 제출·공시 기록 수신 성공. `sec-companyfacts` 동일 CIK의 두 XBRL 분류 응답도 별도 HTTPS 실수신 성공. 최초 응답 bytes 및 수신 UTC·각 SHA receipt는 Git ignored `output/official_api_capture/first_<랜덤ID>/` 아래 owner-only 수신 원장에 있다.
- 이는 **실제 HTTPS·저장 성공**의 증거다. 해당 기업/상장주권 전체 클래스 확인, SEC 전체 역사 PIT/시세/상폐·기업행동/실전 대장주 발굴 성능 검증까지 완료된 것은 아니다.
- Mac 내부 별도 `~/Library/Application Support/EraLeader/api-credentials/official_api.env`에 SEC User-Agent가 저장되었다(폴더 0700, 파일 0600). KRX/DART 키는 아직 등록되지 않았다.

## 2. 실제 키 입력 UI

- 명령: `PYTHONPATH=src:. python3 scripts/open_api_setup.py --project /Volumes/T5DATA/eraleader --port 8768`
- 시스템 브라우저에서 **http://127.0.0.1:8768/** 오픈. 실제 사용자 Mac에서 HTTP **200** 및 `127.0.0.1:8768` 단독 LISTEN 확인, `open` 명령 성공. **외부 네트워크에는 노출되지 않는다**.
- 웹 폼에 `KRX API 인증키`(40자리), `DART API 인증키`(선택), `SEC 연락처 이메일`(로컬 Git 연락처 기본 제안)을 입력하고 'API 설정 안전하게 저장'을 누른다. 입력한 두 키의 원문은 HTML에서 재출력하지 않으며 기존 키가 있으면 입력칸을 비워도 보존한다.
- POST 동작은 loopback Host·Origin·CSRF token·입력 필드·유효 키 길이·본문 크기 상한·중복값을 검사하고, 사용자 전용 파일을 atomic replace로 저장한다. 서버 access log/외부 JavaScript/이미지/외부 폼 전송 금지, 응답 `no-store` / CSP / X-Frame-Options. 45분 뒤 일회성 입력 서버 자동 종료.
- 원래 T5DATA SSD 파일시스템은 파일을 `chmod 600`해도 실제 파일 모드가 `700`으로 남아 기존 `official_api_capture.credentials()`가 거절한다. 이번 작업에서는 권한 검사를 낮추지 않고 **Mac 내부 APFS owner-only** 저장소를 사용한다. 이번 작업 중 실험용으로 SSD에 잠깐 생성했던, Mac 내부 저장본과 bytes가 동일한 **SEC User-Agent 중복 파일만 확인 후 제거**했다. 사용자 기존 데이터는 삭제/덮어쓰지 않았다.
- 기존 `scripts/capture_official_api.py`는 사용자가 별도 `--credentials-file`을 명시하지 않았고 세 관련 환경변수도 모두 비어 있으면 Mac 내부 저장본을 자동 사용하도록 최소 수정했다. **명시한 파일 또는 환경변수 우선권은 유지**한다. CLI 원시 인증키 인자 전달은 여전히 없으며 secret 파일/사용자 이메일 원문이 에러로 출력되지 않는다.

## 3. 다음 KRX 인증·API 확인

웹 폼에 KRX 키가 저장되면 아래 순서대로 호출:

```bash
cd /Volumes/T5DATA/eraleader
python3 scripts/capture_official_api.py --project /Volumes/T5DATA/eraleader \
  --source krx-kospi --market-day 2026-10-08 --check-config
# ready=true면 --check-config를 뺀 명시적 명령으로 KRX KOSPI 실요청.
# KOSDAQ은 --source krx-kosdaq, OpenDART는 --source dart-disclosures.
```

**입력창을 열었다고 KRX/DART 키가 자동 발급·입력된 것은 아니다.** 이번 실제 `--check-config` 확인에서 SEC는 ready=true, KRX는 ready=false(아직 입력 전)이며 키 노출·KRX/DART HTTPS 실호출 0. 사용자 입력 이후 실제 API 인증 응답/저장/PIT mapping을 테스트한다.

## 4. 테스트 및 보안

```bash
PYTHONPATH=src:. python3 -m pytest tests/test_local_api_setup.py tests/test_official_api_capture.py -q -x --tb=short
```

**46/46 테스트 PASS**(신규 로컬 설정 UI 16건 + 기존 공식 API 모듈 연관 30건): 600/700 권한, 원자 저장/빈 입력 보존, 잘못된 키·가짜 이메일 거부, 외부 origin/Host·CSRF 변조·중복 form 차단, HTML 원문 키 비노출, Mac 기본 SEC 자격 읽기, 연결 환경변수 우선, 기존 KRX/DART/SEC API mock 계약 모두 확인. 실제 KRX/DART 인증 성공/전체 데이터 완전성 검증으로 주장하지 않는다.

프로젝트 기존 `native_first_capture.py`의 별도 미커밋 7줄은 절대 수정·staging·commit 금지. 전체 장기 PIT 회귀 및 SSD 물리 재연결은 사용자 기존 지시대로 API 연결 단계 이후로 유보.

## 2026-10-12 이후: 실제 KRX Chrome 승인·HTTPS 원본 검증

- Mac Chrome `API 이용현황`에서 `유가증권 일별매매정보`, `코스닥 일별매매정보` **모두 최종 승인** 상태, 이용기간 **2026-10-12~2026-11-11** 확인. 인증키는 KRX 포털과 Mac 내부 `0600` 파일이 같다는 **일치 여부만** 확인해 원문 키 비노출. 최초 HTTP 401 이후 실제 KRX 서버에 재호출해 정상 HTTP 200.
- KRX 생산 API `2026-10-08` 코스피 **942행**·코스닥 **1,823행** 총 **2,765행** 성공, 기존 `capture_official_api()` 사용해 각각 first raw bytes와 first receipt SHA256 보관 및 파일 재해시 일치 확인. `output/official_api_capture/` Git ignored. 실제 KRX 승인/HTTPS 성공과 **독립 역사 전체 PIT·상장/상폐·기업행동/독립 공시 시각 인증은 구별**한다. API 갱신일 2026-11-11 이전 재신청 필요.
- 다음 연결 단계: 생산 KRX 종목코드와 공식 법인·주권 고유 ID의 시점별 대응, DART 전체 페이지 수집과 정정 공개시각, SEC class/issuer history, 실제 PIT 후보 입력→WATCH→보고서 통합·전체 회귀. Mac Chrome의 Apple Events JavaScript 허용은 사용자 수동으로 켠 상태이고 보안 설정을 자동 해제하지 않았으므로 사용자는 완료 후 수동으로 다시 끌 수 있다.
