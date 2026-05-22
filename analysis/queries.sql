
-- 이벤트 타입별 발생 횟수
-- 어떤 행동이 가장 많이 일어나는지 파악
SELECT
    event_type,
    COUNT(*)                                      AS event_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS ratio_pct
FROM events
GROUP BY event_type
ORDER BY event_count DESC;


-- 유저별 총 이벤트 수 (상위 20명)
-- 가장 활동적인 유저 파악
SELECT
    user_id,
    COUNT(*)                                   AS total_events,
    COUNT(DISTINCT session_id)                 AS session_count,
    COUNT(*) FILTER (WHERE event_type = 'purchase') AS purchase_count,
    COALESCE(SUM(amount) FILTER (WHERE event_type = 'purchase'), 0) AS total_amount
FROM events
GROUP BY user_id
ORDER BY total_events DESC
LIMIT 20;


-- 시간대별 이벤트 추이 (시간 단위)
-- 트래픽이 몰리는 시간대 파악
SELECT
    DATE_TRUNC('hour', timestamp) AS hour_bucket,
    COUNT(*)                      AS event_count,
    COUNT(DISTINCT user_id)       AS unique_users
FROM events
GROUP BY hour_bucket
ORDER BY hour_bucket;


-- 에러 이벤트 비율 및 에러 코드 분포
-- 장애/이슈 모니터링
SELECT
    error_code,
    COUNT(*)                                          AS error_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS ratio_pct
FROM events
WHERE event_type = 'error'
GROUP BY error_code
ORDER BY error_count DESC;


-- 상품별 클릭 → 구매 전환율
-- 어떤 상품이 실제 구매로 이어지는지 분석
SELECT
    p.product_name,
    p.click_count,
    COALESCE(b.purchase_count, 0)                          AS purchase_count,
    COALESCE(b.total_revenue, 0)                           AS total_revenue,
    ROUND(COALESCE(b.purchase_count, 0) * 100.0
          / NULLIF(p.click_count, 0), 2)                   AS conversion_rate_pct
FROM (
    SELECT product_name, COUNT(*) AS click_count
    FROM events
    WHERE event_type = 'click' AND product_name IS NOT NULL
    GROUP BY product_name
) p
LEFT JOIN (
    SELECT product_name, COUNT(*) AS purchase_count, SUM(amount) AS total_revenue
    FROM events
    WHERE event_type = 'purchase' AND product_name IS NOT NULL
    GROUP BY product_name
) b ON p.product_name = b.product_name
ORDER BY conversion_rate_pct DESC;


-- 일별 매출 집계
-- 날짜별 구매 건수 및 매출
SELECT
    DATE_TRUNC('day', timestamp)::DATE AS sale_date,
    COUNT(*)                            AS purchase_count,
    SUM(amount)                         AS daily_revenue,
    ROUND(AVG(amount), 0)               AS avg_order_value
FROM events
WHERE event_type = 'purchase'
GROUP BY sale_date
ORDER BY sale_date;

-- 유저 재방문 (Retention) 분석
-- 같은 유저가 며칠에 걸쳐 방문했는지 파악
SELECT
    user_id,
    COUNT(DISTINCT DATE(timestamp)) AS active_days,
    MIN(DATE(timestamp))            AS first_visit,
    MAX(DATE(timestamp))            AS last_visit,
    MAX(DATE(timestamp)) - MIN(DATE(timestamp)) AS days_since_first_visit
FROM events
GROUP BY user_id
HAVING COUNT(DISTINCT DATE(timestamp)) > 1
ORDER BY active_days DESC;