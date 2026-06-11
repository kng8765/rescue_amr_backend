#!/usr/bin/env python3
"""
dummy_bridge_feed.py — webrtc_bridge 구독 토픽 전부를 한 번에 발행하는 통합 더미.
실제 로봇 없이 프론트(영상/지도/pose/경로/커버리지/배터리)를 end-to-end 테스트.

발행 토픽 (기본 robot=robot5):
  /robot5/survivor/annotated  sensor_msgs/Image          (애니메이션 영상)
  /robot5/pose                geometry_msgs/PoseStamped  (map 프레임, 이동)
  /robot5/map                 nav_msgs/OccupancyGrid     (SLAM처럼 점점 드러남)
  /robot5/coverage/path       nav_msgs/Path              (이동 궤적)
  /robot5/camera_coverage     nav_msgs/OccupancyGrid     (현재 위치 주변 100)
  /robot5/battery_state       sensor_msgs/BatteryState   (서서히 감소)

실행:
  source /opt/ros/humble/setup.bash
  python3 dummy_bridge_feed.py --ros-args -p robot:=robot5
"""
import math
import os
import threading
import numpy as np
import cv2
import requests
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from sensor_msgs.msg import Image, BatteryState
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path, OccupancyGrid
from cv_bridge import CvBridge

# ── 맵 정의 (map 프레임, 미터) ────────────────────────────────────────────────
RES = 0.05                  # m/cell
W = H = 160                 # 8m x 8m
OX = OY = -4.0              # origin (m)
FLASK_BASE = os.getenv("FLASK_BASE", "http://localhost:8001")  # 데이터 평면(백엔드)


def world_to_cell(x, y):
    return int((x - OX) / RES), int((y - OY) / RES)


