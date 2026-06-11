#!/bin/bash
# =============================================================
#  run_ares_bridge.sh — ARES WebRTC 브릿지 실행 (로봇별 1포트)
#  정본 런치(ares_bridge.launch.py)를 robot_id/port와 함께 기동하고,
#  Fast DDS Discovery Server 등 ROS 네트워크 환경을 세팅한다.
#
#  사용법:  ./run_ares_bridge.sh [robot_id] [port]
#  예시:    ./run_ares_bridge.sh robot5 8002     # TB_05 → idx0(ROBOT-01) 패널
#           ./run_ares_bridge.sh robot1 8003     # TB_01 → idx1(ROBOT-02) 패널
# =============================================================
set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ROBOT_ID="${1:-robot5}"
PORT="${2:-8002}"

# ── ROS 네트워크 (Fast DDS Discovery Server) ─────────────────────────────────
# TB_01: 192.168.108.101  /  TB_05: 192.168.108.105
if [ "$ROBOT_ID" = "robot1" ] || [ "$ROBOT_ID" = "TB_01" ]; then
  DEFAULT_DISCOVERY=";192.168.108.101:11811;"
else
  DEFAULT_DISCOVERY=";192.168.108.105:11811;"
fi
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-1}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_DISCOVERY_SERVER="${ROS_DISCOVERY_SERVER:-$DEFAULT_DISCOVERY}"
export ROS_SUPER_CLIENT="${ROS_SUPER_CLIENT:-True}"

# ── 워크스페이스 소싱 ─────────────────────────────────────────────────────────
source /opt/ros/humble/setup.bash
# ares_bridges 빌드 결과 (표준 ROS 메시지만 사용 — 커스텀 의존성 없음)
[ -f "$SCRIPT_DIR/install/setup.bash" ] && source "$SCRIPT_DIR/install/setup.bash"

echo "╔══════════════════════════════════════════════╗"
echo "║         🤖 ARES WebRTC Bridge (로컬)         ║"
echo "╚══════════════════════════════════════════════╝"
echo "  Robot:  $ROBOT_ID    Port: $PORT"
echo "  RMW:    $RMW_IMPLEMENTATION"
echo "  Discovery: $ROS_DISCOVERY_SERVER"
echo ""

ros2 launch ares_bridges ares_bridge.launch.py robot_id:="$ROBOT_ID" port:="$PORT"
