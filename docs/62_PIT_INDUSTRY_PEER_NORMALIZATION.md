# EraLeader 3_5 — PIT 시점 업종 내 동종기업 백분위 연구

> 2026-10-10. 기존 `offline-features`의 결정 시각 기준 산출물만 사용합니다. **공식 업종 종목군·기업행동·재무 원천 공증·미래 대장주 정확도는 미검증**입니다.

## 추가한 최소 기능

- `src/eraleader/peer_normalization.py`: 기존 `offline_research_v1` JSON을 받아 한국/미국을 분리하고 각 기업의 **당시 업종 ID** 내에서 매출·영업이익 YoY 백분위(0~100)를 계산합니다. 동점은 중간순위입니다. 평균은 두 요소의 단순 기술통계이며 투자점수나 실제 대장주 판정이 아닙니다.
- 스냅샷 상 기업 3개 미만 업종의 순위는 **평가 보류**합니다. 재무·산업 원천 자료의 `screen_evaluated=false`, 결측·오래된 450일 초과 값, 보고기간 불일치도 평균/분모에서 제외합니다. 누락 종목을 0점으로 처리하거나 현재 생존 종목으로 보충하지 않습니다.
- 시장/영구 기업 ID/업종/기간/시장 현지일 기반 최신 매출보고일과 나이의 일치/중복/미래날짜를 검사합니다. 과거의 실제 출처가 독립 인증된 것은 아니며 입력 소급 조작 위험은 남습니다.
- `audit-peer-normalization` CLI는 원본 JSON을 **변경하지 않고**, 명시된 새 파생 JSON 파일을 배타적으로 생성합니다(`open('x')`). 원본 바이트 SHA256 기록, 동일 경로/심볼릭 링크/덮어쓰기를 거부합니다. WATCH 상태 원장·랭킹 점수 최초 기록이나 기존 공식 점수에 자동 등록하지 않습니다.

## 로컬 실행

```bash
cd /Volumes/T5DATA/eraleader
PYTHONPATH=src python3 -m eraleader offline-features --market KR --as-of '2024-09-01T17:00:00+09:00' --out output/offline_demo
PYTHONPATH=src python3 -m eraleader audit-peer-normalization --input output/offline_demo/offline_kr_features.json --out output/offline_demo/peer_research.json --min-peers 3
PYTHONPATH=src python3 -m pytest tests/test_peer_normalization.py -q
PYTHONPATH=src python3 -m pytest tests -q
```

별도 `tests/test_peer_normalization.py`의 합성 다중 업종·동점·오래된 소스·미래 기간·신원 중복·시장 분리·입출력 해시·CLI 테스트로 판정 논리를 검증합니다. 재현 테스트 수와 Git SHA는 `PROJECT_STATE.md` 하단 실제 실행 기록을 우선합니다.

## 남은 한계

동일 업종 여부/상장폐지/회계연도/공시 이용시각/업종 peer population은 **입력 PIT 스냅샷의 자기선언**만 검사합니다. 현 자료가 검증된 실제 미국/한국 역사적 동일 업종 종목 전체를 포함한다고 주장하지 않습니다. 산업 내 진짜 표준화에는 공식 당시 업종 이력과 기업별 보고일·회계정책이 추가로 필요합니다. 실제 미래 적중률 및 전향적 라벨 추적은 별도로 검증해야 합니다. 외부 API는 1~6단계 로컬 개발 후, 물리적 SSD 재연결·재부팅은 사용자 D-021에 따라 마지막 단계로 보류합니다.
