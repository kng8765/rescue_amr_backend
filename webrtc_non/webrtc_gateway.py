#!/usr/bin/env python3
"""Unified WebRTC gateway for ARES monitor map and camera panels."""

import asyncio
import base64
import json
import math
import os
import threading
import time
from fractions import Fraction

import cv2
import numpy as np
from aiohttp import web
from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

try:
    import rclpy
    from cv_bridge import CvBridge
    from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
    from nav_msgs.msg import OccupancyGrid
    from rclpy.callback_groups import ReentrantCallbackGroup
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import CompressedImage, Image
    from tf2_ros import Buffer, TransformException, TransformListener
    from visualization_msgs.msg import MarkerArray

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    print("ROS2 packages unavailable; gateway will serve waiting frames only.", flush=True)

try:
    from map_msgs.msg import OccupancyGridUpdate

    MAP_UPDATES_AVAILABLE = True
except ImportError:
    OccupancyGridUpdate = None
    MAP_UPDATES_AVAILABLE = False


PORT = int(os.getenv("WEBRTC_GATEWAY_PORT", "8010"))
DUMMY_MODE = os.getenv("WEBRTC_GATEWAY_DUMMY", "").lower() in ("1", "true", "yes")
USE_PUBLIC_ICE = os.getenv("WEBRTC_USE_PUBLIC_ICE", "").lower() in ("1", "true", "yes")
VIDEO_ROBOTS = [item.strip() for item in os.getenv("WEBRTC_VIDEO_ROBOTS", "robot1,robot5").split(",") if item.strip()]
MAP_ROBOT = os.getenv("WEBRTC_MAP_ROBOT", "robot5").strip("/")
TARGET_FPS = float(os.getenv("WEBRTC_TARGET_FPS", "15"))
MAX_WIDTH = int(os.getenv("WEBRTC_MAX_WIDTH", "480"))
VIDEO_QOS_DEPTH = int(os.getenv("WEBRTC_IMAGE_QOS_DEPTH", "1"))
VIDEO_QOS_RELIABILITY = os.getenv("WEBRTC_IMAGE_QOS_RELIABILITY", "best_effort").lower()
VIDEO_ACCEPT_FPS = float(os.getenv("WEBRTC_IMAGE_ACCEPT_FPS", "0"))
MAP_QOS_DEPTH = int(os.getenv("WEBRTC_MAP_QOS_DEPTH", "1"))
MAP_QOS_RELIABILITY = os.getenv("WEBRTC_MAP_QOS_RELIABILITY", "reliable").strip().lower()
MAP_QOS_DURABILITY = os.getenv("WEBRTC_MAP_QOS_DURABILITY", "transient_local").strip().lower()
MAP_PUBLISH_HZ = float(os.getenv("WEBRTC_MAP_PUBLISH_HZ", "2"))
POSE_HZ = float(os.getenv("WEBRTC_POSE_HZ", "5"))
POSE_TOPIC_TYPE = os.getenv("WEBRTC_POSE_TOPIC_TYPE", "pose_stamped").strip().lower()
MAX_BUFFERED_BYTES = int(os.getenv("WEBRTC_MAP_MAX_BUFFERED_BYTES", str(4 * 1024 * 1024)))
MAP_FRAME = os.getenv("WEBRTC_MAP_FRAME", "map").strip("/")
RTP_CLOCK_RATE = 90000
STATS_INTERVAL = 5.0


def normalize_robot_id(robot_id):
    return str(robot_id or "").strip().lower().replace("-", "_")


def env_key(robot_id):
    return normalize_robot_id(robot_id).upper().replace("_", "")


