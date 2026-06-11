#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROBOT_NAME="${1:-robot5}"

if [ "$ROBOT_NAME" = "robot5" ]; then
  DEFAULT_ROOM="ares-vision-robot5"
else
  DEFAULT_ROOM="ares-vision-${ROBOT_NAME}"
fi

source /opt/ros/humble/setup.bash
for SETUP_FILE in \
  "$BACKEND_DIR/turtlebot4_ws/install/setup.bash" \
  "$BACKEND_DIR/vision_ws/install/setup.bash"
do
  if [ -f "$SETUP_FILE" ]; then
    source "$SETUP_FILE"
  fi
done

if ! python3 -c "import aiortc, av, cv2, numpy, requests" >/dev/null 2>&1; then
  echo "❌ WebRTC Python 패키지가 설치되어 있지 않습니다."
  echo "   아래 명령을 한 번 실행한 뒤 다시 시도하세요:"
  echo "   python3 -m pip install --user -r \"$SCRIPT_DIR/requirements.txt\""
  exit 1
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-1}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
if [ "$ROBOT_NAME" = "robot5" ]; then
  DEFAULT_DISCOVERY_SERVER=";192.168.108.105:11811;"
else
  DEFAULT_DISCOVERY_SERVER=";192.168.107.101:11811;"
fi
export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-$DEFAULT_DISCOVERY_SERVER}"
export ROS_SUPER_CLIENT="${ROS_SUPER_CLIENT:-True}"

export SIGNALING_URL="${SIGNALING_URL:-http://127.0.0.1:5000}"
export WEBRTC_ROOM="${WEBRTC_ROOM:-$DEFAULT_ROOM}"

if [ "$ROBOT_NAME" = "robot5" ]; then
  DEFAULT_IMAGE_TOPIC="/robot5/survivor/annotated"
  if [ "${WEBRTC_IMAGE_TYPE:-}" = "raw" ]; then
    DEFAULT_IMAGE_TOPIC="/robot5/survivor/annotated"
  fi
else
  DEFAULT_IMAGE_TOPIC="/${ROBOT_NAME}/oakd/rgb/image_raw/compressed"
fi

export WEBRTC_IMAGE_TOPIC="${WEBRTC_IMAGE_TOPIC:-$DEFAULT_IMAGE_TOPIC}"
if [[ "$WEBRTC_IMAGE_TOPIC" == */compressed ]]; then
  export WEBRTC_IMAGE_TYPE="${WEBRTC_IMAGE_TYPE:-compressed}"
else
  export WEBRTC_IMAGE_TYPE="${WEBRTC_IMAGE_TYPE:-raw}"
fi
export WEBRTC_NODE_NAME="${WEBRTC_NODE_NAME:-webrtc_vision_${ROBOT_NAME}}"
export WEBRTC_IMAGE_QOS_DEPTH="${WEBRTC_IMAGE_QOS_DEPTH:-1}"
export WEBRTC_IMAGE_QOS_RELIABILITY="${WEBRTC_IMAGE_QOS_RELIABILITY:-best_effort}"
export WEBRTC_MAX_WIDTH="${WEBRTC_MAX_WIDTH:-480}"
export WEBRTC_TARGET_FPS="${WEBRTC_TARGET_FPS:-15}"

python3 "$SCRIPT_DIR/webrtc_vision_server.py"
