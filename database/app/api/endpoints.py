from flask import Blueprint, request, jsonify
from app.services.rescue_amr_service import RescueAMRService
from app.services.survivor_service import SurvivorService
from app.repositories.rescue_amr_repository import RescueAmrRepository
from app.models.database import RescueRobot
import uuid
from app.models.database import IncidentLog, Survivor, SurvivorLog, db

api_bp = Blueprint("api", __name__)


@api_bp.route("/robots/<robot_id>/pose", methods=["POST"])
def update_robot_pose(robot_id):
    """로봇 위치·상태 주기 업데이트 — bt_db_bridge에서 1초마다 호출"""
    data = request.get_json()
    RescueAMRService.update_pose(
        robot_id=robot_id,
        x=data.get("x", 0.0),
        y=data.get("y", 0.0),
        status=data.get("status"),
    )
    return jsonify({"ok": True}), 200


@api_bp.route("/robots/<robot_id>/exploration", methods=["POST"])
def update_robot_exploration(robot_id):
    """탐사 면적 업데이트 — bt_db_bridge에서 /map 분석 후 호출"""
    data = request.get_json()
    RescueAMRService.update_exploration(
        robot_id=robot_id,
        explored_area=data.get("explored_area", 0.0),
        total_area=data.get("total_area", 1.0),
    )
    return jsonify({"ok": True}), 200


@api_bp.route("/robots/<robot_id>/nav_success", methods=["POST"])
def handle_nav_success(robot_id):
    data = request.get_json()
    RescueAMRService.process_nav_success(
        robot_id, data["x"], data["y"], data["message"]
    )
    return jsonify({"status": "ok"}), 200


@api_bp.route("/logs", methods=["GET"])
def get_logs():
    logs = RescueAmrRepository.get_recent_logs(limit=10)
    return jsonify(
        [
            {"time": log.timestamp.strftime("%H:%M:%S"), "msg": log.message}
            for log in logs
        ]
    ), 200


@api_bp.route("/logs", methods=["POST"])
def add_yolo_log():
    data = request.get_json()
    new_log = IncidentLog(
        id=str(uuid.uuid4()),
        robot_id=data.get("robot_id", "ARES-VISION"),
        message=data.get("message", ""),
    )
    RescueAmrRepository.create_log(new_log)
    return jsonify({"status": "ok"}), 200


@api_bp.route("/survivor-logs", methods=["POST"])
def add_survivor_log():
    data = request.get_json()
    try:
        res_body, status_code = SurvivorService.process_survivor_log(data)
        return jsonify(res_body), status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@api_bp.route("/survivors/identify", methods=["POST"])
def identify_survivor():
    data = request.get_json()
    input_vector = data.get("vector")

    try:
        res_body, status_code = SurvivorService.identify_survivor_by_vector(
            input_vector
        )
        # 성공/실패 여부와 상관없이 비즈니스 결과 규격에 맞추어 리턴
        return jsonify({"status": "success", **res_body}), status_code
    except Exception as e:
        print(f"❌ [백엔드 오퍼레이션] SQLAlchemy 내부 연산 실패 상세 원인: {str(e)}")
        return jsonify({"status": "success", "matched": False, "message": str(e)}), 200


@api_bp.route("/survivors", methods=["GET"])
def get_survivors():
    """survivors 테이블 전체 조회 — face URL 포함, WorkerPage용"""
    from app.models.database import Survivor
    survivors = Survivor.query.all()
    return jsonify([
        {
            "id": s.id,
            "name": s.name,
            "sex": s.sex,
            "phone_number": s.phone_number,
            "face": s.face,          # Supabase Storage URL (없으면 null)
        }
        for s in survivors
    ]), 200


@api_bp.route("/robots", methods=["GET"])
def get_robots():
    """rescue_robots 테이블 전체 조회 — 맵 위치 및 상태 실시간 제공

    db_status 값:
      ok    — 로봇 데이터 정상 존재
      empty — DB 연결은 됐지만 등록된 로봇 없음 (bt_db_bridge 미실행 가능성)
      error — PostgreSQL 쿼리 자체 실패 (DB 연결 끊김 등)
    """
    try:
        robots = RescueRobot.query.all()
        db_status = "ok" if robots else "empty"
        return jsonify({
            "db_status": db_status,
            "robots": [
                {
                    "id": r.id,
                    "status": r.status,
                    "pos_x": r.pos_x,
                    "pos_y": r.pos_y,
                    "explored_area": r.explored_area,
                    "total_area": r.total_area,
                }
                for r in robots
            ]
        }), 200
    except Exception as e:
        # 500 대신 200 반환 — 프론트가 항상 JSON 파싱 가능하도록
        return jsonify({
            "db_status": "error",
            "detail": str(e),
            "robots": []
        }), 200


@api_bp.route("/survivor-logs", methods=["GET"])
def get_survivor_logs():
    """survivor_logs 테이블 최근 조회 — 구조활동 기록 페이지용"""
    from app.models.database import SurvivorLog, Survivor
    limit = request.args.get("limit", 50, type=int)
    rows = (
        SurvivorLog.query
        .order_by(SurvivorLog.detection_time.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        survivor = Survivor.query.filter_by(id=row.id).first() if row.id else None
        result.append({
            "log_number": row.log_number,
            "time": row.detection_time.strftime("%H:%M:%S") if row.detection_time else "-",
            "survivor_id": row.id,
            "survivor_name": survivor.name if survivor else None,
            "detected_x": row.detected_x,
            "detected_y": row.detected_y,
            "similarity": round(row.similarity * 100, 1) if row.similarity is not None else None,
            "robot_id": row.robot_id,
            "img_path": row.img_path,
        })
    return jsonify(result), 200


from app.models.database import LoginUser


import bcrypt as _bcrypt
from app.models.database import LoginUser


@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password", "").encode("utf-8")

    user = LoginUser.query.filter_by(username=username).first()
    if not user or not _bcrypt.checkpw(password, user.password_hash.encode("utf-8")):
        return jsonify({"status": "error", "message": "아이디 또는 비밀번호가 틀렸습니다."}), 401

    return jsonify({"ok": True, "username": username}), 200
