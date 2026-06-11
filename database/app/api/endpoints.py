import uuid
import threading
import urllib.request
import cv2
import os
import numpy as np
import bcrypt as _bcrypt
from flask import Blueprint, request, jsonify, current_app
from supabase import create_client

from app.core import config
from app.models.database import db, IncidentLog, Survivor, SurvivorLog, RescueRobot
from app.services.rescue_amr_service import RescueAMRService
from app.services.survivor_service import SurvivorService
from app.repositories.rescue_amr_repository import RescueAmrRepository

api_bp = Blueprint("api", __name__)

# =====================================================================
# [전역 상태] 비동기 동기화 상태 저장소
# =====================================================================
sync_progress = {
    "is_running": False,
    "total": 0,
    "current": 0,
    "message": "대기 중",
    "error": None,
}


def convert_supabase_url(img_url):
    """Supabase 스토리지 상대경로를 Public 절대경로로 변환"""
    if img_url and not img_url.startswith("http"):
        return f"{config.SUPABASE_URL}/storage/v1/object/public/{img_url}"
    return img_url


# =====================================================================
# 1. 인증 (Auth) API
# =====================================================================
@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password", "").encode("utf-8")

    try:
        sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        rows = (
            sb.table("auth_users")
            .select("password_hash")
            .eq("username", username)
            .execute()
            .data
        )
    except Exception:
        return jsonify(
            {"status": "error", "message": "인증 서버에 연결할 수 없습니다."}
        ), 503

    if not rows or not _bcrypt.checkpw(
        password, rows[0]["password_hash"].strip().encode("utf-8")
    ):
        return jsonify(
            {"status": "error", "message": "아이디 또는 비밀번호가 틀렸습니다."}
        ), 401

    return jsonify({"ok": True, "username": username}), 200


# =====================================================================
# 2. AI 비동기 동기화 (Sync) API
# =====================================================================
def async_sync_worker(app_context):
    """Flask 메인 컨텍스트를 격리하여 백그라운드에서 AI 연산 수행"""
    global sync_progress

    with app_context:
        # 무거운 AI 모델은 서버 시작 속도에 영향을 주지 않도록 스레드 내부에서 지연 임포트
        from survivor_identity.face_identification.models import load_models
        from survivor_identity.face_identification.embedding import embed_image
        from sync_survivors import fetch_from_supabase

        try:
            sync_progress["message"] = "Supabase에서 원본 데이터 수신 중..."
            rows = fetch_from_supabase()

            sync_progress["total"] = len(rows)
            sync_progress["current"] = 0
            sync_progress["message"] = "AI 인식 모델(InsightFace) 메모리 로드 중..."

            models = load_models(model_name="buffalo_l", ctx_id=-1)

            for row in rows:
                s_id, name = row["id"], row["name"]
                sync_progress["message"] = (
                    f"[{name}] 신원 동기화 및 512차원 특징점 계산 중..."
                )

                img_url = convert_supabase_url(row.get("face"))
                survivor = Survivor.query.filter_by(id=s_id).first() or Survivor(
                    id=s_id
                )

                survivor.name = name
                survivor.sex = row.get("sex")
                survivor.phone_number = row.get("phone_number")
                survivor.face = img_url
                db.session.add(survivor)
                db.session.commit()

                if img_url:
                    try:
                        req = urllib.request.urlopen(img_url, timeout=3.0)
                        arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
                        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                        embedding = embed_image(
                            img, models.recognition, models.landmark
                        )
                        if embedding is not None:
                            survivor.face_vector = embedding.tolist()
                            db.session.commit()
                    except Exception as img_err:
                        print(f"⚠️ [{name}] 이미지 처리 건너뜀: {img_err}", flush=True)

                sync_progress["current"] += 1

            sync_progress["message"] = "모든 구조대상자 AI 동기화 완료!"
        except Exception as e:
            db.session.rollback()
            sync_progress["error"] = str(e)
            sync_progress["message"] = f"❌ 동기화 실패: {str(e)}"
        finally:
            sync_progress["is_running"] = False


@api_bp.route("/sync/start", methods=["POST"])
def start_integration_sync():
    global sync_progress
    if sync_progress["is_running"]:
        return jsonify(
            {"status": "processing", "message": "이미 인공지능 동기화가 진행 중입니다."}
        ), 200

    sync_progress.update({"is_running": True, "error": None, "current": 0})

    app_context = current_app.app_context()
    threading.Thread(target=async_sync_worker, args=(app_context,), daemon=True).start()

    return jsonify(
        {"status": "started", "message": "AI 특징점 분석 백그라운드 태스크 가동 완료"}
    ), 200


@api_bp.route("/sync/status", methods=["GET"])
def get_integration_sync_status():
    return jsonify(sync_progress), 200


