#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
import requests
import cv2
import numpy as np
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry, OccupancyGrid  # 💡 OccupancyGrid 추가

# AMR팀 인터페이스 계약: 탐지는 rescue_interfaces/SurvivorDetectionArray
# (topic: /robot5/survivor/detections). 구버전 interfaces/TargetPose 대체.
try:
    from rescue_interfaces.msg import SurvivorDetectionArray

    HAS_DETECTIONS = True
except ImportError:
    HAS_DETECTIONS = False
    print(
        "⚠️ [주의] rescue_interfaces/SurvivorDetectionArray 모듈이 없어 탐지 DB 전송이 비활성화됩니다."
    )

FLASK_BASE = "http://127.0.0.1:8001/api"


def _extract_xy(msg, path: str):
    obj = msg
    for attr in path.split("."):
        obj = getattr(obj, attr)
    return float(obj.x), float(obj.y)


class RobotStatusBridge(Node):
    def __init__(self):
        super().__init__("robot_status_bridge")
        self.declare_parameter("robot_id", "robot5")
        self.robot_id = self.get_parameter("robot_id").value

        # 지도는 맵서버가 처음 열릴 때 과거 데이터를 들고 와야 하므로 transient_local 프로파일 적용
        map_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )

        # ── 토픽 구독 ──────────────────────────────────────────────────────────
        self.bt_sub = self.create_subscription(
            PoseStamped,
            f"/{self.robot_id}/report/survivor_found",
            self.bt_report_callback,
            10,
        )

        # 💡 [추가] 맵 토픽 구독 시작
        self.map_sub = self.create_subscription(
            OccupancyGrid, f"/{self.robot_id}/map", self.map_callback, map_qos
        )

        if HAS_DETECTIONS:
            self.det_sub = self.create_subscription(
                SurvivorDetectionArray,
                f"/{self.robot_id}/survivor/detections",
                self.detections_callback,
                qos_profile=sensor_qos,
            )

        self._pose_received = False
        self._try_pose_topics(sensor_qos)
        self.create_timer(1.0, self._pose_heartbeat)

        self.get_logger().info(
            f"✅ [로봇 상태 브릿지] 가동 완료 — robot_id={self.robot_id}"
        )

    # 💡 [추가] OccupancyGrid 토픽을 가로채서 이미지 바이너리로 백엔드 전송
    def map_callback(self, msg: OccupancyGrid):
        try:
            width = msg.info.width
            height = msg.info.height
            if width == 0 or height == 0:
                return

            # 1. 1차원 데이터 배열을 2차원 넘파이 행렬로 재정렬
            data = np.array(msg.data, dtype=np.int8).reshape((height, width))

            # 2. 맵 데이터 값 규칙 매핑 (0: 빈공간->흰색, 100: 벽->검은색, -1: 미탐사->회색)
            img = np.zeros((height, width), dtype=np.uint8)
            img[data == 0] = 255  # 탐사 완료 영역 (White)
            img[data == 100] = 0  # 벽/장애물 (Black)
            img[data == -1] = 127  # 미탐사 구역 (Gray)

            # 3. 데이터 시각적 가독성을 위해 상하 반전 (ROS 좌표계 -> OpenCV 이미지 좌표계 대응)
            img = cv2.flip(img, 0)

            # 4. 메모리 상에서 PNG 포맷으로 압축 이미지 인코딩
            _, img_encoded = cv2.imencode(".png", img)

            # 5. Flask 백엔드로 이미지 바이너리를 멀티파트 폼 데이터로 슛!
            files = {
                "map_image": (
                    f"{self.robot_id}_map.png",
                    img_encoded.tobytes(),
                    "image/png",
                )
            }
            requests.post(
                f"{FLASK_BASE}/robots/{self.robot_id}/map", files=files, timeout=2.0
            )

            self.get_logger().info(
                f"🎯 [지도 동기화] 백엔드로 실시간 맵 전송 성공 ({width}x{height})"
            )
        except Exception as e:
            self.get_logger().error(f"❌ 지도 가공 및 전송 실패: {e}")

    def _try_pose_topics(self, qos):
        PRIORITY = [
            (f"/{self.robot_id}/robot_pose", PoseStamped, "pose.position"),
            (
                f"/{self.robot_id}/amcl_pose",
                PoseWithCovarianceStamped,
                "pose.pose.position",
            ),
            (f"/{self.robot_id}/odom", Odometry, "pose.pose.position"),
        ]
        for topic, msg_type, path in PRIORITY:
            try:
                self.create_subscription(
                    msg_type,
                    topic,
                    lambda msg, p=path: self._pose_callback(msg, p),
                    qos_profile=qos,
                )
                self.get_logger().info(f"📍 위치 토픽 구독: {topic}")
                break
            except Exception:
                pass

    def _pose_callback(self, msg, path: str):
        try:
            self._last_x, self._last_y = _extract_xy(msg, path)
            self._pose_received = True
        except Exception:
            pass

    def _pose_heartbeat(self):
        if self._pose_received:
            self._send_to_flask(
                f"{FLASK_BASE}/robots/{self.robot_id}/pose",
                {"x": self._last_x, "y": self._last_y, "status": "MOVING"},
                "위치",
            )

    def bt_report_callback(self, msg: PoseStamped):
        data = {
            "x": msg.pose.position.x,
            "y": msg.pose.position.y,
            "message": "[임무 성공] 생존자 확보",
        }
        self._send_to_flask(
            f"{FLASK_BASE}/robots/{self.robot_id}/nav_success", data, "BT 임무완료"
        )

    def detections_callback(self, msg):
        # AMR 계약(SurvivorDetectionArray): class_name은 person/exit_sign.
        # 사람 탐지만 /survivor-logs로 적재(신원은 중앙에서 판별 → 미식별로 기록).
        for det in msg.detections:
            if det.class_name != "person":
                continue  # exit_sign 등은 goal 후보로 별도 처리
            data = {
                "id": None,  # 신원 미상(중앙 식별 전)
                "detected_x": float(det.pose.pose.position.x),
                "detected_y": float(det.pose.pose.position.y),
                "similarity": float(det.confidence),
                "robot_id": self.robot_id,
                "img_path": det.image_uri or None,
            }
            self._send_to_flask(f"{FLASK_BASE}/survivor-logs", data, "탐지")

    def _send_to_flask(self, url, data, label):
        try:
            requests.post(url, json=data, timeout=1.0)
        except Exception:
            pass


def main(args=None):
    rclpy.init(args=args)
    node = RobotStatusBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
