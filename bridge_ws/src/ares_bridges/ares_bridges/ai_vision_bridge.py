#!/usr/bin/env python3
import os
import sys
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import requests

DATABASE_DIR = os.path.expanduser("~/rescue_amr_project/database")
if DATABASE_DIR not in sys.path:
    sys.path.append(DATABASE_DIR)

from survivor_identity.face_identification.models import load_models
from survivor_identity.face_identification.embedding import embed_image


class AiVisionBridge(Node):  # 💡 클래스명 변경
    def __init__(self):
        super().__init__("ai_vision_bridge")
        self.bridge = CvBridge()
        self.declare_parameter("robot_id", "robot5")
        self.robot_id = self.get_parameter("robot_id").value

        self.get_logger().info("🧠 InsightFace(buffalo_l) 모델 로딩 중...")
        self.models = load_models(model_name="buffalo_l", ctx_id=-1)

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )

        # 동적 로봇 ID 할당
        topic_name = f"/{self.robot_id}/survivor/face_crop/compressed"
        self.create_subscription(
            CompressedImage, topic_name, self.crop_callback, qos_profile
        )

        self.flask_url = "http://127.0.0.1:8001/api/survivors/identify"
        self.get_logger().info(f"📡 [AI 비전 브릿지] {topic_name} 수신 대기 중...")

    def crop_callback(self, msg: CompressedImage):
        try:
            cv_image = self.bridge.compressed_imgmsg_to_cv2(
                msg, desired_encoding="bgr8"
            )
            embedding = embed_image(
                cv_image, self.models.recognition, self.models.landmark
            )

            if embedding is None:
                return

            res = requests.post(
                self.flask_url, json={"vector": embedding.tolist()}, timeout=2.0
            )
            data = res.json()

            if res.status_code == 200 and data.get("matched"):
                user = data["data"]
                self.get_logger().info(
                    f"🎯 [DB 매칭 완료] {user['name']} 님 식별! (유사도: {user['similarity']}%)"
                )
        except Exception as e:
            self.get_logger().error(f"❌ AI 연산 또는 통신 에러: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = AiVisionBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
