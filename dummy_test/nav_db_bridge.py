#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import requests

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Float32MultiArray  # 임시 탐사율 타입


class RESTClient:
    def __init__(self, base_url, logger):
        self.base_url = base_url
        self.logger = logger
        self.timeout = 1.0

    def post(self, endpoint: str, payload: dict, label: str):
        url = f"{self.base_url}{endpoint}"
        try:
            res = requests.post(url, json=payload, timeout=self.timeout)
            if res.status_code not in [200, 201]:
                self.logger.error(f"⚠️ 백엔드 거부 {res.status_code} ({label})")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Flask 통신 실패 ({label}): {e}")


class NavDbBridge(Node):
    def __init__(self):
        super().__init__("nav_db_bridge")

        # 네임스페이스 처리를 위한 동적 로봇 ID (기본값 robot5)
        self.declare_parameter("robot_id", "robot5")
        self.robot_id = (
            self.get_parameter("robot_id").get_parameter_value().string_value
        )
        self.api = RESTClient(
            base_url="http://127.0.0.1:8001/api", logger=self.get_logger()
        )

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # 1. 위치(Pose) 구독: /robot5/pose
        self.create_subscription(
            PoseStamped, f"/{self.robot_id}/pose", self.pose_callback, qos
        )

        # 2. 배터리 구독: /robot5/battery_state
        self.create_subscription(
            BatteryState, f"/{self.robot_id}/battery_state", self.battery_callback, qos
        )

        # 3. 탐사율 구독: /robot5/camera_coverage_updates (테스트용 임시 타입 적용)
        self.create_subscription(
            Float32MultiArray,
            f"/{self.robot_id}/camera_coverage_updates",
            self.explore_callback,
            qos,
        )

        # 트래픽 제어용 변수
        self._last_x, self._last_y = 0.0, 0.0
        self._last_battery = 100
        self._pose_updated = False

        self.create_timer(1.0, self.sync_to_db)
        self.get_logger().info(
            f"✅ [ARES 브릿지] 동기화 준비 완료 — 대상: {self.robot_id}"
        )

    def pose_callback(self, msg: PoseStamped):
        self._last_x = msg.pose.position.x
        self._last_y = msg.pose.position.y
        self._pose_updated = True

    def battery_callback(self, msg: BatteryState):
        self._last_battery = int(msg.percentage)

    def explore_callback(self, msg: Float32MultiArray):
        if len(msg.data) >= 2:
            payload = {
                "explored_area": float(msg.data[0]),
                "total_area": float(msg.data[1]),
            }
            self.api.post(f"/robots/{self.robot_id}/exploration", payload, "탐사율")

    def sync_to_db(self):
        if self._pose_updated:
            payload = {
                "x": self._last_x,
                "y": self._last_y,
                "status": "MOVING",
                "battery": self._last_battery,
            }
            self.api.post(f"/robots/{self.robot_id}/pose", payload, "상태(위치/배터리)")
            self._pose_updated = False


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(NavDbBridge())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
