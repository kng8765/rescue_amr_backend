#!/bin/bash
# run_ares_vision.sh — ARES WebRTC 카메라 브릿지 실행 스크립트
#
# 사용법:
#   ./run_ares_vision.sh [robot_id] [port] [topic]
#
# 예시:
#   ./run_ares_vision.sh robot1 8002 /robot1/oakd/rgb/image_raw/compressed
#   ./run_ares_vision.sh robot5 8003 /robot5/survivor/annotated/compressed
#
# 환경변수로도 설정 가능:
#   WEBRTC_PORT=8003 WEBRTC_IMAGE_TOPIC=/robot5/survivor/annotated/compressed ./run_ares_vision.sh robot5

set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── 인자 파싱 ─────────────────────────────────────────────────────────────────
ROBOT_ID="${1:-robot1}"
PORT="${2:-}"
TOPIC="${3:-/robot1/oakd/rgb/image_raw/compressed}"

# ── ROS2 환경 ─────────────────────────────────────────────────────────────────
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

# ── ROS2 네트워크 설정 (팀원 run_oakd_vision.sh 참고) ────────────────────────
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-1}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"

# Fast DDS Discovery Server 방식
# TB_01: 192.168.108.101  /  robot5(TB_05): 192.168.108.105
ROBOT_ID_LC="${ROBOT_ID,,}"
if [ "$ROBOT_ID_LC" = "robot2" ] || \
   [ "$ROBOT_ID_LC" = "robot5" ] || \
   [ "$ROBOT_ID_LC" = "tb_05" ] || \
   [ "$ROBOT_ID_LC" = "tb05" ]; then
  DEFAULT_DISCOVERY=";192.168.108.105:11811;"
  DEFAULT_TOPIC="/robot5/survivor/annotated/compressed"
  if [ "${WEBRTC_IMAGE_TYPE:-}" = "raw" ]; then
    DEFAULT_TOPIC="/robot5/survivor/annotated"
  fi
else
  DEFAULT_DISCOVERY=";192.168.108.101:11811;"
  DEFAULT_TOPIC="/TB_01/oakd/rgb/image_raw/compressed"
fi

if [ -z "$PORT" ]; then
  if [ "$ROBOT_ID_LC" = "robot2" ] || \
     [ "$ROBOT_ID_LC" = "robot5" ] || \
     [ "$ROBOT_ID_LC" = "tb_05" ] || \
     [ "$ROBOT_ID_LC" = "tb05" ]; then
    PORT="8003"
  else
    PORT="8002"
  fi
fi

export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-$DEFAULT_DISCOVERY}"
export ROS_SUPER_CLIENT="${ROS_SUPER_CLIENT:-True}"

# topic 인자가 없으면 로봇 ID 기반 기본값 사용
if [ -z "${WEBRTC_IMAGE_TOPIC}" ] && [ "$TOPIC" = "/robot1/oakd/rgb/image_raw/compressed" ]; then
  TOPIC="$DEFAULT_TOPIC"
fi

# ── WebRTC 설정 ───────────────────────────────────────────────────────────────
export WEBRTC_PORT="${WEBRTC_PORT:-$PORT}"
export WEBRTC_ROBOT_ID="${WEBRTC_ROBOT_ID:-$ROBOT_ID}"
export WEBRTC_IMAGE_TOPIC="${WEBRTC_IMAGE_TOPIC:-$TOPIC}"
export WEBRTC_TARGET_FPS="${WEBRTC_TARGET_FPS:-15}"
export WEBRTC_MAX_WIDTH="${WEBRTC_MAX_WIDTH:-480}"
export WEBRTC_IMAGE_QOS_DEPTH="${WEBRTC_IMAGE_QOS_DEPTH:-1}"
export WEBRTC_IMAGE_QOS_RELIABILITY="${WEBRTC_IMAGE_QOS_RELIABILITY:-best_effort}"
export WEBRTC_USE_PUBLIC_ICE="${WEBRTC_USE_PUBLIC_ICE:-0}"

# topic이 /compressed로 끝나면 자동으로 compressed 모드
if [[ "$WEBRTC_IMAGE_TOPIC" == */compressed ]]; then
  export WEBRTC_IMAGE_TYPE="${WEBRTC_IMAGE_TYPE:-compressed}"
else
  export WEBRTC_IMAGE_TYPE="${WEBRTC_IMAGE_TYPE:-raw}"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         🤖 ARES WebRTC Vision Server         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Robot:    $WEBRTC_ROBOT_ID"
echo "  Port:     $WEBRTC_PORT"
echo "  Topic:    $WEBRTC_IMAGE_TOPIC ($WEBRTC_IMAGE_TYPE)"
echo "  FPS:      ≤$WEBRTC_TARGET_FPS  MaxWidth: ${WEBRTC_MAX_WIDTH}px"
echo ""
echo "  ROS_DOMAIN_ID:      $ROS_DOMAIN_ID"
echo "  RMW_IMPLEMENTATION: $RMW_IMPLEMENTATION"
echo "  ROS_DISCOVERY_SERVER: $ROS_DISCOVERY_SERVER"
echo ""

python3 "$SCRIPT_DIR/ares_webrtc_vision_server.py"