def split_topics(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def video_topics_for(robot_id):
    key = env_key(robot_id)
    specific = os.getenv(f"WEBRTC_IMAGE_TOPIC_{key}")
    if specific:
        return split_topics(specific)
    if normalize_robot_id(robot_id) in ("robot5", "robot05", "tb_05", "tb05"):
        return split_topics(os.getenv("WEBRTC_IMAGE_TOPIC_ROBOT5", "/robot5/survivor/annotated"))
    return split_topics(os.getenv("WEBRTC_IMAGE_TOPIC_ROBOT1", "/robot1/oakd/rgb/image_raw/compressed"))


def image_type_for(topic, robot_id):
    if not topic.endswith("/compressed"):
        return "raw"
    key = env_key(robot_id)
    specific = os.getenv(f"WEBRTC_IMAGE_TYPE_{key}", "").strip().lower()
    if specific:
        return specific
    return "compressed"


def build_ice_servers():
    if not USE_PUBLIC_ICE:
        return []
    return [
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(urls="turn:openrelay.metered.ca:80", username="openrelayproject", credential="openrelayproject"),
        RTCIceServer(urls="turn:openrelay.metered.ca:443", username="openrelayproject", credential="openrelayproject"),
    ]


def build_video_qos():
    reliability = ReliabilityPolicy.RELIABLE if VIDEO_QOS_RELIABILITY == "reliable" else ReliabilityPolicy.BEST_EFFORT
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=VIDEO_QOS_DEPTH,
        reliability=reliability,
        durability=DurabilityPolicy.VOLATILE,
    )


def build_map_qos():
    reliability = ReliabilityPolicy.RELIABLE if MAP_QOS_RELIABILITY == "reliable" else ReliabilityPolicy.BEST_EFFORT
    durability = DurabilityPolicy.TRANSIENT_LOCAL if MAP_QOS_DURABILITY == "transient_local" else DurabilityPolicy.VOLATILE
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=MAP_QOS_DEPTH,
        reliability=reliability,
        durability=durability,
    )


