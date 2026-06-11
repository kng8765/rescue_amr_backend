#!/usr/bin/env python3
import numpy as np
import asyncio, json, cv2, sys, threading, math
from fractions import Fraction
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from nav_msgs.msg import Path
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import Image, CompressedImage, BatteryState
from geometry_msgs.msg import PoseStamped

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
        # map 프레임 로봇 pose 토픽 (ROS단에서 map 좌표계로 발행 → /tf 불필요).
        # 비우면 "/{robot}/pose" 사용. 타입은 geometry_msgs/PoseStamped 가정.
        self.declare_parameter("pose_topic", "")
        # 영상 송출 최대 가로폭(px). 0이면 원본. 현장 대역폭 보호용.
        self.declare_parameter("max_width", 480)

        self.port = self.get_parameter("port").value
        self.topic_name = self.get_parameter("topic").value
        self.robot_id = self.get_parameter("robot").value
        self.pose_topic = self.get_parameter("pose_topic").value or f"/{self.robot_id}/pose"
        self.max_width = int(self.get_parameter("max_width").value)

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
        # 로봇 현재 위치 (map 프레임 PoseStamped) → DataChannel pose
        self.create_subscription(
            PoseStamped, self.pose_topic, self.pose_callback, 10
        )
        # SLAM 지도 (탐색 중 실시간으로 자라는 맵) → DataChannel map (1초 throttle)
        self.create_subscription(
            OccupancyGrid, f"/{self.robot_id}/map", self.map_callback, 10
        )
        self._last_map_ns = 0

        self.get_logger().info(
            f"👀 [WebRTC 브릿지] 가동! port:{self.port} 영상:{self.topic_name} "
            f"pose:{self.pose_topic} max_width:{self.max_width or '원본'}"
        )

    # ── DataChannel 공통 송신 헬퍼 ──────────────────────────────────────────
    def _broadcast(self, payload: str):
        """열린 모든 DataChannel로 페이로드 전송 (메인 asyncio 루프 위에서 실행)."""
        global main_loop
        if not active_datachannels or main_loop is None or main_loop.is_closed():
            return
        main_loop.call_soon_threadsafe(
            lambda: [
                c.send(payload)
                for c in list(active_datachannels)
                if c.readyState == "open"
            ]
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

        self._broadcast(json.dumps({"type": "camera_coverage", "points": coverage_points}))

    def battery_callback(self, msg):
        if not active_datachannels:
            return
        self._broadcast(json.dumps(
            {
                "type": "battery",
                "value": round(msg.percentage * 100, 1)
                if msg.percentage <= 1.0
                else round(msg.percentage, 1),
            }
        ))

    def path_callback(self, msg):
        if not active_datachannels:
            return

        # 💡 네트워크 오버헤드를 줄이기 위해 전체 경로 좌표 중 5개당 1개씩만 샘플링(Downsampling)하여 압축
        sampled_poses = msg.poses[::5]

        self._broadcast(json.dumps(
            {
                "type": "path",
                "poses": [
                    {"x": float(p.pose.position.x), "y": float(p.pose.position.y)}
                    for p in sampled_poses
                ],
            }
        ))

    def pose_callback(self, msg: PoseStamped):
        # map 프레임 로봇 현재 위치 + yaw(쿼터니언 → 평면 각도)
        q = msg.pose.orientation
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )
        self._broadcast(json.dumps({
            "type": "pose",
            "x": float(msg.pose.position.x),
            "y": float(msg.pose.position.y),
            "yaw": float(yaw),
        }))

    def map_callback(self, msg: OccupancyGrid):
        # SLAM이 실시간 작성 중인 점유격자 → 점유(벽) 셀을 월드 좌표 점으로 송신.
        # 탐색 중 계속 갱신되므로 1초 throttle + 최대 ~2500점으로 대역폭 보호.
        if not active_datachannels:
            return
        now_ns = self.get_clock().now().nanoseconds
        if now_ns - self._last_map_ns < 1_000_000_000:
            return
        self._last_map_ns = now_ns

        info = msg.info
        data = np.array(msg.data, dtype=np.int8).reshape((info.height, info.width))
        ys, xs = np.where(data >= 65)  # 점유(벽) 셀만
        step = max(1, len(xs) // 800)  # 최대 ~800점 (렌더 부하/끊김 완화)
        ox, oy, res = info.origin.position.x, info.origin.position.y, info.resolution
        walls = [
            {"x": float(ox + x * res), "y": float(oy + y * res)}
            for x, y in zip(xs[::step], ys[::step])
        ]
        self._broadcast(json.dumps({
            "type": "map",
            "resolution": float(res),
            "walls": walls,
        }))

    def image_callback(self, msg):
        global latest_frame
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            # 현장 대역폭 보호: 최대 가로폭 초과 시 비율 유지 축소
            if self.max_width and frame.shape[1] > self.max_width:
                h, w = frame.shape[:2]
                scale = self.max_width / float(w)
                frame = cv2.resize(
                    frame, (self.max_width, int(h * scale)), interpolation=cv2.INTER_AREA
                )
            with frame_lock:
                latest_frame = frame
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

async def handle_health(request):
    # 프론트가 연결 시도 전 브릿지 생존 확인용 (재시도 폭주 방지)
    return web.Response(
        content_type="application/json",
        text=json.dumps({"status": "ok", "robot": _ROBOT_ID}),
        headers={"Access-Control-Allow-Origin": "*"},
    )

async def _on_startup(app):
    # aiohttp가 실제로 돌리는 이벤트 루프를 캡처해야 ROS 콜백→DataChannel 전송이 동작.
    # (직접 new_event_loop를 잡으면 web.run_app이 만든 루프와 달라 call_soon_threadsafe가 무용지물)
    global main_loop
    main_loop = asyncio.get_running_loop()


def main():
    global _ROBOT_ID
    rclpy.init(args=sys.argv)
    node = WebrtcBridge()
    _ROBOT_ID = node.robot_id

    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    app = web.Application()
    app.router.add_post("/offer", handle_offer)
    app.router.add_options("/offer", handle_options)
    app.router.add_get("/health", handle_health)
    app.on_startup.append(_on_startup)

    try:
        web.run_app(app, host="0.0.0.0", port=node.port, print=None)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