class DummyBridgeFeed(Node):
    def __init__(self):
        super().__init__("dummy_bridge_feed")
        self.declare_parameter("robot", "robot5")
        self.robot = self.get_parameter("robot").value
        self.bridge = CvBridge()

        qos_img = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                             history=HistoryPolicy.KEEP_LAST, depth=1)
        r = self.robot
        self.pub_img = self.create_publisher(Image, f"/{r}/survivor/annotated", qos_img)
        self.pub_pose = self.create_publisher(PoseStamped, f"/{r}/pose", 10)
        self.pub_map = self.create_publisher(OccupancyGrid, f"/{r}/map", 10)
        self.pub_path = self.create_publisher(Path, f"/{r}/coverage/path", 10)
        self.pub_cov = self.create_publisher(OccupancyGrid, f"/{r}/camera_coverage", 10)
        self.pub_bat = self.create_publisher(BatteryState, f"/{r}/battery_state", 10)

        # 벽(전체 구조) — 외곽 + 내부 칸막이
        self.walls = np.zeros((H, W), dtype=bool)
        self.walls[0, :] = self.walls[-1, :] = True
        self.walls[:, 0] = self.walls[:, -1] = True
        self.walls[40:120, 80] = True          # 세로 칸막이
        self.walls[80, 20:80] = True           # 가로 칸막이
        self.known = np.zeros((H, W), dtype=bool)   # SLAM처럼 점점 밝혀짐

        self.path_poses = []
        self.t = 0
        self.tick = 0
        self.create_timer(1.0 / 15.0, self.on_image)   # 영상 15Hz
        self.create_timer(0.2, self.on_slow)            # 나머지 5Hz
        self.get_logger().info(f"🧪 dummy_bridge_feed 시작 — robot={r}")

    # ── 현재 위치(라운드 형태로 순회) ────────────────────────────────────────
    def current_pose(self):
        t = self.t
        cx = 2.5 * math.cos(t * 0.25)
        cy = 2.5 * math.sin(t * 0.25)
        yaw = t * 0.25 + math.pi / 2
        return cx, cy, yaw

    def on_image(self):
        self.t += 1.0 / 15.0
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        shift = int((self.t * 50) % 255)
        frame[:, :, 0] = (np.linspace(0, 255, 640).astype(int) + shift) % 255
        frame[:, :, 2] = (np.linspace(255, 0, 640).astype(int) + shift) % 255
        bx = int((640 - 130) * (0.5 + 0.5 * math.sin(self.t)))
        cv2.rectangle(frame, (bx, 180), (bx + 130, 310), (0, 255, 0), 3)
        cv2.putText(frame, "ARES DUMMY (annotated)", (18, 46),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.putText(frame, f"{self.robot}", (18, 86),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        msg.header.frame_id = "camera"
        self.pub_img.publish(msg)

    def on_slow(self):
        self.tick += 1
        cx, cy, yaw = self.current_pose()
        now = self.get_clock().now().to_msg()

        # pose
        p = PoseStamped()
        p.header.stamp = now
        p.header.frame_id = "map"
        p.pose.position.x, p.pose.position.y = cx, cy
        p.pose.orientation.z = math.sin(yaw / 2.0)
        p.pose.orientation.w = math.cos(yaw / 2.0)
        self.pub_pose.publish(p)

        # path (누적, 최근 200점)
        self.path_poses.append((cx, cy))
        self.path_poses = self.path_poses[-200:]
        path = Path()
        path.header.stamp = now
        path.header.frame_id = "map"
        for (px, py) in self.path_poses:
            ps = PoseStamped()
            ps.header.frame_id = "map"
            ps.pose.position.x, ps.pose.position.y = px, py
            path.poses.append(ps)
        self.pub_path.publish(path)

        # SLAM처럼 현재 위치 주변을 '밝혀진(known)' 영역으로 확장
        ccx, ccy = world_to_cell(cx, cy)
        rad = 22
        y0, y1 = max(0, ccy - rad), min(H, ccy + rad)
        x0, x1 = max(0, ccx - rad), min(W, ccx + rad)
        self.known[y0:y1, x0:x1] = True

        # map: known 영역만 (벽=100, 자유=0, 미탐색=-1) — 1초마다
        if self.tick % 5 == 0:
            grid = np.full((H, W), -1, dtype=np.int8)
            grid[self.known & self.walls] = 100
            grid[self.known & ~self.walls] = 0
            self.pub_map.publish(self._occ(grid, now))

        # camera_coverage: 현재 위치 주변 셀 = 100
        cov = np.full((H, W), -1, dtype=np.int8)
        cov[y0:y1, x0:x1] = 100
        self.pub_cov.publish(self._occ(cov, now))

        # battery: 100 → 서서히 감소
        bat = BatteryState()
        bat.header.stamp = now
        bat.percentage = max(0.0, 1.0 - self.tick * 0.0005)
        self.pub_bat.publish(bat)

        # 탐사 완료율(coverage_ratio) → 데이터 평면(백엔드)에 POST (약 2초마다).
        # 실제 시스템에선 robot_status_bridge가 CoverageStatus를 받아 POST하는 자리.
        # 여기선 시연용으로 탐색 진행을 램프로 흉내(블로킹 회피 위해 별도 스레드).
        if self.tick % 10 == 0:
            ratio = min(1.0, self.tick * 0.0015)
            threading.Thread(target=self._post_coverage, args=(ratio,), daemon=True).start()

    def _post_coverage(self, ratio):
        try:
            requests.post(
                f"{FLASK_BASE}/api/robots/{self.robot}/coverage",
                json={"coverage_ratio": round(float(ratio), 3), "mode": "explore"},
                timeout=2,
            )
        except Exception:
            pass

    def _occ(self, grid, stamp):
        m = OccupancyGrid()
        m.header.stamp = stamp
        m.header.frame_id = "map"
        m.info.resolution = RES
        m.info.width = W
        m.info.height = H
        m.info.origin.position.x = OX
        m.info.origin.position.y = OY
        m.data = grid.flatten().tolist()
        return m


def main(args=None):
    rclpy.init(args=args)
    node = DummyBridgeFeed()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
