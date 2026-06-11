#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
import requests
import numpy as np

# 패키지에서 "벡터 추출 모델"만 끌어옵니다.
from survivor_identity.face_identification.models import load_models
from survivor_identity.face_identification.embedding import embed_image


class BackendAIVisionBridge(Node):
    def __init__(self):
        super().__init__("backend_ai_vision_bridge")
        self.bridge = CvBridge()

        # 1. 팀원 AI 모델 메모리 로드 (GPU가 있으면 ctx_id=0, 없으면 -1)
        self.get_logger().info("🧠 InsightFace(buffalo_l) 모델 로딩 중...")
        self.models = load_models(model_name="buffalo_l", ctx_id=-1)

        # 2. AMR이 보내는 "크롭된 얼굴 이미지" 토픽 구독 (화재 현장 네트워크 고려 BEST_EFFORT)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
        )
        # 예: 로봇이 얼굴만 잘라서 압축해서 보내는 토픽
        self.create_subscription(
            CompressedImage,
            "/robot1/survivor/face_crop/compressed",
            self.crop_callback,
            qos_profile,
        )

        self.flask_url = "http://127.0.0.1:8001/api/survivors/identify"
        self.get_logger().info(
            "📡 [백엔드 AI 브릿지] 로봇의 크롭 이미지 수신 및 벡터 추출 대기 중..."
        )

    def crop_callback(self, msg: CompressedImage):
        try:
            # 1. ROS2 압축 이미지 -> OpenCV 변환
            cv_image = self.bridge.compressed_imgmsg_to_cv2(
                msg, desired_encoding="bgr8"
            )

            # 2. 팀원 로직 활용: 이미지에서 특징 벡터 추출 (Embedding)
            embedding = embed_image(
                cv_image, self.models.recognition, self.models.landmark
            )

            if embedding is None:
                self.get_logger().warn(
                    "⚠️ 얼굴 특징점을 찾을 수 없습니다. (화질 불량 또는 얼굴 아님)"
                )
                return

            # 512차원 numpy 배열을 일반 Python List로 변환
            face_vector = embedding.tolist()

            # 3. 기범님의 완성된 Flask 백엔드로 POST 요청 (pgvector 매칭)
            res = requests.post(
                self.flask_url, json={"vector": face_vector}, timeout=2.0
            )
            data = res.json()

            if res.status_code == 200 and data.get("matched"):
                user = data["data"]
                self.get_logger().info(
                    f"🎯 [DB 매칭 완료] {user['name']} 님 식별! (유사도: {user['similarity']}%)"
                )
            else:
                self.get_logger().info("❓ [미식별] 등록되지 않은 구조대상자입니다.")

        except Exception as e:
            self.get_logger().error(f"❌ AI 연산 또는 통신 에러: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = BackendAIVisionBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
