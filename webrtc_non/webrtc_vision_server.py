#!/usr/bin/env python3
"""
webrtc_vision_server.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[구독]
  /robot5/survivor/annotated/compressed  → VideoTrack (OAK-D 주석 영상 스트리밍)
  /robot5/survivor/annotated             → raw Image 모드에서 사용
  /yolo_detections  → DataChannel → 브라우저 (bbox 목록)

[DataChannel 수신]
  브라우저 → select → /selected_object 발행
             (브라우저에서 OAK-D 영상 위 MediaPipe 호버 판정 결과)

[실행]
    ./run_oakd_vision.sh robot5
"""

import asyncio
import json
import time
import threading
import requests
import numpy as np
import cv2
from fractions import Fraction

from av import VideoFrame
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
    from std_msgs.msg import String
    from cv_bridge import CvBridge
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("⚠️  ROS2 없음 — 테스트 모드")

try:
    from gesture_robot_interfaces.msg import SelectedObject
    SELECTED_OBJECT_AVAILABLE = True
except ImportError:
    SelectedObject = None
    SELECTED_OBJECT_AVAILABLE = False
    print("⚠️  SelectedObject 인터페이스 없음 — 영상 스트리밍만 활성화")

import os
SIGNALING_URL = os.getenv('SIGNALING_URL', 'http://127.0.0.1:5000')
ROOM          = os.getenv('WEBRTC_ROOM', 'ares-vision-robot5')
FPS           = 30
IMAGE_TOPIC   = os.getenv('WEBRTC_IMAGE_TOPIC', '/robot5/survivor/annotated/compressed')
IMAGE_TYPE    = os.getenv('WEBRTC_IMAGE_TYPE', '').strip().lower()
DETECTIONS_TOPIC = os.getenv('WEBRTC_DETECTIONS_TOPIC', '/yolo_detections')
USE_PUBLIC_ICE = os.getenv('WEBRTC_USE_PUBLIC_ICE', '').lower() in ('1', 'true', 'yes')
CONNECT_TIMEOUT_SEC = int(os.getenv('WEBRTC_CONNECT_TIMEOUT_SEC', '10'))
IMAGE_QOS_DEPTH = int(os.getenv('WEBRTC_IMAGE_QOS_DEPTH', '1'))
IMAGE_QOS_RELIABILITY = os.getenv('WEBRTC_IMAGE_QOS_RELIABILITY', 'best_effort').lower()
MAX_WIDTH = int(os.getenv('WEBRTC_MAX_WIDTH', '480'))
TARGET_FPS = float(os.getenv('WEBRTC_TARGET_FPS', '15'))
ANSWER_DELAY_SEC = min(float(os.getenv('WEBRTC_ANSWER_DELAY_SEC', '0')), 0.1)
STATS_INTERVAL_SEC = float(os.getenv('WEBRTC_STATS_INTERVAL_SEC', '2.0'))
RTP_CLOCK_RATE = 90000


def ros_name(value):
    return ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in value)


NODE_NAME = os.getenv('WEBRTC_NODE_NAME', f'webrtc_vision_server_{ros_name(ROOM)}')


def build_ice_servers():
    if not USE_PUBLIC_ICE:
        return []

    return [
        RTCIceServer(urls='stun:stun.l.google.com:19302'),
        RTCIceServer(urls='turn:openrelay.metered.ca:80',
                     username='openrelayproject', credential='openrelayproject'),
        RTCIceServer(urls='turn:openrelay.metered.ca:443',
                     username='openrelayproject', credential='openrelayproject'),
    ]


def build_image_qos():
    reliability = (
        ReliabilityPolicy.RELIABLE
        if IMAGE_QOS_RELIABILITY == 'reliable'
        else ReliabilityPolicy.BEST_EFFORT
    )

    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=IMAGE_QOS_DEPTH,
        reliability=reliability,
        durability=DurabilityPolicy.VOLATILE,
    )


def use_compressed_image():
    return IMAGE_TYPE == 'compressed' or IMAGE_TOPIC.endswith('/compressed')


def image_to_rgb(frame, encoding):
    if encoding in ('rgb8', '8UC3'):
        return frame
    if encoding == 'bgr8':
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if encoding == 'mono8':
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    if encoding == 'rgba8':
        return cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
    if encoding == 'bgra8':
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

    if len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def resize_for_stream(frame):
    if MAX_WIDTH <= 0 or frame.shape[1] <= MAX_WIDTH:
        return frame

    height, width = frame.shape[:2]
    scale = MAX_WIDTH / float(width)
    return cv2.resize(frame, (MAX_WIDTH, int(height * scale)), interpolation=cv2.INTER_AREA)


