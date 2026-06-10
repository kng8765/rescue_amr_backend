import psycopg2
import random

# 로컬 DB 연결 정보
DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "dbname": "rescue_amr_db",
    "user": "admin",
    "password": "rokey1234",
}


def seed_dummy_vector():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # DB에 있는 첫 번째 생존자 가져오기
    cur.execute("SELECT id, name FROM survivors LIMIT 1;")
    survivor = cur.fetchone()

    if not survivor:
        print("⚠️ 생존자 데이터가 없습니다. sync_survivors.py를 먼저 실행하세요.")
        return

    s_id, s_name = survivor

    # 1번 원소(index 0)가 높은 특징을 가진 256차원 벡터 생성
    dummy_vector = [
        round(random.uniform(0.85, 0.92), 4)
        if i == 0
        else round(random.uniform(0.08, 0.12), 4)
        for i in range(512)
    ]
    vector_str = f"[{','.join(map(str, dummy_vector))}]"

    # 해당 생존자에게 벡터 업데이트
    cur.execute(
        "UPDATE survivors SET face_vector = %s WHERE id = %s;", (vector_str, s_id)
    )
    conn.commit()

    print(f"✅ {s_name} 님(ID: {s_id})에게 테스트용 face_vector 주입 완료!")
    cur.close()
    conn.close()


if __name__ == "__main__":
    seed_dummy_vector()