def yaw_from_quaternion(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def stamp_to_float(stamp):
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9


def resize_for_stream(frame):
    if MAX_WIDTH <= 0 or frame.shape[1] <= MAX_WIDTH:
        return frame
    height, width = frame.shape[:2]
    scale = MAX_WIDTH / float(width)
    return cv2.resize(frame, (MAX_WIDTH, int(height * scale)), interpolation=cv2.INTER_AREA)


def image_to_rgb(frame, encoding):
    if encoding in ("rgb8", "8UC3"):
        return frame
    if encoding == "bgr8":
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    if encoding == "mono8" or len(frame.shape) == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


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
        if layer.strip() and topic.strip():
            topics.append((layer.strip(), topic.strip()))
    return topics


def map_layer_topics(robot_id):
    default = ",".join(
        [
            f"global_costmap=/{robot_id}/global_costmap/costmap",
            f"local_costmap=/{robot_id}/local_costmap/costmap",
            f"camera_coverage=/{robot_id}/camera_coverage",
        ]
    )
    return parse_named_topics(os.getenv("WEBRTC_MAP_LAYER_TOPICS", default))


def map_update_topics(robot_id):
    default = ",".join(
        [
            f"map=/{robot_id}/map_updates",
            f"camera_coverage=/{robot_id}/camera_coverage_updates",
        ]
    )
    return parse_named_topics(os.getenv("WEBRTC_MAP_UPDATE_TOPICS", default))


def marker_topics(robot_id):
    default = ",".join(
        [
            f"coverage_markers=/{robot_id}/coverage/markers",
            f"survivor_markers=/{robot_id}/survivor/markers",
        ]
    )
    return parse_named_topics(os.getenv("WEBRTC_MARKER_TOPICS", default))


class VideoSharedState:
    def __init__(self, robot_id):
        self.robot_id = robot_id
        self.frame = None
        self.frame_time = 0.0
        self.lock = threading.Lock()
        self.accepted = 0
        self.dropped = 0
        self.sent = 0
        self.incoming = 0
        self.version = 0
        self.last_topic = ""
        self.last_encoding = ""
        self.last_error = ""
        self.min_interval = 1.0 / VIDEO_ACCEPT_FPS if VIDEO_ACCEPT_FPS > 0 else 0.0
        self.last_accept = 0.0

    def mark_incoming(self, topic, encoding=""):
        with self.lock:
            self.incoming += 1
            self.last_topic = topic
            self.last_encoding = encoding

    def should_accept(self):
        now = time.monotonic()
        if self.min_interval > 0 and now - self.last_accept < self.min_interval:
            self.dropped += 1
            return False
        self.last_accept = now
        return True

    def set_frame(self, frame, topic="", encoding=""):
        with self.lock:
            self.frame = frame
            self.frame_time = time.monotonic()
            self.accepted += 1
            self.version += 1
            if topic:
                self.last_topic = topic
            if encoding:
                self.last_encoding = encoding
            self.last_error = ""

    def set_error(self, error):
        with self.lock:
            self.last_error = str(error)

    def get_frame(self):
        with self.lock:
            return self.frame, self.frame_time, self.version

    def mark_sent(self):
        self.sent += 1

    def stats(self):
        with self.lock:
            age = None if self.frame_time <= 0 else max(0.0, time.monotonic() - self.frame_time)
            return {
                "incoming": self.incoming,
                "accepted": self.accepted,
                "dropped": self.dropped,
                "sent": self.sent,
                "version": self.version,
                "lastTopic": self.last_topic,
                "lastEncoding": self.last_encoding,
                "lastError": self.last_error,
                "lastFrameAgeSec": age,
            }


class GatewayVideoTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, state):
        super().__init__()
        self.state = state
        self.start_time = None
        self.pts = 0
        self.frame_interval = 1.0 / TARGET_FPS if TARGET_FPS > 0 else 1.0 / 30
        self.pts_step = max(1, int(RTP_CLOCK_RATE * self.frame_interval))

    async def _next_timestamp(self):
        loop = asyncio.get_event_loop()
        if self.start_time is None:
            self.start_time = loop.time()
            self.pts = 0
            return self.pts, Fraction(1, RTP_CLOCK_RATE)

        self.pts += self.pts_step
        wait = self.start_time + (self.pts / RTP_CLOCK_RATE) - loop.time()
        if wait > 0:
            await asyncio.sleep(wait)
        elif wait < -self.frame_interval:
            self.start_time = loop.time() - (self.pts / RTP_CLOCK_RATE)
        return self.pts, Fraction(1, RTP_CLOCK_RATE)

    async def recv(self):
        pts, time_base = await self._next_timestamp()
        frame, _, _version = self.state.get_frame()
        if frame is None:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(frame, f"ARES {self.state.robot_id} waiting", (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 80, 80), 2)
        vf = VideoFrame.from_ndarray(np.ascontiguousarray(frame), format="rgb24")
        vf.pts = pts
        vf.time_base = time_base
        self.state.mark_sent()
        return vf


