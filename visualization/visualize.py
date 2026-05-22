import os
import psycopg2
import pandas as pd
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.ticker as mticker

# DB 연결
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "eventdb"),
    "user": os.getenv("DB_USER", "eventuser"),
    "password": os.getenv("DB_PASSWORD", "eventpass"),
}

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/app/output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 한글 폰트 설정
try:
    font_path = fm.findfont(fm.FontProperties(family="NanumGothic"))
    plt.rcParams["font.family"] = "NanumGothic"
except Exception:
    plt.rcParams["font.family"] = "DejaVu Sans"

plt.rcParams["axes.unicode_minus"] = False


def get_conn():
    return psycopg2.connect(**DB_CONFIG)

"""차트 1: 이벤트 타입별 발생 횟수 (가로 막대)"""
def plot_event_type_distribution(conn):
    df = pd.read_sql("""
        SELECT event_type, COUNT(*) AS cnt
        FROM events
        GROUP BY event_type
        ORDER BY cnt DESC
    """, conn)

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#937860"]
    bars = ax.barh(df["event_type"], df["cnt"], color=colors[:len(df)])
    ax.bar_label(bars, fmt="%d", padding=4)
    ax.set_xlabel("Event Count")
    ax.set_title("Event Type Distribution")
    ax.invert_yaxis()
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "01_event_type_distribution.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"■ 저장: {path}")

"""차트 2: 시간대별 이벤트 추이 (꺾은선)"""
def plot_hourly_trend(conn):
    df = pd.read_sql("""
        SELECT
            DATE_TRUNC('hour', timestamp) AS hour_bucket,
            COUNT(*) AS event_count,
            COUNT(DISTINCT user_id) AS unique_users
        FROM events
        GROUP BY hour_bucket
        ORDER BY hour_bucket
    """, conn)

    fig, ax1 = plt.subplots(figsize=(12, 4))
    ax2 = ax1.twinx()

    ax1.plot(df["hour_bucket"], df["event_count"], color="#4C72B0", label="Events", linewidth=1.5)
    ax2.plot(df["hour_bucket"], df["unique_users"], color="#C44E52", linestyle="--", label="Unique Users", linewidth=1.2)

    ax1.set_xlabel("Time")
    ax1.set_ylabel("Event Count", color="#4C72B0")
    ax2.set_ylabel("Unique Users", color="#C44E52")
    ax1.set_title("Hourly Event Trend")
    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.88))
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "02_hourly_trend.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"■ 저장: {path}")

"""차트 3: 상위 10명 유저별 이벤트 수 + 구매액"""
def plot_top_users(conn):
    df = pd.read_sql("""
        SELECT
            user_id,
            COUNT(*) AS total_events,
            COALESCE(SUM(amount) FILTER (WHERE event_type = 'purchase'), 0) AS total_amount
        FROM events
        GROUP BY user_id
        ORDER BY total_events DESC
        LIMIT 10
    """, conn)

    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax2 = ax1.twinx()

    x = range(len(df))
    bars = ax1.bar(x, df["total_events"], color="#4C72B0", alpha=0.7, label="Total Events")
    ax2.plot(x, df["total_amount"], color="#C44E52", marker="o", label="Total Amount (₩)", linewidth=1.5)

    ax1.set_xticks(x)
    ax1.set_xticklabels(df["user_id"], rotation=30, ha="right", fontsize=8)
    ax1.set_ylabel("Total Events")
    ax2.set_ylabel("Total Amount (₩)")
    ax1.set_title("Top 10 Users by Event Count")
    fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.88))
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "03_top_users.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"■ 저장: {path}")

"""차트 4: 상품별 클릭 → 구매 전환율"""
def plot_conversion_rate(conn):
    df = pd.read_sql("""
        SELECT
            p.product_name,
            p.click_count,
            COALESCE(b.purchase_count, 0) AS purchase_count,
            ROUND(COALESCE(b.purchase_count, 0) * 100.0 / NULLIF(p.click_count, 0), 2) AS cvr
        FROM (
            SELECT product_name, COUNT(*) AS click_count
            FROM events WHERE event_type = 'click' AND product_name IS NOT NULL
            GROUP BY product_name
        ) p
        LEFT JOIN (
            SELECT product_name, COUNT(*) AS purchase_count
            FROM events WHERE event_type = 'purchase' AND product_name IS NOT NULL
            GROUP BY product_name
        ) b ON p.product_name = b.product_name
        ORDER BY cvr DESC
    """, conn)

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(df["product_name"], df["cvr"], color="#55A868")
    ax.bar_label(bars, fmt="%.1f%%", padding=4)
    ax.set_xlabel("Conversion Rate (%)")
    ax.set_title("Click → Purchase Conversion Rate by Product")
    ax.invert_yaxis()
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "04_conversion_rate.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"■ 저장: {path}")

"""차트 5: 일별 매출"""
def plot_daily_revenue(conn):
    df = pd.read_sql("""
        SELECT
            DATE_TRUNC('day', timestamp)::DATE AS sale_date,
            SUM(amount) AS daily_revenue,
            COUNT(*) AS purchase_count
        FROM events
        WHERE event_type = 'purchase'
        GROUP BY sale_date
        ORDER BY sale_date
    """, conn)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(df["sale_date"], df["daily_revenue"], alpha=0.4, color="#4C72B0")
    ax.plot(df["sale_date"], df["daily_revenue"], color="#4C72B0", marker="o", linewidth=1.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₩{x:,.0f}"))
    ax.set_xlabel("Date")
    ax.set_ylabel("Revenue (₩)")
    ax.set_title("Daily Revenue")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "05_daily_revenue.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"■ 저장: {path}")

"""차트 6: Retention"""
def plot_retention(conn):
    df = pd.read_sql("""
        SELECT
            user_id,
            COUNT(DISTINCT session_id) AS session_count
        FROM events
        GROUP BY user_id
        ORDER BY session_count DESC
        LIMIT 20
    """, conn)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(df["user_id"], df["session_count"], color="#4C72B0")
    ax.set_xticks(range(len(df)))
    ax.set_xticklabels(df["user_id"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Session Count")
    ax.set_title("Top 20 Users by Session Count (Retention)")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "06_retention.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"■ 저장: {path}")


def main():
    print("■ 시각화 시작...")
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        plot_event_type_distribution(conn)
        plot_hourly_trend(conn)
        plot_top_users(conn)
        plot_conversion_rate(conn)
        plot_daily_revenue(conn)
        plot_retention(conn) 
    finally:
        conn.close()
    print(f"\n■ 모든 차트 저장 완료 → {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
