# EraLeader 개발 연속: 3_4·3_5 / 4_2~4_5 / 5_2 일부 / 6_2 일부

> 실제 구현·테스트 2026-10-10, 로컬 SSD /Volumes/T5DATA/eraleader.
> 목표: 미래 대장주 조기 발견. 과거/가상 자료는 검증용이며 **검증 완료 전 실제 확정 후보 발표 금지**.
> API/스크래핑/데이터 다운로드/라이브 알림 전송 0건.

## 1. 이번에 추가한 실제 코드

| 모듈 | 단계 및 상태 | 수행 기능 |
|---|---|---|
| `src/eraleader/research.py` | 3_4·3_5 부분 구현 | 산업·실적과 가격 RS 동일 시점 결합, 시장 불일치·과거 날짜와 가격 행 불일치·미래 가격·중복·오래된 가격 차단, 미검증 종목코드 join 명시 |
| `src/eraleader/state_history.py` | 4_2~4_5 연구용 상태 이력 구현 | WATCH/POTENTIAL/CONFIRMED/WEAKENING/PAUSED/EXITED 상태 전이, 두 번의 근거 확인, 첫 후보 선정일·이벤트 저장, 과거 입력 변조·소급 입력 원천 차단 |
| `src/eraleader/discovery_metrics.py` | 5_2 조기 발견 평가기초 | 최초 발견 시점 vs 훗날 검증 라벨, precision/recall/lead time/false discovery/late detection/censored(평가 미완료) 구분. 부정확한 모집단 recall은 N/A |
| `src/eraleader/delivery.py` | 6_2 오프라인 웹 확장 | 산업·기업·가격 통합 화면 `research_kr.html`/US, 근거/결측/비인증 상태 표시, HTML escape 및 승인되지 않은 공식 후보 표시 차단 |
| `src/eraleader/cli.py` | 인터페이스 확장 | `offline-integrated` / `validate-discovery` 명령. 기존 명령과 코드 보존 |
| `tests/test_research.py` 등 | 49개 자동 테스트 | cross-market/cutoff/가격 미래 유입/중복/시점 보존/상태 전환/중복 이력/평가 시점/웹 출력, 기존 테스트 재검증 |

## 2. 실행 검증

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m eraleader offline-integrated \
  --market KR --as-of '2024-09-01T17:00:00+09:00' --out output/demo_offline
PYTHONPATH=src python3 -m eraleader validate-discovery \
  --signals tests/fixtures/early_signals_synthetic.json \
  --outcomes tests/fixtures/leader_outcomes_synthetic.json \
  --evaluated-at 2024-10-01 --out output/demo_offline
PYTHONPATH=src python3 scripts/verify_local_mvp.py
python3 scripts/check_handoff.py
```

**확인 결과:** 전체 pytest **49개 PASS**. 통합 연구 JSON `output/demo_offline/runs/joined_kr_*.json`·HTML `output/demo_offline/site/research_kr.html` 생성. 검증 도구 예시(100% 합성): 조기발굴 1건, 오탐 1건, 검증 전 1건(실제 종목/성적 아님). 기존 한국/미국 정적 웹 3경로 localhost 200, 핸드오프 PASS. 로컬 비밀키 디렉터리 `.secrets/` 소유자 전용 권한, Git 추적 제외.

## 3. 완료/미완료 경계

**코드와 자동 테스트가 확인된 것:** 가격/재무 PIT 요약 로컬 결합, 과거 이벤트 변조 차단, 조기 발견 평가 공식, 로컬 웹 렌더링, 기존 dry-run 알림/일주월 보고.

**아직 완료하지 않은 것:** 시장 전체 원천 PIT 정합성 인증, 누락된 실제 과거 재무/산업/컨센서스/투자자 수급, 상폐·분할·배당을 포함한 엄격한 투자 성과, 산업별 영구 security_id 매핑, 진짜 대장주 정답 라벨 사전 등록, walk-forward 및 independent out-of-sample, 오탐 교정, 실제 가격·기업 피처를 잇는 대규모 전체시장 재생, GUI 최종 사용자 품질, 일/주/월 운영 자동화, 실전 외부 알림. **30개 작업을 완료로 표시하지 않는다.**

실제 `OfflineLedger`가 보고하는 과거 PIT 커버리지 플래그는 모두 false. 전체 점수 100점과 모델상의 잠재/확정은 기본 차단.

## 4. 다음 개발을 승인 질문 없이 이어갈 순서

1. **2_2·2_5 보강:** 상장폐지/기업행동 PIT 조정 수익률 검증, historical universe completeness audit.
2. **3_1~3_5 강화:** 오프라인 실제 공시/산업 자료가 없는 상태에서 검증 가능한 가격·산업·기업 자료의 품질 등급을 분리하고 조기 후보 recall/lead-time 평가를 사전 정의.
3. **4_2~4_5 실데이터 연계:** Source completeness manifest/version 기반 상태 승격. 가상 fixture만으로 실전 후보 승격 금지.
4. **5_2~5_5:** PIT 워크포워드, 시장 생존편향 점검, 봉인 홀드아웃, 조기 발굴 vs 단순 모멘텀 ablation, 오탐 통계.
5. **6_1~6_5:** 통합 웹 내 실제 발굴 근거/운영 지표, 로컬 스케줄·일/주/월 보고·dry-run 알림의 회복성/사용 편의성 테스트.
6. **API는 이 로컬 1~6단계 기능 통합 테스트 완료 후** 연결. 사용자 요청에 따라 다음 개발부터 추가 승인 질문 생략.

## 5. GitHub 보안/연속성

- GitHub Public 저장소 `arirang0605-lgtm/eraleader` 사용을 2026-10-10 사용자가 명시 승인.
- 로컬 비밀키 보관: `.secrets/` (chmod 700), 실제 키 값 **현재 없음**, Git ignored. `.env`도 ignored.
- `scripts/check_git_safety.py`로 staged credential/raw data 검증 후 테스트 합격 시 main push.
- 작업별 commit SHA, 테스트 건수, push 결과는 `PROJECT_STATE.md`에 기록. 새 대화는 `START_HERE_NEXT_CHAT.md`·`AGENTS.md`·`PROJECT_STATE.md` 및 본 문서부터 읽고 이어서 개발.
