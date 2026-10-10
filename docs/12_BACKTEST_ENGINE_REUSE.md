# 외부 범용 백테스트 엔진 재사용 검토

## 확인된 탐색 대상 (코드·API 실제 검토 전)
- /Volumes/T5DATA/CycleOS-Lab_BacktestEngine
- /Volumes/T5DATA/backtestengine

이 프로젝트들은 EraLeader와 **독립**이다. 다른 프로젝트의 파일을 덮어쓰거나 외부 코드에 직접 import 의존하지 않는다.

## 호환성 체크리스트
1. 배포/패키지/실행 진입점과 라이선스
2. PIT 데이터 계약 및 universe history 지원
3. 종목의 상장/상폐 이력과 기업행동 처리
4. 가격·조정계열·실제 체결가 구분
5. 한국/미국 시각/캘린더 지원
6. 실제 거래 수수료, 슬리피지, 미체결, 유동성, 생존편향
7. 입력 signal stream / target positions 호환성
8. 백테스트 결과 재현 가능성, 명령형 실행, 자동 테스트
9. read-only 데이터 공유 또는 별도 캐시 가능
10. 결과 요약/오류 보고의 작은 JSON 출력 가능

## 연동 정책
가능하면 `EraLeaderBacktestAdapter`를 만들고 엔진별 구현체만 교체. 선택되지 않은 엔진을 재설치/재구현하지 않는다. 엔진에 부족한 PIT 처리 로직을 EraLeader 데이터 계층에서 보완하되, 검증 전엔 '완성' 아님.

## 최소 어댑터 계약
입력: `as_of, ranked_candidates, candidate_state, universe_snapshot_id, price_source_id, assumptions, strategy_version`.
출력: `run_id, status, coverage, hit_rate, lead_time, excess_return, cagr, mdd, turnover, cost_assumptions, validation_flags, artifact_paths`.

## 첫 점검 작업
파일 목록과 README·테스트 구성·핵심 API만 읽기 → 테스트 명령 확인 → 읽기 전용 샘플 실행 → 호환/부분호환/불가 판정 기록. 리포트에는 확실한 증거만 쓴다.

## 2026-10-10 실제 SSD 점검 결과 갱신

**참고:** 이전 상단의 '코드·API 실제 검토 전'은 작성 당시 상태. 이후 사용자 요청으로 소스와 일부 데이터를 읽기 전용 점검했으며, 상세 증거는 [23_BACKTESTENGINE_LOCAL_REUSE.md](23_BACKTESTENGINE_LOCAL_REUSE.md)에 기록.
- \`backtestengine\` 빈 폴더 / \`CycleOS-Lab_BacktestEngine\`에 1995~2026 marcap 일별 가격, 미국 주·월봉, 모멘텀 베이스라인이 실제 존재.
- 32개 국내 marcap parquet 합계 **15,648,407행**과 기존 검증 요약 일치. 현재 PIT/배당·분할 보정·상장폐지 완전성은 미검증.
- 기존 \`grid_mom_rotation.py\` 모멘텀 업종 전략을 로컬 캐시로 **1회 실행 PASS**. 이것은 코드 재사용의 간단한 증거이며 EraLeader 전략 검증이 아님.
- **실행 원칙:** 복사·재다운로드 전 read-only 파일 어댑터, 새 PIT 확인 로직, legacy poller/GCS 직접 호출 금지.