class VisionNode(Node):
    def __init__(self, robot_id, topics, state):
        super().__init__(f"ares_gateway_vision_{normalize_robot_id(robot_id)}")
        self.robot_id = robot_id
        self.topics = topics
        self.state = state
        self.bridge = CvBridge()
        self.group = ReentrantCallbackGroup()
        self.frame_count = 0
        self.last_stat = time.monotonic()
        self.last_snap = self.state.stats()

        for topic in topics:
            image_type = image_type_for(topic, robot_id)
            msg_type = CompressedImage if image_type == "compressed" else Image
            if image_type == "compressed":
                callback = lambda msg, topic=topic: self._compressed_cb(msg, topic)
            else:
                callback = lambda msg, topic=topic: self._raw_cb(msg, topic)
            self.create_subscription(msg_type, topic, callback, build_video_qos(), callback_group=self.group)
            self.get_logger().info(f"[gateway:{robot_id}] image topic: {topic} ({image_type})")
        self.create_timer(STATS_INTERVAL, self._status_timer, callback_group=self.group)

    def _raw_cb(self, msg, topic):
        self.state.mark_incoming(topic, getattr(msg, "encoding", ""))
        if not self.state.should_accept():
            return
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, "passthrough")
            frame = resize_for_stream(frame)
            self.state.set_frame(image_to_rgb(frame, msg.encoding), topic, msg.encoding)
            self._log(frame)
        except Exception as exc:
            self.state.set_error(exc)
            self.get_logger().warn(f"[{self.robot_id}] raw conversion failed: {exc}")

    def _compressed_cb(self, msg, topic):
        self.state.mark_incoming(topic, getattr(msg, "format", "compressed"))
        if not self.state.should_accept():
            return
        try:
            frame = self.bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
            frame = resize_for_stream(frame)
            self.state.set_frame(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), topic, getattr(msg, "format", "compressed"))
            self._log(frame)
        except Exception as exc:
            self.state.set_error(exc)
            self.get_logger().warn(f"[{self.robot_id}] compressed conversion failed: {exc}")

    def _log(self, frame):
        self.frame_count += 1
        now = time.monotonic()
        if now - self.last_stat < STATS_INTERVAL:
            return
        snap = self.state.stats()
        elapsed = max(0.001, now - self.last_stat)
        acc_fps = (snap["accepted"] - self.last_snap["accepted"]) / elapsed
        sent_fps = (snap["sent"] - self.last_snap["sent"]) / elapsed
        dropped = snap["dropped"] - self.last_snap["dropped"]
        height, width = frame.shape[:2]
        self.get_logger().info(f"[{self.robot_id}] {width}x{height} acc={acc_fps:.1f}fps sent={sent_fps:.1f}fps drop={dropped}")
        self.last_snap = snap
        self.last_stat = now

    def _status_timer(self):
        snap = self.state.stats()
        if snap["accepted"] > 0:
            return
        self.get_logger().warn(
            f"[{self.robot_id}] no image frames yet. subscribed topics: {', '.join(self.topics)}"
        )


class MapChannels:
    def __init__(self):
        self.channels = []
        self.lock = threading.Lock()

    def attach(self, channel, loop):
        with self.lock:
            self.channels.append((channel, loop))

    def detach(self, channel):
        with self.lock:
            self.channels = [(ch, loop) for ch, loop in self.channels if ch is not channel]

    def send(self, payload):
        payload_text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        delivered = False
        with self.lock:
            pairs = list(self.channels)
        for channel, loop in pairs:
            if channel.readyState != "open" or getattr(channel, "bufferedAmount", 0) > MAX_BUFFERED_BYTES:
                continue
            asyncio.run_coroutine_threadsafe(self._send(channel, payload_text), loop)
            delivered = True
        return delivered

    async def _send(self, channel, payload_text):
        try:
            if channel.readyState == "open":
                channel.send(payload_text)
        except Exception:
            pass


