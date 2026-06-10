#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge
import cv2
import numpy as np
import math


class DummyYoloVideoPublisher(Node):
    def __init__(self):
        super().__init__("dummy_yolo_video_publisher")
        self.bridge = CvBridge()

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,     
        )

        # 팀원의 yolo_webrtc_bridge가 구독하는 토픽명 컨벤션 일치
        self.publisher_ = self.create_publisher(
            CompressedImage, "rgb_processed/compressed", qos_profile
        )

        # 15 FPS 속도로 프레임 생성 타이머 작동
        self.timer = self.create_timer(1.0 / 15.0, self.timer_callback)
        self.frame_id = 0
        self.get_logger().info(
            "📷 [비전 더미 노드] YOLO 어노테이션 영상 시뮬레이터 가동 (15 FPS)"
        )

    def timer_callback(self):
        self.frame_id += 1

        # 1. Base 가상 화면 생성 (재난 현장 느낌의 어두운 배경)
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 40

        # 격자 무늬 배경 추가
        for i in range(0, 640, 40):
            cv2.line(frame, (i, 0), (i, 480), (60, 60, 60), 1)
        for j in range(0, 480, 40):
            cv2.line(frame, (0, j), (640, j), (60, 60, 60), 1)

        # 2. 가상의 이동하는 YOLO Bounding Box 계산 (사인 함수 활용 이동)
        t = self.frame_id * 0.05
        box_x = int(320 + 150 * math.cos(t))
        box_y = int(240 + 80 * math.sin(t))
        box_w, box_h = 120, 160

        x1, y1 = box_x - box_w // 2, box_y - box_h // 2
        x2, y2 = box_x + box_w // 2, box_y + box_h // 2

        # 3. YOLO 어노테이션 효과 그리기 (박스 + 레이블)
        # 바운딩 박스 (초록색)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        # 인공지능 탐지 레이블 오버레이
        label = f"Survivor: {85.5 + 10 * math.sin(t / 2):.1f}%"
        cv2.putText(
            frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )

        # OAK-D 카메라 상태 및 로봇 ID 메타데이터 화면 표시
        cv2.putText(
            frame,
            "ARES-AMR ROBOT5 LIVE FEED",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (220, 220, 220),
            2,
        )
        cv2.putText(
            frame,
            f"FRAME: {self.frame_id}",
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (150, 150, 150),
            1,
        )

        # 4. OpenCV BGR 이미지를 ROS2 CompressedImage 메시지로 인코딩
        msg = self.bridge.cv2_to_compressed_imgmsg(frame, dst_format="jpg")
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "oakd_camera_optical_frame"

        self.publisher_.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(DummyYoloVideoPublisher())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