def is_aioice_shutdown_noise(context):
    message = str(context.get('message', ''))
    exception = context.get('exception')
    handle = str(context.get('handle', ''))

    if 'Transaction.__retry' not in message and 'Transaction.__retry' not in handle:
        return False

    if not isinstance(exception, AttributeError):
        return False

    text = str(exception)
    return 'sendto' in text or 'call_exception_handler' in text


def handle_loop_exception(loop, context):
    if is_aioice_shutdown_noise(context):
        return

    loop.default_exception_handler(context)


# ══════════════════════════════════════════════════════════════════════════════
# 공유 상태
# ══════════════════════════════════════════════════════════════════════════════

class SharedState:
    def __init__(self):
        self._frame      = None
        self._frame_time = 0.0
        self._frame_lock = threading.Lock()
        self._channel    = None
        self._loop       = None
        self._stats_lock = threading.Lock()
        self._accepted_frames = 0
        self._dropped_frames = 0
        self._sent_frames = 0
        self._last_age_ms = 0.0

    def set_frame(self, frame):
        with self._frame_lock:
            self._frame = frame
            self._frame_time = time.monotonic()

    def get_frame(self):
        with self._frame_lock:
            return self._frame, self._frame_time

    def mark_accepted(self):
        with self._stats_lock:
            self._accepted_frames += 1

    def mark_dropped(self):
        with self._stats_lock:
            self._dropped_frames += 1

    def mark_sent(self, age_ms):
        with self._stats_lock:
            self._sent_frames += 1
            self._last_age_ms = age_ms

    def snapshot_stats(self):
        with self._stats_lock:
            return {
                'accepted': self._accepted_frames,
                'dropped': self._dropped_frames,
                'sent': self._sent_frames,
                'age_ms': self._last_age_ms,
            }

    def send(self, data: dict):
        if self._channel is None or self._loop is None:
            return
        payload = json.dumps(data, ensure_ascii=False)
        asyncio.run_coroutine_threadsafe(self._do_send(payload), self._loop)

    async def _do_send(self, payload: str):
        try:
            if self._channel:
                self._channel.send(payload)
        except Exception:
            pass  # 전송 실패 무시


shared = SharedState()


# ══════════════════════════════════════════════════════════════════════════════
# VideoTrack
# ══════════════════════════════════════════════════════════════════════════════

class AnnotatedFrameTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._start_time = None
        self._pts = 0
        self._frame_interval = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 1.0 / FPS
        self._pts_step = max(1, int(RTP_CLOCK_RATE * self._frame_interval))

    async def _next_timestamp(self):
        loop = asyncio.get_event_loop()
        if self._start_time is None:
            self._start_time = loop.time()
            self._pts = 0
            return self._pts, Fraction(1, RTP_CLOCK_RATE)

        self._pts += self._pts_step
        next_time = self._start_time + (self._pts / RTP_CLOCK_RATE)
        wait = next_time - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        return self._pts, Fraction(1, RTP_CLOCK_RATE)

    async def recv(self):
        pts, time_base = await self._next_timestamp()
        frame, frame_time = shared.get_frame()
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            age_ms = 0.0
        else:
            age_ms = max(0.0, (time.monotonic() - frame_time) * 1000.0)

        video_frame           = VideoFrame.from_ndarray(np.ascontiguousarray(frame), format="rgb24")
        video_frame.pts       = pts
        video_frame.time_base = time_base
        shared.mark_sent(age_ms)
        return video_frame


# ══════════════════════════════════════════════════════════════════════════════
# ROS2 노드
# ══════════════════════════════════════════════════════════════════════════════

