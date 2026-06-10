#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
import math

from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Float32MultiArray


class DummyNavPublisher(Node):
    def __init__(self):
        super().__init__("dummy_nav_publisher")

        self.declare_parameter("robot_id", "robot5")
        self.robot_id = (
            self.get_parameter("robot_id").get_parameter_value().string_value
        )
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # 팀원 명세에 맞춘 토픽 네이밍
        self.pose_pub = self.create_publisher(
            PoseStamped, f"/{self.robot_id}/pose", qos
        )
        self.battery_pub = self.create_publisher(
            BatteryState, f"/{self.robot_id}/battery_state", qos
        )
        self.explore_pub = self.create_publisher(
            Float32MultiArray, f"/{self.robot_id}/camera_coverage_updates", qos
        )

        self.timer = self.create_timer(1.0, self.timer_callback)

        self.time_step = 0.0
        self.explored = 0.0
        self.battery = 100.0

        self.get_logger().info(f"🤖 [더미 노드] {self.robot_id} 가상 주행 시작")

    def timer_callback(self):
        self.time_step += 0.2

        # 1. 위치
        pose_msg = PoseStamped()
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.header.frame_id = "map"
        pose_msg.pose.position.x = 10.0 + 5.0 * math.cos(self.time_step)
        pose_msg.pose.position.y = 10.0 + 5.0 * math.sin(self.time_step)
        self.pose_pub.publish(pose_msg)

        # 2. 배터리 (100에서 서서히 깎임)
        self.battery = max(0.0, self.battery - 0.5)
        batt_msg = BatteryState()
        batt_msg.percentage = self.battery
        self.battery_pub.publish(batt_msg)

        # 3. 탐사율
        if self.explored < 100.0:
            self.explored += 1.0
        exp_msg = Float32MultiArray()
        exp_msg.data = [self.explored, 100.0]
        self.explore_pub.publish(exp_msg)

        self.get_logger().info(
            f"📍 배터리: {int(self.battery)}% | 탐사율: {int(self.explored)}%"
        )


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(DummyNavPublisher())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
