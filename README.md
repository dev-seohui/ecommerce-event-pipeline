# 이커머스 이벤트 파이프라인

> 플랫폼/데이터 엔지니어링 채용 과제  
> 웹 서비스 이벤트를 생성 → 저장 → 분석 → 시각화하는 소규모 데이터 파이프라인

---

## 과제 배경

웹 서비스에서 유저의 행동(클릭, 구매, 에러 등)을 이벤트 로그로 기록하고, 이를 분석해 서비스를 개선합니다.  
이 프로젝트는 **이커머스 도메인**을 기반으로 이벤트를 생성하고 → 저장하고 → 분석하고 → 시각화하는 파이프라인을 구현합니다.

---

## 프로젝트 구조

```
event-pipeline/
├── generator/
│   └── event_generator.py   # Step 1 & 2: 이벤트 생성 + PostgreSQL 저장
├── analysis/
│   └── queries.sql           # Step 3: 집계 분석 쿼리
├── visualization/
│   └── visualize.py          # Step 5: 차트 생성
├── output/                   # 생성된 차트 이미지 저장 경로
├── docker-compose.yml        # Step 4: 전체 스택 실행
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 실행 방법

```bash
# 전체 파이프라인 한 번에 실행
docker compose up --build
```

실행 순서:
1. PostgreSQL DB 컨테이너 기동 및 헬스체크
2. 이벤트 생성기 실행 → 1,000건 이벤트 생성 및 DB 저장
3. 시각화 실행 → `output/` 폴더에 차트 이미지 저장

---

## Step 1. 이벤트 설계

### 도메인: 이커머스 (온라인 쇼핑몰)

실제 이커머스 트래픽을 반영한 5가지 이벤트 타입을 설계했습니다.

| 이벤트 타입 | 설명 | 가중치 |
|------------|------|--------|
| `page_view` | 상품/카테고리 페이지 조회 | 40% |
| `click` | 상품 클릭 (상세 페이지 진입) | 25% |
| `search` | 검색어 입력 | 20% |
| `purchase` | 결제 완료 | 10% |
| `error` | 결제 실패, 재고 없음 등 에러 | 5% |

**설계 이유:**  
실제 이커머스 퍼널(`조회 → 검색 → 클릭 → 구매`)을 반영했습니다.  
가중치는 실무에서 관찰되는 트래픽 비율(페이지뷰가 압도적으로 많고, 구매는 소수)을 모사했습니다.  
에러 이벤트는 서비스 품질 모니터링 목적으로 포함했습니다.

---

## Step 2. 로그 저장

### 저장소: PostgreSQL

**선택 이유:**
- 이벤트 데이터는 구조가 명확(타입, 유저, 시각, 금액 등)하므로 스키마 정의가 유리한 관계형 DB가 적합
- 집계 분석(GROUP BY, 윈도우 함수 등)을 SQL로 직접 수행 가능
- Docker Compose로 앱과 함께 띄우기 쉬움

### 스키마

```sql
-- timestamp 기준 월별 Range Partition
CREATE TABLE events (
    id             BIGSERIAL,
    event_type     VARCHAR(50)   NOT NULL,
    user_id        VARCHAR(50)   NOT NULL,
    session_id     VARCHAR(100)  NOT NULL,
    timestamp      TIMESTAMP     NOT NULL,   -- 파티션 키
    page           VARCHAR(200),
    amount         NUMERIC(12,2),
    error_code     VARCHAR(50),
    product_id     VARCHAR(50),
    product_name   VARCHAR(200),
    search_keyword VARCHAR(200),
    referrer       VARCHAR(500),
    created_at     TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- 월별 파티션 예시 (기동 시 자동 생성)
CREATE TABLE events_2026_03 PARTITION OF events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE events_2026_04 PARTITION OF events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
-- ... 이하 동일
```

**파티션 설계 이유:**
- 이벤트 로그는 시계열 데이터 → `timestamp` 기준 Range Partition이 가장 자연스러움
- `WHERE timestamp BETWEEN ...` 쿼리 시 해당 파티션만 스캔 (Partition Pruning)
- 오래된 파티션을 `DROP TABLE events_2026_03` 한 줄로 빠르게 아카이브/삭제 가능
- 파티션별 인덱스 분리 → VACUUM 비용 분산, 운영 부담 감소

**인덱스:** 파티션별로 `event_type`, `user_id`, `timestamp` 인덱스 자동 생성

---

## Step 3. 데이터 집계 분석

`analysis/queries.sql` 에 6개 쿼리 포함:

1. **이벤트 타입별 발생 횟수** — 트래픽 구성 파악
2. **유저별 총 이벤트 수 / 구매액** — 헤비 유저 식별
3. **시간대별 이벤트 추이** — 트래픽 피크 타임 파악
4. **에러 코드 분포** — 장애 유형 모니터링
5. **상품별 클릭→구매 전환율** — 상품 성과 분석
6. **일별 매출 집계** — 매출 트렌드 파악

---

## Step 5. 결과 시각화

`docker compose up` 실행 후 `output/` 폴더에 5개 차트 이미지가 생성됩니다.

| 파일명 | 내용 |
|--------|------|
| `01_event_type_distribution.png` | 이벤트 타입별 발생 횟수 |
| `02_hourly_trend.png` | 시간대별 이벤트 추이 |
| `03_top_users.png` | 상위 10명 유저 활동 |
| `04_conversion_rate.png` | 상품별 클릭→구매 전환율 |
| `05_daily_revenue.png` | 일별 매출 |

---

## 기술 스택

| 항목 | 선택 |
|------|------|
| 언어 | Python 3.11 |
| DB | PostgreSQL 15 |
| 시각화 | matplotlib, pandas |
| 인프라 | Docker Compose |
