#!/usr/bin/env python3
"""Stream a ROS2 OccupancyGrid map and robot pose to the dashboard."""

import asyncio
import base64
import json
import math
import os
import threading
import time

import cv2
import numpy as np
import requests
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

try:
    import rclpy
    from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
    from nav_msgs.msg import OccupancyGrid
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from rclpy.time import Time
    from tf2_ros import Buffer, TransformException, TransformListener
    from visualization_msgs.msg import MarkerArray

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("ROS2 packages unavailable; map streaming is disabled.")

try:
    from map_msgs.msg import OccupancyGridUpdate
    MAP_UPDATES_AVAILABLE = True
except ImportError:
    OccupancyGridUpdate = None
    MAP_UPDATES_AVAILABLE = False


SIGNALING_URL = os.getenv("SIGNALING_URL", "http://127.0.0.1:5000").rstrip("/")
ROBOT_NAME = os.getenv("WEBRTC_ROBOT_NAME", "robot1").strip("/")
ROOM = os.getenv("WEBRTC_MAP_ROOM", f"ares-map-{ROBOT_NAME or 'robot'}")
MAP_TOPIC = os.getenv("WEBRTC_MAP_TOPIC", f"/{ROBOT_NAME}/map")
NODE_NAME = os.getenv("WEBRTC_MAP_NODE_NAME", f"webrtc_map_{ROBOT_NAME or 'robot'}")
MAP_UPDATE_TOPIC = os.getenv("WEBRTC_MAP_UPDATE_TOPIC", f"/{ROBOT_NAME}/map_updates")
CAMERA_COVERAGE_UPDATE_TOPIC = os.getenv(
    "WEBRTC_CAMERA_COVERAGE_UPDATE_TOPIC",
    f"/{ROBOT_NAME}/camera_coverage_updates",
)
POSE_TOPIC = os.getenv("WEBRTC_POSE_TOPIC", f"/{ROBOT_NAME}/pose")
POSE_TOPIC_TYPE = os.getenv("WEBRTC_POSE_TOPIC_TYPE", "pose_stamped").strip().lower()
COVERAGE_MARKERS_TOPIC = os.getenv("WEBRTC_COVERAGE_MARKERS_TOPIC", f"/{ROBOT_NAME}/coverage/markers")
SURVIVOR_MARKERS_TOPIC = os.getenv("WEBRTC_SURVIVOR_MARKERS_TOPIC", f"/{ROBOT_NAME}/survivor/markers")
DEFAULT_LAYER_TOPICS = ",".join([
    f"global_costmap=/{ROBOT_NAME}/global_costmap/costmap",
    f"local_costmap=/{ROBOT_NAME}/local_costmap/costmap",
    f"camera_coverage=/{ROBOT_NAME}/camera_coverage",
])
LAYER_TOPICS = os.getenv("WEBRTC_MAP_LAYER_TOPICS", DEFAULT_LAYER_TOPICS)
DEFAULT_UPDATE_TOPICS = ",".join([
    f"map={MAP_UPDATE_TOPIC}",
    f"camera_coverage={CAMERA_COVERAGE_UPDATE_TOPIC}",
])
UPDATE_TOPICS = os.getenv("WEBRTC_MAP_UPDATE_TOPICS", DEFAULT_UPDATE_TOPICS)
DEFAULT_MARKER_TOPICS = ",".join([
    f"coverage_markers={COVERAGE_MARKERS_TOPIC}",
    f"survivor_markers={SURVIVOR_MARKERS_TOPIC}",
])
MARKER_TOPICS = os.getenv("WEBRTC_MARKER_TOPICS", DEFAULT_MARKER_TOPICS)
MAP_FRAME = os.getenv("WEBRTC_MAP_FRAME", "map").strip("/")
POSE_HZ = float(os.getenv("WEBRTC_POSE_HZ", "5"))
QOS_DEPTH = int(os.getenv("WEBRTC_MAP_QOS_DEPTH", "1"))
QOS_RELIABILITY = os.getenv("WEBRTC_MAP_QOS_RELIABILITY", "reliable").strip().lower()
QOS_DURABILITY = os.getenv("WEBRTC_MAP_QOS_DURABILITY", "transient_local").strip().lower()
USE_PUBLIC_ICE = os.getenv("WEBRTC_USE_PUBLIC_ICE", "").lower() in ("1", "true", "yes")
CONNECT_TIMEOUT_SEC = int(os.getenv("WEBRTC_MAP_CONNECT_TIMEOUT_SEC", "10"))
MAX_BUFFERED_BYTES = int(os.getenv("WEBRTC_MAP_MAX_BUFFERED_BYTES", str(4 * 1024 * 1024)))
MAP_PUBLISH_HZ = float(os.getenv("WEBRTC_MAP_PUBLISH_HZ", "2"))
SEND_GRID_PAYLOAD = os.getenv("WEBRTC_MAP_SEND_GRID", "0").lower() in ("1", "true", "yes")


