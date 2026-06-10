from app.models.database import db, Survivor, SurvivorLog


class SurvivorRepository:
    @staticmethod
    def create_survivor_log(log_obj: SurvivorLog):
        """생존자 실시간 위치/매칭 로그 저장"""
        db.session.add(log_obj)

    @staticmethod
    def get_survivor_by_id(survivor_id: str):
        """부모 테이블에서 생존자 정보 조회"""
        return Survivor.query.filter_by(id=survivor_id).first()

    @staticmethod
    def match_survivor_by_vector(vector_str: str):
        """pgvector 기반 코사인 유사도 매칭 쿼리 실행"""
        query_text = db.text("""
            SELECT id, name, birth_year, sex, phone_number,
                   (1 - (face_vector <=> CAST(:vec AS vector))) * 100 AS similarity
            FROM survivors
            WHERE face_vector IS NOT NULL
            ORDER BY face_vector <=> CAST(:vec AS vector)
            LIMIT 1;
        """)
        return db.session.execute(query_text, {"vec": vector_str}).fetchone()
