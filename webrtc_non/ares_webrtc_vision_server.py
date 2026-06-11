#!/usr/bin/env python3
"""
ares_webrtc_vision_server.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
팀원 webrtc_vision_server.py의 딜레이 개선 로직을 그대로 가져오되,
Legacy 시그널링 서버 방식을 제거하고 aiohttp 직접 /offer 방식으로 교체.
로봇 2대를 다른 포트로 동시 실행 가능.

[실행]
  # 로봇 1
  WEBRTC_PORT=8002 WEBRTC_IMAGE_TOPIC=/robot1/oakd/rgb/image_raw/compressed \\
    python3 ares_webrtc_vision_server.py

  # robot5 annotated 영상
  WEBRTC_PORT=8003 WEBRTC_IMAGE_TOPIC=/robot5/survivor/annotated/compressed \\
    python3 ares_webrtc_vision_server.py

[환경변수]
  WEBRTC_PORT               포트 (기본 8002)
  WEBRTC_IMAGE_TOPIC        구독 토픽 (기본 /robot1/oakd/rgb/image_raw/compressed)
  WEBRTC_IMAGE_TYPE         compressed | raw (토픽명으로 자동판별)
  WEBRTC_IMAGE_QOS_DEPTH    QoS depth (기본 1 — 항상 최신 프레임)
  WEBRTC_IMAGE_QOS_RELIABILITY  best_effort | reliable (기본 best_effort)
  WEBRTC_TARGET_FPS         브라우저 전송 FPS (기본 15)
  WEBRTC_MAX_WIDTH          리사이즈 최대 폭 px (기본 480, 0=원본)
  WEBRTC_USE_PUBLIC_ICE     1이면 STUN/TURN 사용 (기본 0 = LAN only)
  WEBRTC_ROBOT_ID           로봇 식별자 로그용 (기본 robot1)
"""

import asyncio
import json
import os
import time
import threading
from fractions import Fraction

import cv2
import numpy as np
from av import VideoFrame
from aiohttp import web
from aiortc import (
    RTCPeerConnection, RTCSessionDescription,
    RTCConfiguration, RTCIceServer,
    VideoStreamTrack,
)

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import CompressedImage, Image
    from cv_bridge import CvBridge
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("⚠️  ROS2 없음 — 더미 프레임 모드")

# ── 환경변수 설정 ─────────────────────────────────────────────────────────────
PORT              = int(os.getenv("WEBRTC_PORT",  "8002"))
IMAGE_TOPIC       = os.getenv("WEBRTC_IMAGE_TOPIC", "/robot1/oakd/rgb/image_raw/compressed")
IMAGE_TYPE        = os.getenv("WEBRTC_IMAGE_TYPE",  "").strip().lower()
IMAGE_QOS_DEPTH   = int(os.getenv("WEBRTC_IMAGE_QOS_DEPTH", "1"))
IMAGE_QOS_RELIABILITY = os.getenv("WEBRTC_IMAGE_QOS_RELIABILITY", "best_effort").lower()
TARGET_FPS        = float(os.getenv("WEBRTC_TARGET_FPS", "15"))
MAX_WIDTH         = int(os.getenv("WEBRTC_MAX_WIDTH", "480"))
USE_PUBLIC_ICE    = os.getenv("WEBRTC_USE_PUBLIC_ICE", "").lower() in ("1", "true", "yes")
ROBOT_ID          = os.getenv("WEBRTC_ROBOT_ID", "robot1")
RTP_CLOCK_RATE    = 90000
STATS_INTERVAL    = 5.0


def use_compressed():
    return IMAGE_TYPE == "compressed" or IMAGE_TOPIC.endswith("/compressed")


def build_ice_servers():
    if not USE_PUBLIC_ICE:
        return []
    return [
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(urls="turn:openrelay.metered.ca:80",
                     username="openrelayproject", credential="openrelayproject"),
        RTCIceServer(urls="turn:openrelay.metered.ca:443",
                     username="openrelayproject", credential="openrelayproject"),
    ]


def build_image_qos():
    reliability = (
        ReliabilityPolicy.RELIABLE
        if IMAGE_QOS_RELIABILITY == "reliable"
        else ReliabilityPolicy.BEST_EFFORT
    )
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=IMAGE_QOS_DEPTH,       # depth=1 → 항상 최신 프레임만, 버퍼 없음
        reliability=reliability,
        durability=DurabilityPolicy.VOLATILE,
    )