class VisionStreamNode(Node):

    def __init__(self):
        super().__init__(NODE_NAME)

        self._bridge   = CvBridge()
        self._cb_group = ReentrantCallbackGroup()
        self._frame_count = 0
        self._last_accept_time = 0.0
        self._min_frame_interval = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 0.0
        self._last_stats_time = time.monotonic()
        self._last_stats = shared.snapshot_stats()

        # 퍼블리셔 — 브라우저 호버 선택 결과 → /selected_object
        self._pub_selected = None
        if SELECTED_OBJECT_AVAILABLE:
            self._pub_selected = self.create_publisher(
                SelectedObject, '/selected_object', 10)

        # 구독
        image_msg_type = CompressedImage if use_compressed_image() else Image
        image_callback = self._compressed_image_cb if use_compressed_image() else self._image_cb
        self.create_subscription(
            image_msg_type, IMAGE_TOPIC, image_callback, build_image_qos(),
            callback_group=self._cb_group,
        )
        self.create_subscription(
            String, DETECTIONS_TOPIC, self._yolo_detections_cb, 10,
            callback_group=self._cb_group)

        self.get_logger().info('VisionStreamNode ready')
        self.get_logger().info(
            f"  {IMAGE_TOPIC} ({'compressed' if use_compressed_image() else 'raw'}) → VideoTrack")
        self.get_logger().info(f'  {DETECTIONS_TOPIC} → DataChannel → 브라우저')
        if SELECTED_OBJECT_AVAILABLE:
            self.get_logger().info('  브라우저 호버 선택 → DataChannel → /selected_object')
        else:
            self.get_logger().warn('  SelectedObject 없음 → 브라우저 선택 발행 비활성화')

    def _image_cb(self, msg: Image):
        try:
            if not self._should_accept_frame():
                return

            frame = self._bridge.imgmsg_to_cv2(msg, 'passthrough')
            frame = resize_for_stream(frame)
            self._store_frame(image_to_rgb(frame, msg.encoding))
        except Exception as e:
            self.get_logger().warn(f'{IMAGE_TOPIC} 변환 오류: {e}')

    def _compressed_image_cb(self, msg: CompressedImage):
        try:
            if not self._should_accept_frame():
                return

            frame = self._bridge.compressed_imgmsg_to_cv2(msg, 'bgr8')
            frame = resize_for_stream(frame)
            self._store_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        except Exception as e:
            self.get_logger().warn(f'{IMAGE_TOPIC} compressed 변환 오류: {e}')

    def _should_accept_frame(self):
        now = time.monotonic()
        if self._min_frame_interval > 0 and now - self._last_accept_time < self._min_frame_interval:
            shared.mark_dropped()
            return False

        self._last_accept_time = now
        return True

    def _store_frame(self, frame):
        shared.set_frame(frame)
        shared.mark_accepted()
        self._frame_count += 1
        if self._frame_count == 1 or self._frame_count % 300 == 0:
            height, width = frame.shape[:2]
            self.get_logger().info(
                f'{IMAGE_TOPIC} frame #{self._frame_count}: {width}x{height}')
        self._log_stream_stats()

    def _log_stream_stats(self):
        now = time.monotonic()
        if now - self._last_stats_time < STATS_INTERVAL_SEC:
            return

        stats = shared.snapshot_stats()
        elapsed = max(0.001, now - self._last_stats_time)
        accepted_fps = (stats['accepted'] - self._last_stats['accepted']) / elapsed
        sent_fps = (stats['sent'] - self._last_stats['sent']) / elapsed
        dropped_delta = stats['dropped'] - self._last_stats['dropped']
        self.get_logger().info(
            f"stream stats: age={stats['age_ms']:.0f}ms "
            f"accepted={accepted_fps:.1f}fps sent={sent_fps:.1f}fps "
            f"dropped={dropped_delta}")
        self._last_stats = stats
        self._last_stats_time = now

    def _yolo_detections_cb(self, msg: String):
        try:
            data = json.loads(msg.data)
            shared.send({
                'type'      : 'yolo_detections',
                'detections': data.get('detections', []),
                'timestamp' : data.get('timestamp', ''),
            })
        except Exception as e:
            self.get_logger().warn(f'yolo_detections 파싱 오류: {e}')

    def on_browser_message(self, message: str):
        """
        브라우저 DataChannel 메시지 처리
        형식: {"type": "select", "label": "apple", "box": [...], "confidence": 0.9}
        """
        try:
            data = json.loads(message)
            if data.get('type') != 'select':
                return

            label = data.get('label', '')
            box   = data.get('box', [])
            conf  = float(data.get('confidence', 0.0))

            if not label:
                return

            if self._pub_selected is None or SelectedObject is None:
                self.get_logger().warn('[BROWSER SELECT] SelectedObject 인터페이스 없음 — 발행 생략')
                return

            msg              = SelectedObject()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.label        = label
            msg.confidence   = conf
            msg.box          = [int(v) for v in box]
            self._pub_selected.publish(msg)

            self.get_logger().info(
                f'[BROWSER SELECT] {label} conf={conf:.3f}')

        except Exception as e:
            self.get_logger().warn(f'DataChannel 메시지 파싱 오류: {e}')