class MapStreamNode(Node):
    def __init__(self, robot_id, channels):
        super().__init__(f"ares_gateway_map_{normalize_robot_id(robot_id)}")
        self.robot_id = robot_id
        self.channels = channels
        self.group = ReentrantCallbackGroup()
        self.tf_buffer = Buffer()
        self.frames = self._frame_candidates()
        self.cached_payloads = []
        self.frame_counts = {}
        self.last_emit_times = {}
        self.layer_maps = {}
        self.map_topic = os.getenv("WEBRTC_MAP_TOPIC", f"/{robot_id}/map")
        self.pose_topic = os.getenv("WEBRTC_POSE_TOPIC", f"/{robot_id}/pose")

        tf_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=100, reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
        tf_static_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=100, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.tf_listener = TransformListener(self.tf_buffer, self, qos=tf_qos, static_qos=tf_static_qos)

        self._create_grid_subscriptions("map", self.map_topic)
        for layer, topic in map_layer_topics(robot_id):
            self._create_grid_subscriptions(layer, topic)
        if MAP_UPDATES_AVAILABLE:
            for layer, topic in map_update_topics(robot_id):
                self._create_update_subscription(layer, topic)
        else:
            self.get_logger().warn("map_msgs unavailable; map update subscriptions disabled")
        self._create_pose_subscription(self.pose_topic)
        for layer, topic in marker_topics(robot_id):
            self._create_marker_subscription(layer, topic)
        if POSE_HZ > 0:
            self.create_timer(1.0 / POSE_HZ, self.pose_timer, callback_group=self.group)

        self.get_logger().info(f"[gateway:{robot_id}] map topic: {self.map_topic}")
        for layer, topic in map_layer_topics(robot_id):
            self.get_logger().info(f"[gateway:{robot_id}] layer {layer}: {topic}")
        self.get_logger().info(f"[gateway:{robot_id}] pose topic: {self.pose_topic}")

    def _frame_candidates(self):
        configured = os.getenv("WEBRTC_ROBOT_FRAMES", "").strip()
        if configured:
            return [frame.strip().strip("/") for frame in configured.split(",") if frame.strip()]
        return [f"{self.robot_id}/base_link", f"{self.robot_id}/base_footprint", "base_link", "base_footprint"]

    def _map_qos_profiles(self):
        return [
            build_map_qos(),
            QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=max(1, MAP_QOS_DEPTH), reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE),
            QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=max(1, MAP_QOS_DEPTH), reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE),
        ]

    def _create_grid_subscriptions(self, layer, topic):
        for qos in self._map_qos_profiles():
            self.create_subscription(OccupancyGrid, topic, lambda msg, layer=layer, topic=topic: self.grid_cb(msg, layer, topic), qos, callback_group=self.group)

    def _create_update_subscription(self, layer, topic):
        for qos in self._map_qos_profiles():
            self.create_subscription(OccupancyGridUpdate, topic, lambda msg, layer=layer, topic=topic: self.map_update_cb(msg, layer, topic), qos, callback_group=self.group)

    def _create_pose_subscription(self, topic):
        pose_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10, reliability=ReliabilityPolicy.BEST_EFFORT, durability=DurabilityPolicy.VOLATILE)
        if POSE_TOPIC_TYPE in ("pose_with_covariance", "pose_with_covariance_stamped", "covariance"):
            self.create_subscription(PoseWithCovarianceStamped, topic, lambda msg: self.pose_msg_cb(msg, topic, "PoseWithCovarianceStamped"), pose_qos, callback_group=self.group)
        else:
            self.create_subscription(PoseStamped, topic, lambda msg: self.pose_msg_cb(msg, topic, "PoseStamped"), pose_qos, callback_group=self.group)

    def _create_marker_subscription(self, layer, topic):
        marker_qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE)
        self.create_subscription(MarkerArray, topic, lambda msg, layer=layer, topic=topic: self.marker_cb(msg, layer, topic), marker_qos, callback_group=self.group)

    def attach_cached(self):
        self.emit({"type": "hello", "room": f"ares-map-{self.robot_id}", "mapTopic": self.map_topic, "robotId": self.robot_id})
        for payload in self.cached_payloads:
            self.channels.send(payload)

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
        return self.channels.send(payload)

    def grid_cb(self, msg, layer, topic):
        try:
            self.publish_grid(msg, layer, topic)
        except Exception as exc:
            self.get_logger().warn(f"{topic} conversion failed: {exc}")

    def publish_grid(self, msg, layer, topic):
        self.frame_counts[layer] = self.frame_counts.get(layer, 0) + 1
        frame_count = self.frame_counts[layer]
        if not self.should_emit_layer(layer):
            return

        width = int(msg.info.width)
        height = int(msg.info.height)
        origin = {
            "x": float(msg.info.origin.position.x),
            "y": float(msg.info.origin.position.y),
            "yaw": yaw_from_quaternion(msg.info.origin.orientation),
        }
        data = list(msg.data)
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
        delivered = self.emit({"type": "map", **common, "image": occupancy_to_png_data_url(data, width, height, layer)}, cache=True)
        self.layer_maps[layer] = {**common, "data": data}

        if frame_count == 1 or frame_count % 30 == 0:
            state = "sent" if delivered else "cached, waiting for DataChannel"
            self.get_logger().info(f"{topic} [{layer}] frame #{frame_count}: {state} {width}x{height}, resolution={msg.info.resolution:.3f}")

    def map_update_cb(self, msg, layer, topic):
        try:
            if layer not in self.layer_maps:
                return
            base = self.layer_maps[layer]
            width = int(base["width"])
            height = int(base["height"])
            data = list(base["data"])
            update = list(msg.data)
            for row in range(int(msg.height)):
                dest_y = int(msg.y) + row
                if dest_y < 0 or dest_y >= height:
                    continue
                for col in range(int(msg.width)):
                    dest_x = int(msg.x) + col
                    if 0 <= dest_x < width:
                        data[dest_y * width + dest_x] = update[row * int(msg.width) + col]
            base["data"] = data
            common = {key: base[key] for key in ("layer", "topic", "width", "height", "resolution", "origin", "frame_id")}
            common["stamp"] = stamp_to_float(msg.header.stamp)
            self.emit({"type": "map", **common, "image": occupancy_to_png_data_url(data, width, height, layer)}, cache=True)
        except Exception as exc:
            self.get_logger().warn(f"{topic} [{layer}] update failed: {exc}")

    def pose_msg_cb(self, msg, topic, msg_type):
        try:
            pose = msg.pose.pose if hasattr(msg.pose, "pose") else msg.pose
            payload = {
                "type": "pose",
                "robotId": self.robot_id,
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
                        "scale": {"x": float(marker.scale.x), "y": float(marker.scale.y), "z": float(marker.scale.z)},
                        "color": {"r": float(marker.color.r), "g": float(marker.color.g), "b": float(marker.color.b), "a": float(marker.color.a)},
                    }
                )
            self.emit({"type": "markers", "layer": layer, "topic": topic, "markers": markers}, cache=True)
        except Exception as exc:
            self.get_logger().warn(f"{topic} [{layer}] marker conversion failed: {exc}")

    def pose_timer(self):
        transform = self.lookup_robot_transform()
        if transform is None:
            return
        translation = transform.transform.translation
        rotation = transform.transform.rotation
        self.emit(
            {
                "type": "robot_pose",
                "robotId": self.robot_id,
                "source": "tf",
                "frame_id": MAP_FRAME,
                "child_frame_id": self.last_pose_frame,
                "stamp": time.time(),
                "x": float(translation.x),
                "y": float(translation.y),
                "yaw": yaw_from_quaternion(rotation),
            },
            cache=True,
        )

    def lookup_robot_transform(self):
        for frame in self.frames:
            try:
                transform = self.tf_buffer.lookup_transform(MAP_FRAME, frame, rclpy.time.Time())
                self.last_pose_frame = frame
                return transform
            except TransformException:
                continue
        return None


