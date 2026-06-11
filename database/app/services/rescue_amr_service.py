import uuid
from app.models.database import db, RescueRobot, IncidentLog
from app.repositories.rescue_amr_repository import RescueAmrRepository

# 터틀봇4 관련 비즈니스 로직을 담당하는 Service 클래스
class RescueAMRService:
    @staticmethod
    def process_nav_success(
        robot_id: str, x: float, y: float, message: str):
        try:
            robot = RescueAmrRepository.get_robot_by_id(robot_id)
            if not robot:
                robot = RescueRobot(id=robot_id)

            robot.status = "SUCCESS"
            robot.pos_x = x
            robot.pos_y = y
            RescueAmrRepository.save_robot(robot) # 장바구니 담기 1

            new_log = IncidentLog(
                id=str(uuid.uuid4()),
                robot_id=robot_id,
                message=f"<span class='highlight'>{robot_id}</span> {message} (x:{x:.1f}, y:{y:.1f})",
            )
            RescueAmrRepository.create_log(new_log) # 장바구니 담기 2

            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def update_pose(
        robot_id: str, x: float, y: float, status: str = None, battery: int = None
    ):
        """로봇 위치·상태 upsert — 없으면 신규 생성, 있으면 갱신"""
        robot = RescueAmrRepository.get_robot_by_id(robot_id)
        if not robot:
            robot = RescueRobot(id=robot_id)

        robot.pos_x = x
        robot.pos_y = y
        if status:
            robot.status = status
        if battery is not None:
            robot.battery = battery  # 💡 [추가] 배터리 모델 적용

        RescueAmrRepository.save_robot(robot)
        db.session.commit()  

    @staticmethod
    def update_coverage(robot_id: str, coverage_ratio: float, mode: str = None):
        """탐색 진행률(0~1)·모드 갱신 — 100% 도달 시 SUCCESS로 전환 (CoverageStatus 기반)"""
        robot = RescueAmrRepository.get_robot_by_id(robot_id)
        if not robot:
            robot = RescueRobot(id=robot_id)

        robot.coverage_ratio = coverage_ratio
        if mode:
            robot.mode = mode
        robot.status = "SUCCESS" if coverage_ratio >= 1.0 else "MOVING"

        RescueAmrRepository.save_robot(robot)
        db.session.commit()
