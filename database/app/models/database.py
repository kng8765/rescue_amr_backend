from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from app.core import config
from pgvector.sqlalchemy import Vector

db = SQLAlchemy()


def init_db(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(db.text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        db.create_all()


# ==========================================
# 2. 데이터베이스 스키마 정의 (테이블 구조)
# ==========================================
class RescueRobot(db.Model):
    __tablename__ = "rescue_robots"
    id = db.Column(db.String, primary_key=True, index=True)
    status = db.Column(db.String, default="IDLE")  # IDLE, MOVING, SUCCESS, ERROR
    battery = db.Column(db.Integer, nullable=True)
    pos_x = db.Column(db.Float, nullable=True)
    pos_y = db.Column(db.Float, nullable=True)


class IncidentLog(db.Model):
    __tablename__ = "incident_logs"
    id = db.Column(db.String, primary_key=True, index=True)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    robot_id = db.Column(db.String, nullable=True)
    message = db.Column(db.String, nullable=False)

# 구조대상자 신상정보 테이블
class Survivor(db.Model):
    __tablename__ = "survivors"

    # 실제 소방 규격이나 주민등록번호 확장을 고려해 String(Varchar)으로 셋팅
    id = db.Column(db.String(50), primary_key=True, index=True)
    name = db.Column(db.String(50), nullable=False)
    sex = db.Column(db.String(10), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)

    # YOLO/FaceNet 등에서 추출한 256차원 얼굴 임베딩 벡터 저장 공간
    face_vector = db.Column(Vector(256), nullable=True)


# 고도화된 실시간 구조 로그 테이블
class SurvivorLog(db.Model):
    __tablename__ = "survivor_logs"

    log_number = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # survivors 테이블의 id와 연동 (외래키 설정으로 데이터 무결성 확보)
    id = db.Column(db.String(50), db.ForeignKey("survivors.id"), nullable=True)

    detected_x = db.Column(db.Float, nullable=False)
    detected_y = db.Column(db.Float, nullable=False)
    similarity = db.Column(db.Float, nullable=True)  # 얼굴 일치도 (0.0 ~ 1.0)
    robot_id = db.Column(db.String(50), default="robot1")
    img_path = db.Column(db.String(255), nullable=True)  # 현장 증거 사진 로컬/서버 경로
    detection_time = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    
# 로그인 ID, 비밀번호 테이블
class LoginUser(db.Model):
    __tablename__ = "login_data"
    username      = db.Column(db.String(20), primary_key=True) # ID
    password_hash = db.Column(db.String(255), nullable=False)  # Hash코드로 변경된 비밀번호