_stream_node: "VisionStreamNode | None" = None


def start_ros2():
    global _stream_node
    rclpy.init()
    _stream_node = VisionStreamNode()
    executor = MultiThreadedExecutor()
    executor.add_node(_stream_node)
    executor.spin()


# ══════════════════════════════════════════════════════════════════════════════
# WebRTC 서버
# ══════════════════════════════════════════════════════════════════════════════

async def run_webrtc():
    config = RTCConfiguration(iceServers=build_ice_servers())
    pc     = RTCPeerConnection(configuration=config)
    track  = AnnotatedFrameTrack()
    pc.addTrack(track)

    shared._loop = asyncio.get_event_loop()

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(f"\n✅ DataChannel 수신: {channel.label}")
        shared._channel = channel
        shared._loop    = asyncio.get_event_loop()

        @channel.on("open")
        def on_open():
            print("✅ DataChannel 열림")

        @channel.on("message")
        def on_msg(message):
            if _stream_node:
                _stream_node.on_browser_message(message)

        @channel.on("close")
        def on_close():
            print("\n❌ DataChannel 닫힘")
            shared._channel = None

    @pc.on("connectionstatechange")
    async def on_state():
        print(f"\n🔗 연결 상태: {pc.connectionState}")

    count = 0
    while True:
        try:
            resp = requests.get(f"{SIGNALING_URL}/offer/{ROOM}", timeout=5)
            if resp.status_code == 200:
                offer_data = resp.json()
                print()
                break
        except Exception:
            pass
        count += 1
        print(f"\r⏳ [vision] offer 대기 중... {count}s", end='', flush=True)
        await asyncio.sleep(1.0)

    print("✅ Offer 수신!")
    await pc.setRemoteDescription(RTCSessionDescription(
        sdp=offer_data['sdp'], type=offer_data['type']))

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    if ANSWER_DELAY_SEC > 0:
        await asyncio.sleep(ANSWER_DELAY_SEC)

    resp = requests.post(f"{SIGNALING_URL}/answer", json={
        'room': ROOM,
        'sdp' : pc.localDescription.sdp,
        'type': pc.localDescription.type,
    }, timeout=5)
    resp.raise_for_status()
    print("✅ Answer 전송 → 연결 수립!")
    print("📡 스트리밍 중...\n")

    try:
        wait_sec = 0
        while True:
            await asyncio.sleep(1.0)
            wait_sec += 1
            if pc.connectionState == 'connected':
                wait_sec = 0
            if pc.connectionState in ('failed', 'closed'):
                break
            if pc.connectionState in ('new', 'connecting') and wait_sec >= CONNECT_TIMEOUT_SEC:
                print(f"⏱️ 연결 타임아웃({CONNECT_TIMEOUT_SEC}s) → 새 offer 대기")
                break
    except asyncio.CancelledError:
        pass
    finally:
        await pc.close()


async def main():
    asyncio.get_running_loop().set_exception_handler(handle_loop_exception)

    print("🤖 ARES WebRTC Vision 스트리밍 서버")
    print(f"   Room: {ROOM}\n")
    print(f"   ROS node: {NODE_NAME}")
    print(f"   Image topic: {IMAGE_TOPIC}")
    print(f"   Image type: {'compressed' if use_compressed_image() else 'raw'}")
    print(f"   Detection topic: {DETECTIONS_TOPIC}\n")
    print(f"   Signaling: {SIGNALING_URL}")
    print(f"   Public ICE: {'on' if USE_PUBLIC_ICE else 'off'}\n")
    print(f"   Target FPS: {TARGET_FPS:g}")
    print(f"   Max width: {MAX_WIDTH if MAX_WIDTH > 0 else 'source'}")
    print(f"   Image QoS: {IMAGE_QOS_RELIABILITY}, depth={IMAGE_QOS_DEPTH}\n")

    if ROS2_AVAILABLE:
        t = threading.Thread(target=start_ros2, daemon=True)
        t.start()
        print("✅ ROS2 스트림 노드 시작\n")
        await asyncio.sleep(2.0)
    else:
        print("⚠️  테스트 모드\n")

    while True:
        try:
            await run_webrtc()
        except KeyboardInterrupt:
            print("\n👋 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류: {e} — 3초 후 재연결...")
            await asyncio.sleep(3)


if __name__ == '__main__':
    asyncio.run(main())