def resize_for_stream(frame):
    if MAX_WIDTH <= 0 or frame.shape[1] <= MAX_WIDTH:
        return frame
    h, w = frame.shape[:2]
    scale = MAX_WIDTH / float(w)
    return cv2.resize(frame, (MAX_WIDTH, int(h * scale)), interpolation=cv2.INTER_AREA)


def image_to_rgb(frame, encoding):
    if encoding in ("rgb8", "8UC3"):
        return frame
    if encoding == "bgr8":
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if encoding == "mono8":
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


# ── 공유 상태 ─────────────────────────────────────────────────────────────────
class SharedState:
    def __init__(self):
        self._frame      = None
        self._frame_time = 0.0
        self._lock       = threading.Lock()
        self._accepted   = 0
        self._dropped    = 0
        self._sent       = 0
        self._channel    = None
        self._loop       = None

        # 프레임 드롭: TARGET_FPS 초과 분은 버림
        self._min_interval = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 0.0
        self._last_accept  = 0.0

    def should_accept(self):
        now = time.monotonic()
        if self._min_interval > 0 and now - self._last_accept < self._min_interval:
            self._dropped += 1
            return False
        self._last_accept = now
        return True

    def set_frame(self, frame):
        with self._lock:
            self._frame      = frame
            self._frame_time = time.monotonic()
            self._accepted  += 1

    def get_frame(self):
        with self._lock:
            return self._frame, self._frame_time

    def mark_sent(self):
        self._sent += 1

    def stats(self):
        return dict(accepted=self._accepted, dropped=self._dropped, sent=self._sent)

    def send_datachannel(self, data: dict):
        if self._channel is None or self._loop is None:
            return
        payload = json.dumps(data, ensure_ascii=False)
        asyncio.run_coroutine_threadsafe(self._do_send(payload), self._loop)

    async def _do_send(self, payload):
        try:
            if self._channel:
                self._channel.send(payload)
        except Exception:
            pass


shared = SharedState()


# ── 비디오 트랙 ───────────────────────────────────────────────────────────────
class AresVideoTrack(VideoStreamTrack):
    """팀원 코드의 정밀 RTP 타임스탬프 로직 그대로 유지"""
    kind = "video"

    def __init__(self):
        super().__init__()
        self._start_time    = None
        self._pts           = 0
        self._frame_interval = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 1.0 / 30
        self._pts_step      = max(1, int(RTP_CLOCK_RATE * self._frame_interval))

    async def _next_timestamp(self):
        loop = asyncio.get_event_loop()
        if self._start_time is None:
            self._start_time = loop.time()
            self._pts = 0
            return self._pts, Fraction(1, RTP_CLOCK_RATE)

        self._pts += self._pts_step
        next_time  = self._start_time + (self._pts / RTP_CLOCK_RATE)
        wait       = next_time - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        return self._pts, Fraction(1, RTP_CLOCK_RATE)

    async def recv(self):
        pts, time_base = await self._next_timestamp()
        frame, _ = shared.get_frame()

        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"ARES {ROBOT_ID} — Waiting...",
                        (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        vf           = VideoFrame.from_ndarray(np.ascontiguousarray(frame), format="rgb24")
        vf.pts       = pts
        vf.time_base = time_base
        shared.mark_sent()
        return vf


# ── ROS2 노드 ─────────────────────────────────────────────────────────────────
_stream_node = None


class AresVisionNode(Node):
    def __init__(self):
        super().__init__(f"ares_vision_{ROBOT_ID.replace('-', '_').lower()}")
        self._bridge    = CvBridge()
        self._cb_group  = ReentrantCallbackGroup()
        self._frame_cnt = 0
        self._last_stat = time.monotonic()
        self._last_snap = shared.stats()

        img_type = CompressedImage if use_compressed() else Image
        img_cb   = self._compressed_cb if use_compressed() else self._raw_cb

        self.create_subscription(
            img_type, IMAGE_TOPIC, img_cb,
            build_image_qos(), callback_group=self._cb_group,
        )
        self.get_logger().info(f"📡 [{ROBOT_ID}] 토픽 구독: {IMAGE_TOPIC}")
        self.get_logger().info(
            f"   QoS: {IMAGE_QOS_RELIABILITY} depth={IMAGE_QOS_DEPTH} | "
            f"FPS≤{TARGET_FPS:g} | max_width={MAX_WIDTH if MAX_WIDTH>0 else '원본'}"
        )

    def _raw_cb(self, msg: "Image"):
        if not shared.should_accept():
            return
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, "passthrough")
            frame = resize_for_stream(frame)
            shared.set_frame(image_to_rgb(frame, msg.encoding))
            self._log(frame)
        except Exception as e:
            self.get_logger().warn(f"raw 변환 오류: {e}")

    def _compressed_cb(self, msg: "CompressedImage"):
        if not shared.should_accept():
            return
        try:
            frame = self._bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
            frame = resize_for_stream(frame)
            shared.set_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            self._log(frame)
        except Exception as e:
            self.get_logger().warn(f"compressed 변환 오류: {e}")

    def _log(self, frame):
        self._frame_cnt += 1
        now = time.monotonic()
        if now - self._last_stat < STATS_INTERVAL:
            return
        snap  = shared.stats()
        elapsed = max(0.001, now - self._last_stat)
        acc_fps = (snap["accepted"] - self._last_snap["accepted"]) / elapsed
        snt_fps = (snap["sent"]     - self._last_snap["sent"])     / elapsed
        drp     =  snap["dropped"]  - self._last_snap["dropped"]
        h, w    = frame.shape[:2]
        self.get_logger().info(
            f"[{ROBOT_ID}] {w}x{h} | acc={acc_fps:.1f}fps snt={snt_fps:.1f}fps drp={drp}"
        )
        self._last_snap = snap
        self._last_stat = now


