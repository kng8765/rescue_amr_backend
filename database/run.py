from app.main import app
from app.models.database import db
from app.core import config

if __name__ == "__main__":
    with app.app_context():
        print(
            "🧱 [ARES 백엔드] PostgreSQL 데이터베이스 테이블 무결성 검증 및 생성 중..."
        )
        db.create_all()
        print("✅ [ARES 백엔드] 데이터베이스 테이블 생성 및 연동 완료!")

    app.run(host=config.SERVER_HOST, port=config.SERVER_PORT, debug=True)
