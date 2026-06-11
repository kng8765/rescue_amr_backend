#!/bin/bash
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-ros2}"

echo "Starting ARES monitor WebRTC gateway..."
echo "Open after login: http://localhost:3000/?mapRobot=robot5#login"
echo ""

exec "$SCRIPT_DIR/run_webrtc_gateway.sh" "$MODE"