def start_ros2():
    global _stream_node
    rclpy.init()
    _stream_node = AresVisionNode()
    executor = MultiThreadedExecutor()
    executor.add_node(_stream_node)
    executor.spin()


# ── aiohttp 핸들러 (직접 /offer POST — 시그널링 서버 불필요) ────────────────
pcs = set()

CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


async def handle_options(request):
    return web.Response(status=200, headers=CORS_HEADERS)


async def handle_offer(request):
    params = await request.json()
    offer  = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    config = RTCConfiguration(iceServers=build_ice_servers())
    pc     = RTCPeerConnection(configuration=config)
    pcs.add(pc)

    # 비디오 트랙 추가
    pc.addTrack(AresVideoTrack())

    # DataChannel 수신 (브라우저 → 로봇 메시지용, 현재는 로깅만)
    @pc.on("datachannel")
    def on_datachannel(channel):
        shared._channel = channel
        shared._loop    = asyncio.get_event_loop()
        print(f"[{ROBOT_ID}] DataChannel 열림: {channel.label}")

    @pc.on("connectionstatechange")
    async def on_state():
        state = pc.connectionState
        print(f"[{ROBOT_ID}] 연결 상태: {state}")
        if state in ("failed", "closed"):
            pcs.discard(pc)
            await pc.close()

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}),
        headers=CORS_HEADERS,
    )


async def on_shutdown(app):
    await asyncio.gather(*[pc.close() for pc in pcs])
    pcs.clear()


# ── 진입점 ────────────────────────────────────────────────────────────────────
def main():
    print(f"🚀 ARES WebRTC Vision Server")
    print(f"   Robot:  {ROBOT_ID}")
    print(f"   Port:   {PORT}")
    print(f"   Topic:  {IMAGE_TOPIC} ({'compressed' if use_compressed() else 'raw'})")
    print(f"   FPS:    ≤{TARGET_FPS:g}  MaxWidth: {MAX_WIDTH if MAX_WIDTH > 0 else '원본'}px")
    print(f"   ICE:    {'STUN/TURN' if USE_PUBLIC_ICE else 'LAN only'}\n")

    if ROS2_AVAILABLE:
        t = threading.Thread(target=start_ros2, daemon=True)
        t.start()
        time.sleep(2.0)  # ROS2 노드 초기화 대기
    else:
        print("⚠️  테스트 모드 — 더미 프레임 송출\n")

    app = web.Application()
    app.router.add_post("/offer",    handle_offer)
    app.router.add_options("/offer", handle_options)
    app.on_shutdown.append(on_shutdown)

    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
