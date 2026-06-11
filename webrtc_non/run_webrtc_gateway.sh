#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE="${1:-ros2}"

if [ "$MODE" = "dummy" ] || [ "$MODE" = "local" ]; then
  export WEBRTC_GATEWAY_DUMMY=1
fi
DISPLAY_MODE="ros2"
if [ "${WEBRTC_GATEWAY_DUMMY:-0}" = "1" ]; then
  DISPLAY_MODE="dummy"
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

if ! python3 -c "import aiohttp, aiortc, av, cv2, numpy" >/dev/null 2>&1; then
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

# robot1(TB_01) and robot5(TB_05) discovery servers in one gateway process.
export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-;192.168.108.101:11811;192.168.108.105:11811;}"
export ROS_SUPER_CLIENT="${ROS_SUPER_CLIENT:-True}"

export WEBRTC_GATEWAY_PORT="${WEBRTC_GATEWAY_PORT:-8010}"
export WEBRTC_VIDEO_ROBOTS="${WEBRTC_VIDEO_ROBOTS:-robot1,robot5}"
export WEBRTC_MAP_ROBOT="${WEBRTC_MAP_ROBOT:-robot5}"
export WEBRTC_IMAGE_TOPIC_ROBOT1="${WEBRTC_IMAGE_TOPIC_ROBOT1:-/robot1/oakd/rgb/image_raw/compressed}"
export WEBRTC_IMAGE_TOPIC_ROBOT5="${WEBRTC_IMAGE_TOPIC_ROBOT5:-/robot5/survivor/annotated}"
export WEBRTC_IMAGE_TYPE_ROBOT5="raw"
export WEBRTC_IMAGE_ACCEPT_FPS="${WEBRTC_IMAGE_ACCEPT_FPS:-15}"
export WEBRTC_TARGET_FPS="${WEBRTC_TARGET_FPS:-15}"
export WEBRTC_MAX_WIDTH="${WEBRTC_MAX_WIDTH:-320}"
export WEBRTC_IMAGE_QOS_DEPTH="${WEBRTC_IMAGE_QOS_DEPTH:-2}"
export WEBRTC_IMAGE_QOS_RELIABILITY="${WEBRTC_IMAGE_QOS_RELIABILITY:-best_effort}"
export WEBRTC_MAP_QOS_DEPTH="${WEBRTC_MAP_QOS_DEPTH:-1}"
export WEBRTC_MAP_QOS_RELIABILITY="${WEBRTC_MAP_QOS_RELIABILITY:-reliable}"
export WEBRTC_MAP_QOS_DURABILITY="${WEBRTC_MAP_QOS_DURABILITY:-transient_local}"
export WEBRTC_MAP_PUBLISH_HZ="${WEBRTC_MAP_PUBLISH_HZ:-2}"
export WEBRTC_POSE_HZ="${WEBRTC_POSE_HZ:-5}"
export WEBRTC_USE_PUBLIC_ICE="${WEBRTC_USE_PUBLIC_ICE:-0}"

echo ""
echo "ARES WebRTC Gateway"
echo "  URL:      http://127.0.0.1:${WEBRTC_GATEWAY_PORT}"
echo "  Mode:     ${DISPLAY_MODE}"
echo "  Map:      ${WEBRTC_MAP_ROBOT}"
echo "  Videos:   ${WEBRTC_VIDEO_ROBOTS}"
echo "  robot1:   ${WEBRTC_IMAGE_TOPIC_ROBOT1}"
echo "  robot5:   ${WEBRTC_IMAGE_TOPIC_ROBOT5}"
echo "  ROS_DISCOVERY_SERVER: ${ROS_DISCOVERY_SERVER}"
echo ""

python3 "$SCRIPT_DIR/webrtc_gateway.py"
