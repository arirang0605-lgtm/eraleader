# EraLeader 2_2 · 2_5 · 4_1 · 6_5 — 제3 거래소 명부 WATCH 엄격모드 최초 고정/다운그레이드 차단

> 2026-10-12 KST. 이번 릴리스는 *이미 실행 가능한* `docs/109`의 원본 A/B PIN + 별도 issuer/share class + 제3 whole-exchange roster 검증을 **동일 출력 저장소의 후속 실행에서도 빠뜨리지 못하도록** 하는 로컬 안티 다운그레이드 기능이다. 공인 거래소 원본·외부 최초 게시시각·실전 대장주 적중률을 검증하는 기능은 아니다. D-017 API와 D-021 SSD 물리 탈착·재연결/맥북 재부팅은 최종 단계.

## 실질적으로 없던 기능

직전 `offline-integrated --require-provider-exchange-roster --provider-exchange-roster ... --provider-exchange-roster-sha256 ...`는 실행 **한 번**의 엄격한 첫 원본 검증에만 적용됐다. 이후 동일 `output` 루트를 사용하면서 이 플래그를 누락하면, 과거 약한 공급자 검증으로 새로운 연구 WATCH가 기록될 수 있었다. 통합 배치가 `execute_integrated()`를 직접 호출할 때도 같은 보호가 필요했다.

## 구현과 실행 시 안전성

- 신규 `src/eraleader/exchange_roster_policy.py`의 `guard_integrated_policy(out, market, strict_mode=...)`는 **시장 KR/US를 분리**한 SHA 봉인 정책. 이미 정상인 `execute_integrated`를 얇은 래퍼로 보호하므로 CLI 호출뿐 아니라 기존 batch의 직접 함수 호출에도 적용한다. ***엄격 모드를 요청하지 않은 기존 output에서*** 파일/잠금 생성 없이 기존 기본 연구 흐름을 유지한다.
- 최초로 **정확한** A/B 원시 PIN 4개, issuer 계보, 명부 원본 및 자체 SHA, 3-way option의 완전성을 갖춘 옵션이 실행되면 ***시장 DB를 열거나 실행/후보 WATCH 원장을 변경하기 이전*** `provider_exchange_policy_kr.json`(또는 `us`)을 `O_CREAT|O_EXCL|O_NOFOLLOW`로 처음 기록한다. 이후 독립 파일 `provider_exchange_policy_guard_kr.json`(또는 `us`)에 원본 canonical bytes SHA/nonce SHA를 기록하여 부분 손상/소급 변조를 차단한다. `.provider_exchange_policy_kr.lock`(또는 `us`)의 OS `flock`으로 경쟁을 직렬화한다. **필수 입력을 빠뜨린 요청은 정책잠금 파일 생성 전** 차단한다.
- 이 정책은 최초 실제 거래소 명부의 **그날 SHA를 사고검증용 first-write 기록으로** 보존하지만, 그 특정 일자의 종목 명부를 영구 동결해 다음 거래일 명부를 가로막지는 않는다. **매 후속 실행은 새 원본명부/해당 날짜 claimed PIT 수신시각과 SHA를 전체 재검증해야 한다.** 최초 정책을 한 번 봉인한 시장에서는 `offline-integrated` 재시도나 batch 인프로세스 호출 시 필수 게이트 입력을 제거할 수 없다. 무옵션/두 공급자만/issuer만/모든 약한 게이트 옵션은 ***원본 offline.sqlite에 접근하기 전*** 실패; 뒤늦게 보강된 로컬 증거가 존재하더라도 `research_watch_allowed`가 공식 인증이 되지는 않는다.
- 최초 엄격 **원본 검증이 실패해 WATCH 0**이더라도 이미 엄격 정책을 선택한 출력루트는 이후 약한 모드로 돌아갈 수 없다. 잘못된 원천은 **같은 강한 모드**로 증빙을 보완해 다시 검사해야 한다. 정책/guard 중 1개 유실·수정·비정상 JSON·SHA 불일치·검증용 .lock만 남고 두 봉인 모두 없는 경우는 ***자가 재가입/새 Genesis 발급 금지***, 명시적으로 복구 전 실행을 차단한다.
- protected `offline-integrated` 실행 전·WATCH 게이트 산출물 작성 직전·신규 run/종목 상태 및 prospective WATCH 기록 직전에 정책 불변을 재검사한다. `source_pair_digest_sha256` 및 original first-ingest raw PIN/issuer/roster 조건 자체는 `docs/109` 기능을 재사용하며 정상인 후보 점수·전략·공시 분류·백테스트를 바꾸지 않는다.
- ***원본 종목ID/공급자 원천 경로/비밀키는 정책·guard에 포함하지 않는다.*** 시장/엄격 최소 게이트/최초 roster raw SHA(공개될 수 있는 연구용 해시)/로컬 UTC OS first observation/무작위 nonce/공식 PIT 불인증 상태만 보관한다. 내부 발생한 임시 OS 시각은 최초 시장·거래소 발행기관의 외부 공증이 아니다. 정책 파일 2개를 한 명의 관리자/공격자가 **함께** 다시 서명해 교체하거나 모든 봉인+잠금 파일을 함께 삭제하면 단일 장비만으로 탐지할 수 없다. 운영에서는 독립 외부 시각/발행기관 증명이 필요하다.