def log(message):
    print(message, flush=True)


def build_ice_servers():
    if not USE_PUBLIC_ICE:
        return []
    return [
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(urls="turn:openrelay.metered.ca:80", username="openrelayproject", credential="openrelayproject"),
        RTCIceServer(urls="turn:openrelay.metered.ca:443", username="openrelayproject", credential="openrelayproject"),
    ]


def build_map_qos():
    reliability = ReliabilityPolicy.RELIABLE if QOS_RELIABILITY == "reliable" else ReliabilityPolicy.BEST_EFFORT
    durability = DurabilityPolicy.TRANSIENT_LOCAL if QOS_DURABILITY == "transient_local" else DurabilityPolicy.VOLATILE
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=QOS_DEPTH,
        reliability=reliability,
        durability=durability,
    )


def yaw_from_quaternion(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def stamp_to_float(stamp):
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9


def rle(values):
    encoded = []
    last = None
    count = 0
    for raw in values:
        value = int(raw)
        if value == last and count < 65535:
            count += 1
            continue
        if last is not None:
            encoded.extend([last, count])
        last = value
        count = 1
    if last is not None:
        encoded.extend([last, count])
    return encoded


def occupancy_to_png_data_url(values, width, height, layer="map"):
    grid = np.asarray(values, dtype=np.int16).reshape((height, width))
    image = np.zeros((height, width, 4), dtype=np.uint8)

    unknown = grid < 0
    occupied = grid >= 65
    free = ~(unknown | occupied)

    if layer == "map":
        image[unknown] = [92, 105, 106, 190]
        image[free] = [245, 245, 245, 245]
        image[occupied] = [38, 47, 61, 255]
    elif layer == "global_costmap":
        image[occupied] = [37, 99, 235, 130]
        image[free] = [37, 99, 235, 18]
    elif layer == "local_costmap":
        image[occupied] = [239, 68, 68, 155]
        image[free] = [239, 68, 68, 18]
    elif layer == "camera_coverage":
        image[grid >= 1] = [34, 197, 94, 95]
    else:
        image[occupied] = [15, 23, 42, 140]
        image[free] = [15, 23, 42, 18]
    image = np.flipud(image)

    ok, png = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("failed to encode occupancy grid as PNG")
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def frame_candidates():
    configured = os.getenv("WEBRTC_ROBOT_FRAMES", "").strip()
    if configured:
        return [frame.strip().strip("/") for frame in configured.split(",") if frame.strip()]

    frames = []
    if ROBOT_NAME:
        frames.extend([f"{ROBOT_NAME}/base_link", f"{ROBOT_NAME}/base_footprint"])
    frames.extend(["base_link", "base_footprint"])
    return frames


def parse_named_topics(value):
    topics = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            layer, topic = item.split("=", 1)
        else:
            topic = item
            layer = topic.strip("/").replace("/", "_")
        layer = layer.strip()
        topic = topic.strip()
        if layer and topic:
            topics.append((layer, topic))
    return topics


def parse_layer_topics():
    return parse_named_topics(LAYER_TOPICS)


def parse_update_topics():
    return parse_named_topics(UPDATE_TOPICS)


def parse_marker_topics():
    return parse_named_topics(MARKER_TOPICS)


class SharedChannel:
    def __init__(self):
        self.channel = None
        self.loop = None
        self.lock = threading.Lock()

    def attach(self, channel, loop):
        with self.lock:
            self.channel = channel
            self.loop = loop

    def detach(self, channel):
        with self.lock:
            if self.channel is channel:
                self.channel = None

    def send(self, payload):
        with self.lock:
            channel = self.channel
            loop = self.loop
        if not channel or not loop or channel.readyState != "open":
            return False
        if getattr(channel, "bufferedAmount", 0) > MAX_BUFFERED_BYTES:
            return False
        asyncio.run_coroutine_threadsafe(self._send(channel, payload), loop)
        return True

    async def _send(self, channel, payload):
        try:
            if channel.readyState == "open":
                channel.send(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        except Exception:
            pass


shared = SharedChannel()
_map_node = None


class MapStreamNode(Node):
    def __init__(self):
        super().__init__(NODE_NAME)
        self.group = ReentrantCallbackGroup()
        self.tf_buffer = Buffer()
        tf_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        tf_static_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.tf_listener = TransformListener(
            self.tf_buffer,
            self,
            qos=tf_qos,
            static_qos=tf_static_qos,
        )
        self.frames = frame_candidates()
        self.cached_payloads = []
        self.frame_counts = {}
        self.last_emit_times = {}
        self.last_pose_frame = ""
        self.layer_maps = {}
        self._create_grid_subscriptions("map", MAP_TOPIC)
        for layer, topic in parse_layer_topics():
            self._create_grid_subscriptions(layer, topic)
        if MAP_UPDATES_AVAILABLE:
            for layer, topic in parse_update_topics():
                self._create_update_subscription(layer, topic)
        else:
            self.get_logger().warn("map_msgs unavailable; map update subscriptions disabled")
        self._create_pose_subscriptions(POSE_TOPIC)
        for layer, topic in parse_marker_topics():
            self._create_marker_subscription(layer, topic)
        if POSE_HZ > 0:
            self.create_timer(1.0 / POSE_HZ, self.pose_timer, callback_group=self.group)

        self.get_logger().info("MapStreamNode ready")
        self.get_logger().info(f"  Map topic: {MAP_TOPIC}")
        for layer, topic in parse_update_topics():
            self.get_logger().info(f"  Update {layer}: {topic}")
        for layer, topic in parse_layer_topics():
            self.get_logger().info(f"  Layer {layer}: {topic}")
        self.get_logger().info(f"  Pose topic: {POSE_TOPIC}")
        for layer, topic in parse_marker_topics():
            self.get_logger().info(f"  Markers {layer}: {topic}")
        self.get_logger().info(f"  Robot frames: {', '.join(self.frames)}")

    def _create_grid_subscriptions(self, layer, topic):
        for qos in self._map_qos_profiles():
            self.create_subscription(
                OccupancyGrid,
                topic,
                lambda msg, layer=layer, topic=topic: self.grid_cb(msg, layer, topic),
                qos,
                callback_group=self.group,
            )

    def _create_update_subscription(self, layer, topic):
        for qos in self._map_qos_profiles():
            self.create_subscription(
                OccupancyGridUpdate,
                topic,
                lambda msg, layer=layer, topic=topic: self.map_update_cb(msg, layer, topic),
                qos,
                callback_group=self.group,
            )

    def _create_pose_subscriptions(self, topic):
        pose_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        if POSE_TOPIC_TYPE in ("pose_with_covariance", "pose_with_covariance_stamped", "covariance"):
            self.create_subscription(
                PoseWithCovarianceStamped,
                topic,
                lambda msg, topic=topic: self.pose_msg_cb(msg, topic, "PoseWithCovarianceStamped"),
                pose_qos,
                callback_group=self.group,
            )
        else:
            self.create_subscription(
                PoseStamped,
                topic,
                lambda msg, topic=topic: self.pose_msg_cb(msg, topic, "PoseStamped"),
                pose_qos,
                callback_group=self.group,
            )

    def _create_marker_subscription(self, layer, topic):
        marker_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            MarkerArray,
            topic,
            lambda msg, layer=layer, topic=topic: self.marker_cb(msg, layer, topic),
            marker_qos,
            callback_group=self.group,
        )

    def _map_qos_profiles(self):
        configured = build_map_qos()
        volatile_best_effort = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=max(1, QOS_DEPTH),
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        volatile_reliable = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=max(1, QOS_DEPTH),
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        return [configured, volatile_best_effort, volatile_reliable]

    def attach_cached(self):
        shared.send({"type": "hello", "room": ROOM, "mapTopic": MAP_TOPIC, "robotId": ROBOT_NAME})
        for payload in self.cached_payloads:
            shared.send(payload)

    def should_emit_layer(self, layer):
        if MAP_PUBLISH_HZ <= 0:
            return True
        now = time.monotonic()
        last = self.last_emit_times.get(layer, 0.0)
        if now - last < 1.0 / MAP_PUBLISH_HZ:
            return False
        self.last_emit_times[layer] = now
        return True

    def emit(self, payload, cache=False):
        payload["ts"] = time.time()
        if cache:
            self.cached_payloads = [
                item for item in self.cached_payloads
                if (item.get("type"), item.get("layer")) != (payload.get("type"), payload.get("layer"))
            ]
            self.cached_payloads.append(payload)
        return shared.send(payload)

    def grid_cb(self, msg, layer, topic):
        try:
            self.publish_grid(msg, layer, topic)
        except Exception as exc:
            self.get_logger().warn(f"{topic} conversion failed: {exc}")

    def publish_grid(self, msg, layer, topic):
        self.frame_counts[layer] = self.frame_counts.get(layer, 0) + 1
        frame_count = self.frame_counts[layer]
        if not self.should_emit_layer(layer):
            if frame_count == 1 or frame_count % 30 == 0:
                self.get_logger().info(
                    f"{topic} [{layer}] frame #{frame_count}: throttled"
                )
            return

        width = int(msg.info.width)
        height = int(msg.info.height)
        origin = {
            "x": float(msg.info.origin.position.x),
            "y": float(msg.info.origin.position.y),
            "yaw": yaw_from_quaternion(msg.info.origin.orientation),
        }
        data = list(msg.data)
        image = occupancy_to_png_data_url(data, width, height, layer)
        common = {
            "layer": layer,
            "topic": topic,
            "width": width,
            "height": height,
            "resolution": float(msg.info.resolution),
            "origin": origin,
            "frame_id": msg.header.frame_id,
            "stamp": stamp_to_float(msg.header.stamp),
        }

        delivered = self.emit({"type": "map", **common, "image": image}, cache=True)
        if SEND_GRID_PAYLOAD:
            delivered = self.emit(
                {
                    "type": "grid",
                    "encoding": "rle-int8",
                    "data": rle(data),
                    "info": {
                        "width": width,
                        "height": height,
                        "resolution": common["resolution"],
                        "origin": origin,
                    },
                    **common,
                },
                cache=True,
            )

        self.layer_maps[layer] = {
            "width": width,
            "height": height,
            "resolution": common["resolution"],
            "origin": origin,
            "frame_id": common["frame_id"],
            "stamp": common["stamp"],
            "data": data,
            "topic": topic,
        }

        if frame_count == 1 or frame_count % 30 == 0:
            delivery_state = "sent" if delivered else "cached, waiting for DataChannel"
            self.get_logger().info(
                f"{topic} [{layer}] frame #{frame_count}: {delivery_state} {width}x{height}, "
                f"resolution={msg.info.resolution:.3f}"
            )

    def map_update_cb(self, msg, layer, topic):
        try:
            if layer not in self.layer_maps:
                self.frame_counts[f"{layer}_updates_waiting"] = self.frame_counts.get(f"{layer}_updates_waiting", 0) + 1
                if self.frame_counts[f"{layer}_updates_waiting"] == 1:
                    self.get_logger().info(f"{topic} [{layer}] update received before full grid; waiting for base layer")
                return
            base = self.layer_maps[layer]
            width = int(base["width"])
            height = int(base["height"])
            update_width = int(msg.width)
            update_height = int(msg.height)
            x0 = int(msg.x)
            y0 = int(msg.y)
            data = list(base["data"])
            update = list(msg.data)

            for row in range(update_height):
                dest_y = y0 + row
                if dest_y < 0 or dest_y >= height:
                    continue
                for col in range(update_width):
                    dest_x = x0 + col
                    if dest_x < 0 or dest_x >= width:
                        continue
                    data[dest_y * width + dest_x] = update[row * update_width + col]

            base["data"] = data
            image = occupancy_to_png_data_url(data, width, height, layer)
            common = {
                "layer": layer,
                "topic": base.get("topic", topic),
                "width": width,
                "height": height,
                "resolution": base["resolution"],
                "origin": base["origin"],
                "frame_id": base["frame_id"],
                "stamp": stamp_to_float(msg.header.stamp),
            }
            delivered = self.emit({"type": "map", **common, "image": image}, cache=True)
            if SEND_GRID_PAYLOAD:
                delivered = self.emit(
                    {
                        "type": "grid",
                        "encoding": "rle-int8",
                        "data": rle(data),
                        "info": {
                            "width": width,
                            "height": height,
                            "resolution": base["resolution"],
                            "origin": base["origin"],
                        },
                        **common,
                    },
                    cache=True,
                )
            count_key = f"{layer}_updates"
            self.frame_counts[count_key] = self.frame_counts.get(count_key, 0) + 1
            if self.frame_counts[count_key] == 1 or self.frame_counts[count_key] % 30 == 0:
                delivery_state = "sent" if delivered else "cached, waiting for DataChannel"
                self.get_logger().info(
                    f"{topic} [{layer}] update #{self.frame_counts[count_key]}: "
                    f"{delivery_state} {update_width}x{update_height} at ({x0}, {y0})"
                )
        except Exception as exc:
            self.get_logger().warn(f"{topic} [{layer}] update failed: {exc}")

    def pose_msg_cb(self, msg, topic, msg_type):
        try:
            pose = msg.pose.pose if hasattr(msg.pose, "pose") else msg.pose
            payload = {
                "type": "pose",
                "robotId": ROBOT_NAME,
                "topic": topic,
                "source": msg_type,
                "frame_id": msg.header.frame_id or MAP_FRAME,
                "stamp": stamp_to_float(msg.header.stamp),
                "x": float(pose.position.x),
                "y": float(pose.position.y),
                "yaw": yaw_from_quaternion(pose.orientation),
            }
            self.emit(payload, cache=True)
            self.emit({**payload, "type": "robot_pose"}, cache=False)

            count_key = f"pose_{msg_type}"
            self.frame_counts[count_key] = self.frame_counts.get(count_key, 0) + 1
            if self.frame_counts[count_key] == 1 or self.frame_counts[count_key] % 30 == 0:
                self.get_logger().info(
                    f"{topic} [{msg_type}] pose #{self.frame_counts[count_key]}: "
                    f"x={payload['x']:.2f}, y={payload['y']:.2f}, yaw={payload['yaw']:.2f}"
                )
        except Exception as exc:
            self.get_logger().warn(f"{topic} pose conversion failed: {exc}")

    def marker_cb(self, msg, layer, topic):
        try:
            markers = []
            for marker in msg.markers:
                if marker.action == marker.DELETE:
                    continue
                markers.append(
                    {
                        "id": int(marker.id),
                        "ns": marker.ns,
                        "type": int(marker.type),
                        "frame_id": marker.header.frame_id,
                        "x": float(marker.pose.position.x),
                        "y": float(marker.pose.position.y),
                        "yaw": yaw_from_quaternion(marker.pose.orientation),
                        "scale": {
                            "x": float(marker.scale.x),
                            "y": float(marker.scale.y),
                            "z": float(marker.scale.z),
                        },
                        "color": {
                            "r": float(marker.color.r),
                            "g": float(marker.color.g),
                            "b": float(marker.color.b),
                            "a": float(marker.color.a),
                        },
                    }
                )

            payload = {
                "type": "markers",
                "layer": layer,
                "topic": topic,
                "markers": markers,
            }
            delivered = self.emit(payload, cache=True)

            self.frame_counts[layer] = self.frame_counts.get(layer, 0) + 1
            if self.frame_counts[layer] == 1 or self.frame_counts[layer] % 30 == 0:
                delivery_state = "sent" if delivered else "cached, waiting for DataChannel"
                self.get_logger().info(
                    f"{topic} [{layer}] marker array #{self.frame_counts[layer]}: "
                    f"{delivery_state} {len(markers)} markers"
                )
        except Exception as exc:
            self.get_logger().warn(f"{topic} [{layer}] marker conversion failed: {exc}")

    def pose_timer(self):
        transform = self.lookup_robot_transform()
        if transform is None:
            return

        translation = transform.transform.translation
        pose = {
            "robotId": ROBOT_NAME,
            "frame_id": MAP_FRAME,
            "x": float(translation.x),
            "y": float(translation.y),
            "yaw": yaw_from_quaternion(transform.transform.rotation),
        }
        self.emit({"type": "pose", **pose}, cache=True)
        self.emit({"type": "robot_pose", **pose}, cache=False)

    def lookup_robot_transform(self):
        for frame in self.frames:
            try:
                transform = self.tf_buffer.lookup_transform(MAP_FRAME, frame, Time())
                if frame != self.last_pose_frame:
                    self.get_logger().info(f"Robot pose frame: {MAP_FRAME} <- {frame}")
                    self.last_pose_frame = frame
                return transform
            except TransformException:
                continue
        return None


def start_ros2():
    global _map_node
    rclpy.init()
    _map_node = MapStreamNode()
    executor = MultiThreadedExecutor()
    executor.add_node(_map_node)
    executor.spin()


async def wait_for_offer():
    count = 0
    while True:
        try:
            response = requests.get(f"{SIGNALING_URL}/offer/{ROOM}", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        count += 1
        log(f"\rWaiting for map offer... {count}s",)
        await asyncio.sleep(1)


async def run_webrtc():
    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=build_ice_servers()))

    @pc.on("datachannel")
    def on_datachannel(channel):
        log(f"DataChannel received: {channel.label}")
        loop = asyncio.get_event_loop()
        attached = False

        def attach_channel():
            nonlocal attached
            if attached:
                return
            attached = True
            shared.attach(channel, loop)
            log(f"DataChannel open: {channel.label}")
            if _map_node:
                _map_node.attach_cached()
            else:
                shared.send({"type": "hello", "room": ROOM, "rosAvailable": False})

        async def wait_until_open():
            for _ in range(50):
                if channel.readyState == "open":
                    attach_channel()
                    return
                await asyncio.sleep(0.1)

        @channel.on("open")
        def on_open():
            attach_channel()

        @channel.on("close")
        def on_close():
            shared.detach(channel)

        @channel.on("message")
        def on_message(message):
            if message == "ping":
                shared.send({"type": "pong", "ts": time.time()})

        loop.create_task(wait_until_open())

    @pc.on("connectionstatechange")
    async def on_state():
        log(f"Map WebRTC state: {pc.connectionState}")

    offer = await wait_for_offer()
    log("Map offer received")
    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    response = requests.post(
        f"{SIGNALING_URL}/answer",
        json={"room": ROOM, "sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
        timeout=5,
    )
    response.raise_for_status()
    log("Map answer sent")

    wait_sec = 0
    try:
        while True:
            await asyncio.sleep(1)
            wait_sec += 1
            if pc.connectionState == "connected":
                wait_sec = 0
            if pc.connectionState in ("failed", "closed"):
                break
            if pc.connectionState in ("new", "connecting") and wait_sec >= CONNECT_TIMEOUT_SEC:
                log(f"Map connection timeout ({CONNECT_TIMEOUT_SEC}s)")
                break
    finally:
        await pc.close()


async def main():
    log("ARES WebRTC Map Stream Server")
    log(f"  Room: {ROOM}")
    log(f"  Map topic: {MAP_TOPIC}")
    log(f"  Robot: {ROBOT_NAME}")
    log(f"  Signaling: {SIGNALING_URL}")

    if ROS2_AVAILABLE:
        threading.Thread(target=start_ros2, daemon=True).start()
        await asyncio.sleep(1)
    else:
        log("ROS2 unavailable; waiting for WebRTC only")

    while True:
        try:
            await run_webrtc()
        except KeyboardInterrupt:
            break
        except Exception as exc:
            log(f"Map server error: {exc}; retrying in 3s")
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(main())
