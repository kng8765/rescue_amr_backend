"""
Supabase survivors 테이블 → 로컬 survivors 테이블 동기화 스크립트
실행: python sync_survivors.py
"""

import os
from dotenv import load_dotenv
from supabase import create_client
from app.core import config
import psycopg2

current_dir = os.path.dirname(__file__)
env_path = os.path.join(current_dir, "../admin_dashboard/.env")

# .env 로드
load_dotenv(dotenv_path=env_path)

# ── Supabase 설정 ──────────────────────────────
SUPABASE_URL = config.SUPABASE_URL
SUPABASE_KEY = config.SUPABASE_KEY

# ── 로컬 PostgreSQL 설정 ───────────────────────
LOCAL_DB = {
    "host": config.DB_HOST,
    "port": config.DB_PORT,
    "dbname": config.DB_NAME,
    "user": config.DB_USER,
    "password": config.DB_PASSWORD,
}

def fetch_from_supabase():
    """Supabase survivors 테이블에서 인적정보 조회 (face 제외)"""
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    res = client.table("survivors").select("id, name, sex, phone_number").execute()
    return res.data


def insert_to_local(rows):
    """로컬 survivors 테이블에 INSERT (중복 id는 UPDATE)"""
    conn = psycopg2.connect(**LOCAL_DB)
    cur = conn.cursor()

    for row in rows:
        cur.execute("""
            INSERT INTO survivors (id, name, sex, phone_number)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name         = EXCLUDED.name,
                sex          = EXCLUDED.sex,
                phone_number = EXCLUDED.phone_number
        """, (row["id"], row["name"], row["sex"], row["phone_number"]))

    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ {len(rows)}명 동기화 완료")


if __name__ == "__main__":
    print("📡 Supabase에서 인적정보 가져오는 중...")
    rows = fetch_from_supabase()
    print(f"   {len(rows)}명 조회됨")

    print("💾 로컬 DB에 저장 중...")
    insert_to_local(rows)
