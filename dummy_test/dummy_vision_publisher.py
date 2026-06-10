#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import requests
import random
from interfaces.msg import TargetPose


class DummyVisionPublisher(Node):
    def __init__(self):
        super().__init__("dummy_vision_publisher")

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self.publisher_ = self.create_publisher(
            TargetPose, "/yolo/target_pose", qos_profile
        )
        self.timer = self.create_timer(
            4.0, self.timer_callback
        )  # 너무 빠르지 않게 4초 주기

        self.identify_url = "http://127.0.0.1:8001/api/survivors/identify"
        self.get_logger().info("🤖 [비전 더미 노드] 실시간 벡터 매칭 시뮬레이터 가동!")

    def timer_callback(self):
        # 50% 확률로 우리가 심어둔 정답 벡터(1번 원소가 높음) 생성, 50% 확률로 미식별 노이즈 벡터 생성
        is_known = random.choice([True, False])

        if is_known:
            mock_vector = [
                round(random.uniform(0.85, 0.92), 4)
                if i == 0
                else round(random.uniform(0.08, 0.12), 4)
                for i in range(512)
            ]
            self.get_logger().info(
                "🔍 [카메라] 등록된 생존자 패턴 포착! 매칭 시도 중..."
            )
        else:
            mock_vector = [round(random.uniform(0.4, 0.6), 4) for _ in range(512)]
            self.get_logger().info("🔍 [카메라] 미상 인원 패턴 포착! 매칭 시도 중...")

        msg = TargetPose()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        try:
            # 백엔드에 256차원 벡터를 보내 pgvector 코사인 유사도 연산 요청
            res = requests.post(
                self.identify_url, json={"vector": mock_vector}, timeout=1.0
            )
            data = res.json()

            if res.status_code == 200 and data.get("matched"):
                user = data["data"]
                msg.class_name = user["id"]
                msg.confidence = user["similarity"] / 100.0
                self.get_logger().info(
                    f"✅ [매칭 성공] {user['name']} (유사도: {user['similarity']:.1f}%)"
                )
            else:
                msg.class_name = "Unknown"
                msg.confidence = 0.5
                self.get_logger().warn(f"⚠️ [매칭 실패] 일치하는 대상자 없음")

        except Exception as e:
            self.get_logger().error(f"❌ API 에러: {e}")
            return

        # 가상 좌표 생성 및 발행
        msg.pose.position.x = round(random.uniform(5.0, 15.0), 2)
        msg.pose.position.y = round(random.uniform(5.0, 15.0), 2)

        self.publisher_.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = DummyVisionPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
