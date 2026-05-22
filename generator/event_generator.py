import random
import uuid
import time
import os
import json
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import execute_batch

# DB 연결 설정
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "eventdb"),
    "user": os.getenv("DB_USER", "eventuser"),
    "password": os.getenv("DB_PASSWORD", "eventpass"),
}

# 이커머스 도메인 데이터
PAGES = [
    "/", "/products", "/products/shoes", "/products/bags",
    "/products/clothes", "/cart", "/checkout", "/mypage", "/search"
]

PRODUCTS = [
    {"id": "P001", "name": "Nike Air Max", "price": 129000},
    {"id": "P002", "name": "Adidas Stan Smith", "price": 89000},
    {"id": "P003", "name": "Leather Tote Bag", "price": 75000},
    {"id": "P004", "name": "Denim Jacket", "price": 119000},
    {"id": "P005", "name": "Running Shorts", "price": 39000},
]

SEARCH_KEYWORDS = [
    "운동화", "가방", "자켓", "여름 원피스", "슬랙스",
    "nike", "adidas", "신상", "세일", "무료배송"
]

ERROR_CODES = ["OUT_OF_STOCK", "PAYMENT_FAILED", "SESSION_EXPIRED", "INVALID_COUPON", "NETWORK_ERROR"]

USER_IDS = [f"user_{str(i).zfill(4)}" for i in range(1, 51)]  # user_0001 ~ user_0050


def generate_session_id():
    return str(uuid.uuid4())


def generate_page_view(user_id, session_id, ts):
    page = random.choice(PAGES)
    referrer = random.choice([None, "https://google.com", "https://naver.com", "direct"])
    # ── Step 1: 앱/서버가 이벤트를 JSON으로 직렬화 ──
    return json.dumps({
        "event_type": "page_view",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": ts.isoformat(),
        "page": page,
        "referrer": referrer,
    })

def generate_search(user_id, session_id, ts):
    keyword = random.choice(SEARCH_KEYWORDS)
    return json.dumps({
        "event_type": "search",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": ts.isoformat(),
        "page": "/search",
        "search_keyword": keyword,
    })

def generate_click(user_id, session_id, ts):
    product = random.choice(PRODUCTS)
    return json.dumps({
        "event_type": "click",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": ts.isoformat(),
        "page": f"/products/{product['id'].lower()}",
        "product_id": product["id"],
        "product_name": product["name"],
    })

def generate_purchase(user_id, session_id, ts):
    product = random.choice(PRODUCTS)
    quantity = random.randint(1, 3)
    return json.dumps({
        "event_type": "purchase",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": ts.isoformat(),
        "page": "/checkout",
        "product_id": product["id"],
        "product_name": product["name"],
        "amount": product["price"] * quantity,
    })

def generate_error(user_id, session_id, ts):
    return json.dumps({
        "event_type": "error",
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": ts.isoformat(),
        "page": random.choice(["/checkout", "/cart", "/products"]),
        "error_code": random.choice(ERROR_CODES),
    })

def parse_event(raw_json: str) -> dict:
    e = json.loads(raw_json)
    return {
        "event_type":     e["event_type"],
        "user_id":        e["user_id"],
        "session_id":     e["session_id"],
        "timestamp":      e["timestamp"],
        "page":           e.get("page"),
        "amount":         e.get("amount"),           # purchase만 존재
        "error_code":     e.get("error_code"),       # error만 존재
        "product_id":     e.get("product_id"),       # click / purchase만 존재
        "product_name":   e.get("product_name"),     # click / purchase만 존재
        "search_keyword": e.get("search_keyword"),   # search만 존재
        "referrer":       e.get("referrer"),         # page_view만 존재
    }

# 이벤트 타입별 가중치 (실제 이커머스 트래픽 비율 반영)
EVENT_GENERATORS = [
    (generate_page_view, 40),
    (generate_search, 20),
    (generate_click, 25),
    (generate_purchase, 10),
    (generate_error, 5),
]

GENERATORS, WEIGHTS = zip(*EVENT_GENERATORS)
DAYS_RANGE = int(os.getenv("DAYS_RANGE", "90"))  # 시뮬레이션 기간 (일)