class DummyMapPublisher:
    def __init__(self, robot_id, channels):
        self.robot_id = robot_id
        self.channels = channels
        self.cached_payloads = []
        self.running = False
        self.tick = 0
        self.width = 160
        self.height = 120
        self.resolution = 0.05
        self.origin = {"x": -4.0, "y": -3.0, "yaw": 0.0}

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def attach_cached(self):
        self.emit({"type": "hello", "room": f"ares-map-{self.robot_id}", "mapTopic": f"/{self.robot_id}/map", "robotId": self.robot_id})
        for payload in self.cached_payloads:
            self.channels.send(payload)

    def emit(self, payload, cache=False):
        payload["ts"] = time.time()
        if cache:
            self.cached_payloads = [
                item for item in self.cached_payloads
                if (item.get("type"), item.get("layer")) != (payload.get("type"), payload.get("layer"))
            ]
            self.cached_payloads.append(payload)
        return self.channels.send(payload)

    def _grid(self, layer):
        grid = np.zeros((self.height, self.width), dtype=np.int16)
        if layer == "map":
            grid.fill(-1)
            grid[16:104, 20:138] = 0
            grid[22:28, 24:132] = 100
            grid[92:98, 24:132] = 100
            grid[22:96, 24:30] = 100
            grid[22:96, 126:132] = 100
            grid[46:52, 30:88] = 100
            grid[66:72, 64:132] = 100
            grid[28:46, 74:92] = -1
            grid[72:92, 42:58] = -1
        elif layer == "global_costmap":
            grid[18:102, 20:140] = 8
            grid[22:29, 24:132] = 100
            grid[92:99, 24:132] = 100
            grid[22:96, 24:31] = 100
            grid[22:96, 126:133] = 100
        elif layer == "local_costmap":
            cx = 86 + int(18 * math.sin(self.tick * 0.25))
            cy = 58 + int(14 * math.cos(self.tick * 0.25))
            grid[max(0, cy - 18):min(self.height, cy + 18), max(0, cx - 18):min(self.width, cx + 18)] = 12
            grid[max(0, cy - 4):min(self.height, cy + 4), max(0, cx - 4):min(self.width, cx + 4)] = 100
        elif layer == "camera_coverage":
            grid[18:88, 18:106] = 1
            sweep = 64 + int(36 * math.sin(self.tick * 0.18))
            grid[24:98, max(0, sweep - 16):min(self.width, sweep + 16)] = 1
        return grid.reshape(-1).tolist()

    def _map_payload(self, layer):
        data = self._grid(layer)
        return {
            "type": "map",
            "layer": layer,
            "topic": f"/{self.robot_id}/{'map' if layer == 'map' else layer.replace('_', '/')}",
            "width": self.width,
            "height": self.height,
            "resolution": self.resolution,
            "origin": self.origin,
            "frame_id": "map",
            "stamp": time.time(),
            "image": occupancy_to_png_data_url(data, self.width, self.height, layer),
        }

    def _pose_payload(self):
        x = -0.8 + 1.2 * math.sin(self.tick * 0.18)
        y = 0.2 + 0.9 * math.cos(self.tick * 0.18)
        yaw = self.tick * 0.08
        return {
            "type": "robot_pose",
            "robotId": self.robot_id,
            "source": "dummy",
            "frame_id": "map",
            "child_frame_id": f"{self.robot_id}/base_link",
            "stamp": time.time(),
            "x": x,
            "y": y,
            "yaw": yaw,
        }

    def _markers_payload(self):
        return {
            "type": "markers",
            "layer": "survivor_markers",
            "topic": f"/{self.robot_id}/survivor/markers",
            "markers": [
                {
                    "id": 1,
                    "ns": "dummy_survivor",
                    "type": 2,
                    "frame_id": "map",
                    "x": 1.3,
                    "y": 0.8,
                    "yaw": 0.0,
                    "scale": {"x": 0.25, "y": 0.25, "z": 0.25},
                    "color": {"r": 1.0, "g": 0.1, "b": 0.1, "a": 1.0},
                }
            ],
        }

    def _run(self):
        print(f"[dummy:map:{self.robot_id}] started", flush=True)
        while self.running:
            self.tick += 1
            for layer in ("map", "global_costmap", "local_costmap", "camera_coverage"):
                self.emit(self._map_payload(layer), cache=True)
            self.emit(self._pose_payload(), cache=True)
            self.emit(self._markers_payload(), cache=True)
            time.sleep(0.5)


