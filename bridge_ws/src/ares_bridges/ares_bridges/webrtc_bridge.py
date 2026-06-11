#!/usr/bin/env python3
import numpy as np
import asyncio, json, cv2, sys, threading
from fractions import Fraction
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from nav_msgs.msg import Path
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import Image, CompressedImage, BatteryState

from cv_bridge import CvBridge
from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from av import VideoFrame

latest_frame = None
frame_lock = threading.Lock()
pcs = set()
active_datachannels = set()
_ROBOT_ID = "robot1"
main_loop = None


class RosImageTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self):
        super().__init__()
        self._start_time = None
        self._pts = 0
        self._pts_step = max(1, int(90000 * (1.0 / 15.0)))

    async def recv(self):
        global latest_frame
        loop = asyncio.get_event_loop()
        if self._start_time is None:
            self._start_time = loop.time()

        self._pts += self._pts_step
        await asyncio.sleep(
            max(0, (self._start_time + (self._pts / 90000)) - loop.time())
        )

        with frame_lock:
            img = (
                latest_frame
                if latest_frame is not None
                else np.zeros((480, 640, 3), dtype=np.uint8)
            )

        frame = VideoFrame.from_ndarray(
            cv2.cvtColor(img, cv2.COLOR_BGR2RGB), format="rgb24"
        )
        frame.pts, frame.time_base = self._pts, Fraction(1, 90000)
        return frame


class WebrtcBridge(Node):
    def __init__(self):
        super().__init__("webrtc_bridge")
        self.bridge = CvBridge()
        self.declare_parameter("port", 8002)
        self.declare_parameter("topic", "/robot5/survivor/annotated")
        self.declare_parameter("robot", "robot5")

        self.port = self.get_parameter("port").value
        self.topic_name = self.get_parameter("topic").value
        self.robot_id = self.get_parameter("robot").value

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.create_subscription(
            Image, self.topic_name, self.image_callback, qos
        )
        self.create_subscription(
            BatteryState, f"/{self.robot_id}/battery_state", self.battery_callback, 10
        )

        self.create_subscription(
            Path, f"/{self.robot_id}/coverage/path", self.path_callback, 10
        )

        self.create_subscription(
            OccupancyGrid,
            f"/{self.robot_id}/camera_coverage",
            self.coverage_callback,
            10,
        )

        self.get_logger().info(
            f"👀 [WebRTC 브릿지] 가동2! 포트: {self.port}, 토픽: {self.topic_name}"
        )
    
    def coverage_callback(self, msg: OccupancyGrid):
        if not active_datachannels:
            return

        width = msg.info.width
        height = msg.info.height
        res = msg.info.resolution
        origin_x = msg.info.origin.position.x
        origin_y = msg.info.origin.position.y

        data = np.array(msg.data, dtype=np.int8).reshape((height, width))

        # 💡 값이 100(카메라가 훑고 지나간 영역)인 인덱스만 싹 골라내기
        y_indices, x_indices = np.where(data == 100)

        # 데이터 다이어트를 위해 최대 200개까지만 샘플링하여 대역폭 보호
        step = max(1, len(x_indices) // 200)
        sampled_x = x_indices[::step]
        sampled_y = y_indices[::step]

        # 인덱스 좌표 -> 실제 ROS2 평면 미터(m) 좌표로 역연산 변환
        coverage_points = []
        for sx, sy in zip(sampled_x, sampled_y):
            real_x = origin_x + (sx * res)
            real_y = origin_y + (sy * res)
            coverage_points.append({"x": float(real_x), "y": float(real_y)})

        payload = json.dumps({"type": "camera_coverage", "points": coverage_points})

        global main_loop
        if main_loop and not main_loop.is_closed():
            main_loop.call_soon_threadsafe(
                lambda: [
                    c.send(payload)
                    for c in list(active_datachannels)
                    if c.readyState == "open"
                ]
            )
            
    def battery_callback(self, msg):
        if not active_datachannels:
            return
        payload = json.dumps(
            {
                "type": "battery",
                "value": round(msg.percentage * 100, 1)
                if msg.percentage <= 1.0
                else round(msg.percentage, 1),
            }
        )

        global main_loop
        if main_loop and not main_loop.is_closed():
            main_loop.call_soon_threadsafe(
                lambda: [
                    c.send(payload)
                    for c in list(active_datachannels)
                    if c.readyState == "open"
                ]
            )

    def path_callback(self, msg):
        if not active_datachannels:
            return

        # 💡 네트워크 오버헤드를 줄이기 위해 전체 경로 좌표 중 5개당 1개씩만 샘플링(Downsampling)하여 압축
        sampled_poses = msg.poses[::5]

        payload = json.dumps(
            {
                "type": "path",
                "poses": [
                    {"x": float(p.pose.position.x), "y": float(p.pose.position.y)}
                    for p in sampled_poses
                ],
            }
        )

        global main_loop
        if main_loop and not main_loop.is_closed():
            main_loop.call_soon_threadsafe(
                lambda: [
                    c.send(payload)
                    for c in list(active_datachannels)
                    if c.readyState == "open"
                ]
            )

    def image_callback(self, msg):
        global latest_frame
        try:
            with frame_lock:
                latest_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
                # latest_frame = self.bridge.compressed_imgmsg_to_cv2(
                #     msg, desired_encoding="bgr8"
                # )
        except Exception:
            pass


async def handle_offer(request):
    params = await request.json()
    pc = RTCPeerConnection()
    pcs.add(pc)
    pc.addTrack(RosImageTrack())

    @pc.on("datachannel")
    def on_datachannel(channel):
        active_datachannels.add(channel)

        @channel.on("close")
        def on_close():
            active_datachannels.discard(channel)

    @pc.on("connectionstatechange")
    async def on_state():
        if pc.connectionState in ("failed", "closed"):
            pcs.discard(pc)
            await pc.close()

    await pc.setRemoteDescription(
        RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    )
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # [CORS 설정] Access-Control-Allow-Headers에 Content-Type을 명시적으로 허용해 줍니다.
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        },
    )

async def handle_options(request):
    return web.Response(
        status=200, 
        headers={
            "Access-Control-Allow-Origin": "*", 
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Allow-Methods": "POST, OPTIONS"
        }
    )

def main():
    global main_loop, _ROBOT_ID
    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)

    rclpy.init(args=sys.argv)
    node = WebrtcBridge()
    _ROBOT_ID = node.robot_id

    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    app = web.Application()
    app.router.add_post("/offer", handle_offer)
    app.router.add_options("/offer", handle_options)

    try:
        web.run_app(app, host="0.0.0.0", port=node.port, print=None)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
