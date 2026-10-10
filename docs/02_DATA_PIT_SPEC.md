# 데이터 및 Point-in-Time(PIT) 규격

## 데이터 소스
- 한국 가격·거래량·종목목록: KRX OPEN API 등 허용된 공식/상업 데이터
- 한국 재무·공시: OpenDART (공시 접수·정정 이력·분기/연간)
- 미국 공시·재무: SEC EDGAR(companyfacts 등), SEC 공시 접수 시각
- 미국 시세·상장폐지·기업행동: 별도 적합한 시세 공급자 필요
- 미래 EPS 컨센서스: 과거 스냅샷 공급자 있을 때만. 없으면 N/A, 대체 신호로 처리.

## 최소 테이블
```text
security_master(security_id, market, venue, ticker, isin_or_cik, name,
                effective_from, effective_to, security_type, listing_status)
price_bar(security_id, session_date, open, high, low, close, volume,
          currency, provider, ingest_at, adjustment_policy, version)
corporate_action(security_id, effective_date, known_at, action_type, ratio, cash)
filing(security_id, period_end, filed_at, accepted_at, first_available_at,
       filing_id, amended_from, report_type, source)
fundamental(security_id, metric, value, unit, period_start, period_end,
            available_at, filing_id, revision_id)
estimate(security_id, metric, horizon, value, snapshot_at, vendor, coverage)
industry_membership(security_id, industry_code, effective_from, effective_to)
feature_snapshot(security_id, as_of, feature_version, input_data_cutoff, features_json)
candidate_snapshot(security_id, as_of, state, score, reasons_json,
                   data_quality_json, model_version)
candidate_event(event_id, security_id, as_of, old_state, new_state, reasons_json)
run_manifest(run_id, as_of, input_hashes, code_sha, config_hash, created_at)
```

## PIT 불변 조건
- t시점 분석에는 `available_at <= decision_timestamp(t)`인 데이터만 사용.
- 재무값은 period_end가 아니라 filed_at/accepted_at·실제 공급 지연을 고려한 first_available_at 기준.
- t일 종가가 필요한 전략은 t일 종료 후 결정, 주문 전략을 만든다면 다음 거래가능 시점부터 체결.
- 과거 이력 수정(정정공시)은 원본 버전을 덮어쓰지 않는다.
- 산업 분류, 편입종목, 상장/상폐, 액면분할·배당/권리정보를 시점별로 재현.
- 주가 수익률 계산용 adjusted series와 실제 체결가 series를 혼동하지 않는다.
- 상장폐지·거래정지·미체결·유동성 부족은 평가에 반영.
- KR/US 거래일/시간대와 각 거래소 현지 캘린더 사용.

## 품질 게이트
중복 PK, 누락 거래일, 비정상 급등락, 가격<=0, 거래량<0, 공시시점 역전, 단위/통화 불일치, 상장 전 가격, 스플릿 충돌, 조인 실패, 최신 데이터 지연을 탐지. 오류는 유형·영향 종목수·미검증구간·조치방법을 구조화한 JSON으로 반환.

## 결측 처리
없는 예측 EPS를 0 또는 가상 수치로 채우지 않는다. 평가 가능한 가중치를 재정규화하는 실험과 점수 보류 방식을 둘 다 테스트. 필수 필드 누락 시 후보를 '평가보류'로 기록하고 사용자 화면에 근거를 노출.

## 수집 정책
증분 수집, 원본 응답 로컬 캐시, rate limit/재시도(backoff), 마지막 성공 watermark, 요청 ID, 실패 보고. 라이선스·재배포 제한 준수. 자격증명은 코드·Git·결과 로그에 남기지 않는다.
