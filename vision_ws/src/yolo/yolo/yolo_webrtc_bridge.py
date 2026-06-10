#!/usr/bin/env python3
import numpy as np
import asyncio
import json
import cv2
import sys
import threading
from fractions import Fraction

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage
from cv_bridge import CvBridge

from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame

# 글로벌 프레임 공유 자원 및 커넥션 관리
latest_frame = None
frame_lock = threading.Lock()
pcs = set()
_ROBOT_ID = "robot1"


class RosImageTrack(MediaStreamTrack):
    """ROS2 토픽 이미지를 WebRTC 비디오 트랙으로 변환하는 클래스"""

    kind = "video"

    def __init__(self):
        super().__init__()
        self.bridge = CvBridge()
        # 💡 타임스탬프 계산을 위한 초기 변수 세팅
        self._start_time = None
        self._pts = 0
        self._frame_interval = 1.0 / 15.0  # 15 FPS 기준
        self._pts_step = max(1, int(90000 * self._frame_interval))

    async def _next_timestamp(self):
        """💡 원본 코드에서 누락되었던 WebRTC 정밀 타임스탬프 계산 메서드 구현"""
        loop = asyncio.get_event_loop()
        if self._start_time is None:
            self._start_time = loop.time()
            self._pts = 0
            return self._pts, Fraction(1, 90000)

        self._pts += self._pts_step
        next_time = self._start_time + (self._pts / 90000)
        wait = next_time - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        return self._pts, Fraction(1, 90000)

    async def recv(self):
        global latest_frame

        # 💡 다음 프레임 전송 타이밍 대기
        pts, time_base = await self._next_timestamp()

        with frame_lock:
            if latest_frame is None:
                # 대기 상태일 때 보낼 가짜 더미 화면
                img = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(
                    img,
                    "ARES Video Waiting...",
                    (160, 240),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 0, 255),
                    2,
                )
            else:
                img = latest_frame

        # OpenCV BGR 이미지를 WebRTC 표준 VideoFrame(RGB)으로 변환
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        frame = VideoFrame.from_ndarray(img_rgb, format="rgb24")

        frame.pts = pts
        frame.time_base = time_base
        return frame


class YoloWebRtcBridge(Node):
    """ROS2 이미지 토픽을 가로채서 WebRTC 통신망으로 전달하는 브릿지 노드"""

    def __init__(self):
        super().__init__("yolo_webrtc_bridge")
        self.bridge = CvBridge()

        # 💡 ROS2 공식 Parameter API 선언
        self.declare_parameter("port", 8002)
        self.declare_parameter("topic", "rgb_processed/compressed")
        self.declare_parameter("robot", "robot1")

        self.port = self.get_parameter("port").value
        self.topic_name = self.get_parameter("topic").value
        self.robot_id = self.get_parameter("robot").value

        # 💡 기범님의 설계 원칙 반영: 영상 스트리밍 특화 QoS 설정 (BEST_EFFORT & 깊이 1)
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )

        self.subscription = self.create_subscription(
            CompressedImage, self.topic_name, self.image_callback, qos_profile
        )

        # 30프레임 주기 로그용 변수
        self.frame_cnt = 0
        self.get_logger().info(
            f"👀 [{self.robot_id}] 브릿지 가동! 구독 토픽: {self.topic_name} (BEST_EFFORT)"
        )

    def image_callback(self, msg):
        global latest_frame
        try:
            cv_image = self.bridge.compressed_imgmsg_to_cv2(
                msg, desired_encoding="bgr8"
            )
            with frame_lock:
                latest_frame = cv_image

            # 실시간 프레임 수신 디버깅 확인 로그
            self.frame_cnt += 1
            if self.frame_cnt % 30 == 0:
                self.get_logger().info(
                    "✅ ROS2 영상 30프레임 수신 및 OpenCV 디코딩 성공!"
                )
        except Exception as e:
            self.get_logger().error(f"이미지 디코딩 실패: {e}")


# =====================================================================
# WebRTC 시그널링 핸들러 (CORS 완벽 대응)
# =====================================================================
async def handle_offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)
    pc.addTrack(RosImageTrack())

    @pc.on("connectionstatechange")
    async def on_state():
        # 💡 버퍼에 막히지 않도록 flush=True 추가하여 실시간 커넥션 모니터링
        print(
            f"🔗 [{_ROBOT_ID}] WebRTC 연결 상태 변화: {pc.connectionState}", flush=True
        )
        if pc.connectionState in ("failed", "closed"):
            pcs.discard(pc)
            await pc.close()

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
    )


async def handle_options(request):
    return web.Response(
        status=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
    )


def main():
    rclpy.init(args=sys.argv)
    node = YoloWebRtcBridge()

    global _ROBOT_ID
    _ROBOT_ID = node.robot_id
    port = node.port

    # ROS2 스핀 스레드 분리 실행
    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    app = web.Application()
    app.router.add_post("/offer", handle_offer)
    app.router.add_options("/offer", handle_options)

    node.get_logger().info(
        f"🚀 WebRTC 서버가 {port} 포트에서 요청을 받을 준비가 되었습니다."
    )

    try:
        web.run_app(app, host="0.0.0.0", port=port, print=None)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
