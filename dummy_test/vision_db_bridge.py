#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import requests

# 커스텀 메시지 import (vision_ws의 interfaces 사용)
from interfaces.msg import TargetPose

TARGET_VISION_TOPIC = "/yolo/target_pose"


class VisionDbBridge(Node):
    def __init__(self):
        super().__init__("vision_db_bridge")

        self.declare_parameter("robot_id", "robot5")
        self.robot_id = (
            self.get_parameter("robot_id").get_parameter_value().string_value
        )

        self.backend_url = "http://127.0.0.1:8001/api/survivor-logs"

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        self.sub = self.create_subscription(
            TargetPose, TARGET_VISION_TOPIC, self.vision_callback, qos_profile
        )

        self.get_logger().info(f"👁️ [비전 브릿지] 가동 완료 — 대상: {self.robot_id}")

    def vision_callback(self, msg: TargetPose):
        self.get_logger().info(
            f"🚀 [YOLO 탐지 수신] ID: {msg.class_name}, 신뢰도: {msg.confidence:.2f}"
        )

        data = {
            "id": msg.class_name,  # 매칭 실패시 "Unknown"이 들어옴
            "detected_x": msg.pose.position.x,
            "detected_y": msg.pose.position.y,
            "similarity": float(msg.confidence),
            "robot_id": self.robot_id,
            "img_path": f"/workspace/app/static/img/captured/{msg.class_name}.jpg",
        }

        try:
            res = requests.post(self.backend_url, json=data, timeout=1.0)
            if res.status_code == 201:
                self.get_logger().info(
                    f"🎯 [DB 저장 성공] 인시던트 로그 및 구조 로그 갱신 완"
                )
            else:
                self.get_logger().error(f"⚠️ 백엔드 거부: {res.text}")
        except Exception as e:
            self.get_logger().error(f"❌ Flask 통신 에러: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = VisionDbBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