## 활성화와 복구

기존 엄격 명령을 **그대로 한 번 실행하면 자동 첫 봉인**된다. 새 별도의 설치 단계, 외부 API, 토큰 발급, 실제 launchd 설정 변경은 없다. 첫 봉인 뒤에는 **동일 output 루트의 동일 KR/US 시장**에서 `docs/109`의 `--require-provider-exchange-roster` 포함 전체 원본 플래그를 매번 입력해야 한다. 한국 정책은 미국 정책을 잠그지 않고, 미국을 엄격하게 실행한 시점부터 미국도 별도 보호된다. 기존 `docs/109`의 opt-in 이전에 발생한 연구 신호·잠깐 누락된 기록을 소급 인증할 수 없다.

파생 `provider_exchange_policy_{kr,us}.json` 및 `provider_exchange_policy_guard_{kr,us}.json`를 `local_backup.JSON_NAMES`에 **정확히 네 이름**만 추가하여, 기존 안전 ZIP SHA 검증 + 새 디렉터리 복원에서 양쪽 봉인 보존 여부 확인. `.lock`은 상태보존 백업 대상이 아니고 복원된 디렉터리에서 다음 실제 protected 실행 시 다시 생성한다. **봉인 손상 시 파일을 삭제하거나 새 정책을 자동 덮어쓰기 하지 않는다.** 복구는 현존하는 검증된 로컬 ZIP 백업에서 새 위치에 복원·양쪽 파일 SHA 확인 후 실제 원본 ledger/서류 증빙과 합쳐 적법하게 재실행하는 방식만 연구용으로 검증했다. 기존 source/data/raw 가격을 GitHub에 올리지 않는다.

## 테스트 기준

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests/test_exchange_roster_policy.py -q --tb=short
PYTHONPATH=src python3 -m pytest tests -q --tb=short
python3 scripts/check_handoff.py
python3 scripts/check_git_safety.py
```

- 신규 `tests/test_exchange_roster_policy.py`: KR/US 한 번 엄격 실행→시장별 첫 정책+guard 봉인/같은 모드 재실행 정책 불변; 그 뒤 약한 세 가지 입력 모드 차단+기존 offline DB/first WATCH/run/GATE 결과 불변; 원래 엄격 불일치도 양호한 로컬 자료가 오기 전까지 약화 실행 차단; 정책 1개 삭제/둘 다 지워짐/.lock만 생존/변조/가짜 공식 PIT/원본 SHA 재해시; O_EXCL·simultaneous flock; 정책 source hash first-write가 특정 날짜에만 고착되지 않음; 정책 등록 당시 입력 불완전 시 파일 미생성; 재검증 도중 marker 변조한 뒤 WATCH 발행0; 기존 기본 모드 무영향; direct batch 함수 entrypoint 봉인; 안전 ZIP 새 위치 복원 후 무옵션 downgrade 차단.
- 이 테스트는 투자 성과·법적 issuer/등재 명부 진실성·최초 공시 시각의 증명력이 없으며, 전향적 미래 outcome과 KRX/DART/SEC API 연결은 별도 미완료다.