def start_dummy_video(robot_id, state):
    def run():
        tick = 0
        key = normalize_robot_id(robot_id)
        print(f"[dummy:video:{robot_id}] started", flush=True)
        while True:
            tick += 1
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:, :] = (22, 30, 44) if key == "robot1" else (32, 28, 48)
            for x in range(0, 640, 40):
                cv2.line(frame, (x, 0), (x, 480), (54, 68, 88), 1)
            for y in range(0, 480, 40):
                cv2.line(frame, (0, y), (640, y), (54, 68, 88), 1)
            cx = 320 + int(180 * math.sin(tick * 0.08 + (0 if key == "robot1" else 1.6)))
            cy = 240 + int(110 * math.cos(tick * 0.06 + (0 if key == "robot1" else 1.2)))
            color = (80, 210, 120) if key == "robot1" else (255, 160, 80)
            cv2.circle(frame, (cx, cy), 36, color, -1)
            cv2.putText(frame, f"ARES DUMMY {robot_id}", (34, 58), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (235, 240, 248), 2)
            cv2.putText(frame, "Unified gateway /offer", (34, 96), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (170, 190, 210), 2)
            state.set_frame(frame)
            time.sleep(1.0 / max(1.0, TARGET_FPS))

    threading.Thread(target=run, daemon=True).start()