# =====================================================================
# 3. 로봇 상태 & 제어 (Robot) API
# =====================================================================
@api_bp.route("/robots", methods=["GET"])
def get_robots():
    try:
        robots = RescueRobot.query.all()
        return jsonify(
            {
                "db_status": "ok" if robots else "empty",
                "robots": [
                    {
                        "id": r.id,
                        "status": r.status,
                        "mode": r.mode,
                        "battery": r.battery,
                        "pos_x": r.pos_x,
                        "pos_y": r.pos_y,
                        "coverage_ratio": r.coverage_ratio,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                    for r in robots
                ],
            }
        ), 200
    except Exception as e:
        return jsonify({"db_status": "error", "detail": str(e), "robots": []}), 200

@api_bp.route("/robots/<robot_id>/map", methods=["POST"])
def upload_robot_map(robot_id):
    """💡 [추가] 브릿지 노드가 가공한 PNG 맵 이미지를 수신하여 정적 폴더에 저장"""
    if "map_image" not in request.files:
        return jsonify({"error": "No map file content"}), 400

    file = request.files["map_image"]
    if file.filename == "":
        return jsonify({"error": "No filename"}), 400

    try:
        # Flask 어플리케이션의 내부 static 폴더 내부에 'maps' 디렉토리 경로 지정
        # 예: /workspace/app/static/maps/
        static_maps_dir = os.path.join(current_app.static_folder, "maps")

        # 폴더가 없으면 에러 방지를 위해 자동 생성
        if not os.path.exists(static_maps_dir):
            os.makedirs(static_maps_dir, exist_ok=True)

        # 저장될 파일명 확정 (예: robot5_map.png)
        filename = f"{robot_id}_map.png"
        file_path = os.path.join(static_maps_dir, filename)

        # 기존 맵 이미지 위에 새로운 실시간 맵을 덮어쓰기(Overwrite)
        file.save(file_path)

        return jsonify({"ok": True, "path": f"/static/maps/{filename}"}), 200
    except Exception as e:
        print(f"❌ [API] 지반 지도 파일 저장 실패: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500
    
@api_bp.route("/robots/<robot_id>/pose", methods=["POST"])
def update_robot_pose(robot_id):
    data = request.get_json()
    RescueAMRService.update_pose(
        robot_id=robot_id,
        x=data.get("x", 0.0),
        y=data.get("y", 0.0),
        status=data.get("status"),
        battery=data.get("battery"),
    )
    return jsonify({"ok": True}), 200


@api_bp.route("/robots/<robot_id>/coverage", methods=["POST"])
def update_robot_coverage(robot_id):
    data = request.get_json()
    RescueAMRService.update_coverage(
        robot_id=robot_id,
        coverage_ratio=data.get("coverage_ratio", 0.0),
        mode=data.get("mode"),
    )
    return jsonify({"ok": True}), 200


# =====================================================================
# 4. 로그 수집 (Logging) API - 텍스트/이벤트 수신
# =====================================================================
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
    """일반/장애/YOLO 인시던트 텍스트 로그 수신"""
    data = request.get_json()
    RescueAmrRepository.create_log(
        IncidentLog(
            id=str(uuid.uuid4()),
            robot_id=data.get("robot_id", "ARES-VISION"),
            message=data.get("message", ""),
        )
    )
    return jsonify({"status": "ok"}), 200


@api_bp.route("/robots/<robot_id>/nav_success", methods=["POST"])
def handle_nav_success(robot_id):
    """주행 성공 알림 및 관련 로그 생성"""
    data = request.get_json()
    RescueAMRService.process_nav_success(
        robot_id, data["x"], data["y"], data["message"]
    )
    return jsonify({"status": "ok"}), 200


# =====================================================================
# 5. 구조대상자 식별 & 이력 (Survivor) API
# =====================================================================
@api_bp.route("/survivors", methods=["GET"])
def get_survivors():
    survivors = Survivor.query.all()
    return jsonify(
        [
            {
                "id": s.id,
                "name": s.name,
                "sex": s.sex,
                "phone_number": s.phone_number,
                "face": s.face,
            }
            for s in survivors
        ]
    ), 200


@api_bp.route("/survivors/identify", methods=["POST"])
def identify_survivor():
    data = request.get_json()
    input_vector = data.get("vector")

    print(
        f"\n📥 [API] /survivors/identify 수신 (벡터: {len(input_vector) if input_vector else 0}차원)",
        flush=True,
    )
    try:
        res_body, status_code = SurvivorService.identify_survivor_by_vector(
            input_vector
        )
        return jsonify({"status": "success", **res_body}), status_code
    except Exception as e:
        print(f"❌ [API] 매칭 연산 실패: {str(e)}", flush=True)
        return jsonify({"status": "success", "matched": False, "message": str(e)}), 200


@api_bp.route("/survivor-logs", methods=["GET"])
def get_survivor_logs():
    limit = request.args.get("limit", 50, type=int)
    rows = (
        SurvivorLog.query.order_by(SurvivorLog.detection_time.desc()).limit(limit).all()
    )

    result = []
    for row in rows:
        survivor = Survivor.query.filter_by(id=row.id).first() if row.id else None
        result.append(
            {
                "log_number": row.log_number,
                "time": row.detection_time.strftime("%H:%M:%S")
                if row.detection_time
                else "-",
                "survivor_id": row.id,
                "survivor_name": survivor.name if survivor else None,
                "detected_x": row.detected_x,
                "detected_y": row.detected_y,
                "similarity": round(row.similarity * 100, 1)
                if row.similarity is not None
                else None,
                "robot_id": row.robot_id,
                "img_path": row.img_path,
            }
        )
    return jsonify(result), 200


@api_bp.route("/survivor-logs", methods=["POST"])
def add_survivor_log():
    data = request.get_json()
    try:
        res_body, status_code = SurvivorService.process_survivor_log(data)
        return jsonify(res_body), status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