def generate_events(n_sessions=1000):
    raw_jsons = []
    now = datetime.now()

    for _ in range(n_sessions):
        user_id = random.choice(USER_IDS)
        session_id = generate_session_id()  # 세션 하나
        
        # 세션 시작 시각
        session_start = now - timedelta(
            days=random.uniform(0, DAYS_RANGE),
            hours=random.uniform(0, 23),
            minutes=random.uniform(0, 59),
        )
        
        # 이 세션에서 몇 개 이벤트 발생할지
        n_events = random.randint(1, 5)
        
        for i in range(n_events):
            # 이벤트는 세션 시작 후 순서대로 발생 (1분씩 간격)
            ts = session_start + timedelta(minutes=i * random.randint(1, 3))
            generator = random.choices(GENERATORS, weights=WEIGHTS, k=1)[0]
            raw_jsons.append(generator(user_id, session_id, ts))

    parsed = [parse_event(raw) for raw in raw_jsons]
    return parsed


def _partition_name(year: int, month: int) -> str:
    return f"events_{year}_{month:02d}"

def create_table(conn):
    now = datetime.now()
    with conn.cursor() as cur:
        # 부모 테이블 (파티션 테이블)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id             BIGSERIAL,
                event_type     VARCHAR(50)   NOT NULL,
                user_id        VARCHAR(50)   NOT NULL,
                session_id     VARCHAR(100)  NOT NULL,
                timestamp      TIMESTAMP     NOT NULL,
                page           VARCHAR(200),
                amount         NUMERIC(12, 2),
                error_code     VARCHAR(50),
                product_id     VARCHAR(50),
                product_name   VARCHAR(200),
                search_keyword VARCHAR(200),
                referrer       VARCHAR(500),
                created_at     TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (id, timestamp)   
            ) PARTITION BY RANGE (timestamp);
        """)

        # 과거 DAYS_RANGE일 ~ 다음 달까지 월별 파티션 자동 생성
        months_needed = set()
        for delta in range(DAYS_RANGE + 32):  # 약간 여유 있게
            d = now - timedelta(days=delta)
            months_needed.add((d.year, d.month))
        # 다음 달 파티션도 미리 생성 (신규 이벤트 대비)
        next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        months_needed.add((next_month.year, next_month.month))

        for year, month in sorted(months_needed):
            pname = _partition_name(year, month)
            start = f"{year}-{month:02d}-01"
            # 다음 달 1일
            if month == 12:
                end = f"{year+1}-01-01"
            else:
                end = f"{year}-{month+1:02d}-01"

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {pname}
                    PARTITION OF events
                    FOR VALUES FROM ('{start}') TO ('{end}');
            """)

            # 파티션별 인덱스 (Partition Pruning 극대화)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{pname}_type
                    ON {pname}(event_type);
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{pname}_user
                    ON {pname}(user_id);
            """)
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{pname}_ts
                    ON {pname}(timestamp);
            """)

    conn.commit()
    print(f"■ 파티션 테이블 생성 완료 ({len(months_needed)}개 월별 파티션)")


def insert_events(conn, events):
    sql = """
        INSERT INTO events
            (event_type, user_id, session_id, timestamp, page,
             amount, error_code, product_id, product_name, search_keyword, referrer)
        VALUES
            (%(event_type)s, %(user_id)s, %(session_id)s, %(timestamp)s, %(page)s,
             %(amount)s, %(error_code)s, %(product_id)s, %(product_name)s,
             %(search_keyword)s, %(referrer)s)
    """
    with conn.cursor() as cur:
        execute_batch(cur, sql, events, page_size=1000)  # 10만건 대비 배치 사이즈 증가
    conn.commit()
    print(f"■ {len(events)}건 이벤트 저장 완료")


def wait_for_db(max_retries=10, delay=3):
    """Docker 환경에서 DB 준비될 때까지 대기"""
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            print("■ DB 연결 성공")
            return conn
        except psycopg2.OperationalError as e:
            print(f"■ DB 대기 중... ({i+1}/{max_retries}): {e}")
            time.sleep(delay)
    raise Exception("■ DB 연결 실패")


def main():
    n_sessions = int(os.getenv("SESSION_COUNT", "10000"))
    print(f"■ 이커머스 이벤트 파이프라인 시작 (세션 수: {n_sessions})")

    conn = wait_for_db()
    try:
        create_table(conn)
        events = generate_events(n_sessions)
        insert_events(conn, events)

        # 간단한 통계 출력
        from collections import Counter
        counts = Counter(e["event_type"] for e in events)
        print("\n■ 생성된 이벤트 분포:")
        for etype, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"   {etype:<15} {cnt:>5}건  ({cnt/len(events)*100:.1f}%)")
    finally:
        conn.close()

    print("\n■ 완료")


if __name__ == "__main__":
    main()
