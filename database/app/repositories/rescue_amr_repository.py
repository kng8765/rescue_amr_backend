from sqlalchemy.orm import Session
from app.models.database import db, RescueRobot, IncidentLog

# 터틀봇4 관련 데이터베이스 작업(Querry, Update, Delete)을 담당하는 Repository 클래스
class RescueAmrRepository:
    @staticmethod
    def get_robot_by_id(robot_id: str):
        return RescueRobot.query.filter_by(id=robot_id).first()

    @staticmethod
    def save_robot(robot: RescueRobot):
        db.session.add(robot)

    @staticmethod
    def create_log(log: IncidentLog):
        db.session.add(log)

    @staticmethod
    def get_recent_logs(limit: int = 10):
        return IncidentLog.query.order_by(IncidentLog.timestamp.desc()).limit(limit).all()
