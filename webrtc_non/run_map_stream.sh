#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROBOT_NAME="${1:-robot1}"
ROBOT_NAME_LC="${ROBOT_NAME,,}"

source /opt/ros/humble/setup.bash
for SETUP_FILE in \
  "$BACKEND_DIR/turtlebot4_ws/install/setup.bash" \
  "$BACKEND_DIR/vision_ws/install/setup.bash"
do
  if [ -f "$SETUP_FILE" ]; then
    source "$SETUP_FILE"
  fi
done

if ! python3 -c "import aiortc, cv2, numpy, requests" >/dev/null 2>&1; then
  echo "❌ WebRTC Python 패키지가 설치되어 있지 않습니다."
  echo "   아래 명령을 한 번 실행한 뒤 다시 시도하세요:"
  echo "   python3 -m pip install --user -r \"$SCRIPT_DIR/requirements.txt\""
  exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-1}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_LOG_DIR="${ROS_LOG_DIR:-/tmp/rescue_amr_ros_logs}"
mkdir -p "$ROS_LOG_DIR"

if [ "$ROBOT_NAME_LC" = "robot5" ] || \
   [ "$ROBOT_NAME_LC" = "tb_05" ] || \
   [ "$ROBOT_NAME_LC" = "tb05" ]; then
  DEFAULT_DISCOVERY_SERVER=";192.168.108.105:11811;"
else
  DEFAULT_DISCOVERY_SERVER=";192.168.108.101:11811;"
fi
export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-$DEFAULT_DISCOVERY_SERVER}"
export ROS_SUPER_CLIENT="${ROS_SUPER_CLIENT:-True}"

export SIGNALING_URL="${SIGNALING_URL:-http://127.0.0.1:5000}"
export WEBRTC_MAP_ROOM="${WEBRTC_MAP_ROOM:-ares-map-${ROBOT_NAME}}"
export WEBRTC_MAP_TOPIC="${WEBRTC_MAP_TOPIC:-/${ROBOT_NAME}/map}"
export WEBRTC_MAP_UPDATE_TOPIC="${WEBRTC_MAP_UPDATE_TOPIC:-/${ROBOT_NAME}/map_updates}"
export WEBRTC_CAMERA_COVERAGE_UPDATE_TOPIC="${WEBRTC_CAMERA_COVERAGE_UPDATE_TOPIC:-/${ROBOT_NAME}/camera_coverage_updates}"
export WEBRTC_POSE_TOPIC="${WEBRTC_POSE_TOPIC:-/${ROBOT_NAME}/pose}"
export WEBRTC_ROBOT_NAME="${WEBRTC_ROBOT_NAME:-$ROBOT_NAME}"
export WEBRTC_MAP_QOS_DEPTH="${WEBRTC_MAP_QOS_DEPTH:-1}"
export WEBRTC_MAP_QOS_RELIABILITY="${WEBRTC_MAP_QOS_RELIABILITY:-reliable}"
export WEBRTC_MAP_QOS_DURABILITY="${WEBRTC_MAP_QOS_DURABILITY:-transient_local}"
export WEBRTC_MAP_PUBLISH_HZ="${WEBRTC_MAP_PUBLISH_HZ:-2}"
export WEBRTC_MAP_SEND_GRID="${WEBRTC_MAP_SEND_GRID:-0}"
export WEBRTC_POSE_HZ="${WEBRTC_POSE_HZ:-5}"

python3 "$SCRIPT_DIR/webrtc_map_server.py"