video_states = {normalize_robot_id(robot): VideoSharedState(robot) for robot in VIDEO_ROBOTS}
map_channels = MapChannels()
map_node = None
pcs = set()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}


def start_ros2():
    global map_node
    rclpy.init()
    executor = MultiThreadedExecutor()
    map_node = MapStreamNode(MAP_ROBOT, map_channels)
    executor.add_node(map_node)
    for robot in VIDEO_ROBOTS:
        key = normalize_robot_id(robot)
        topics = video_topics_for(robot)
        node = VisionNode(robot, topics, video_states[key])
        executor.add_node(node)
    executor.spin()


def start_dummy():
    global map_node
    map_node = DummyMapPublisher(MAP_ROBOT, map_channels)
    map_node.start()
    for robot in VIDEO_ROBOTS:
        key = normalize_robot_id(robot)
        start_dummy_video(robot, video_states[key])


async def handle_health(_request):
    return web.json_response(
        {
            "ok": True,
            "port": PORT,
            "mapRobot": MAP_ROBOT,
            "videoRobots": VIDEO_ROBOTS,
            "videoStats": {
                key: state.stats()
                for key, state in video_states.items()
            },
            "ros2": ROS2_AVAILABLE,
            "dummy": DUMMY_MODE,
        },
        headers=CORS_HEADERS,
    )


async def handle_options(_request):
    return web.Response(status=200, headers=CORS_HEADERS)


async def handle_offer(request):
    params = await request.json()
    kind = params.get("kind", "video")
    robot_id = normalize_robot_id(params.get("robotId") or params.get("robot") or "")
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=build_ice_servers()))
    pcs.add(pc)

    if kind == "map":
        @pc.on("datachannel")
        def on_datachannel(channel):
            loop = asyncio.get_event_loop()
            map_channels.attach(channel, loop)
            print(f"[gateway:map:{MAP_ROBOT}] DataChannel open: {channel.label}", flush=True)

            @channel.on("open")
            def on_open():
                if map_node:
                    map_node.attach_cached()

            @channel.on("message")
            def on_message(_message):
                if map_node:
                    map_node.attach_cached()

            @channel.on("close")
            def on_close():
                map_channels.detach(channel)

    elif kind == "video":
        state = video_states.get(robot_id)
        if state is None:
            pcs.discard(pc)
            await pc.close()
            return web.json_response({"error": f"unknown robotId: {robot_id}"}, status=404, headers=CORS_HEADERS)
        pc.addTrack(GatewayVideoTrack(state))
    else:
        pcs.discard(pc)
        await pc.close()
        return web.json_response({"error": f"unknown offer kind: {kind}"}, status=400, headers=CORS_HEADERS)

    @pc.on("connectionstatechange")
    async def on_state():
        print(f"[gateway:{kind}:{robot_id or MAP_ROBOT}] state={pc.connectionState}", flush=True)
        if pc.connectionState in ("failed", "closed"):
            pcs.discard(pc)
            await pc.close()

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type},
        headers=CORS_HEADERS,
    )


async def on_shutdown(_app):
    await asyncio.gather(*[pc.close() for pc in pcs])
    pcs.clear()


def main():
    print("ARES WebRTC Gateway")
    print(f"  Port: {PORT}")
    print(f"  Map:  {MAP_ROBOT}")
    print(f"  Video: {', '.join(VIDEO_ROBOTS)}")
    print(f"  Mode: {'dummy' if DUMMY_MODE else 'ros2'}")
    print(f"  ICE:  {'STUN/TURN' if USE_PUBLIC_ICE else 'LAN only'}")
    print("")

    if DUMMY_MODE:
        start_dummy()
    elif ROS2_AVAILABLE:
        thread = threading.Thread(target=start_ros2, daemon=True)
        thread.start()
        time.sleep(2.0)
    else:
        start_dummy()

    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/offer", handle_offer)
    app.router.add_options("/offer", handle_options)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
