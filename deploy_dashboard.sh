#!/bin/bash
# =============================================================
#  ARES 대시보드 빌드 + Firebase 배포
#  사용법: ./deploy_dashboard.sh <백엔드_HTTPS_주소> [firebase_프로젝트_ID]
#  예시:   ./deploy_dashboard.sh https://abc-def.trycloudflare.com ares-rescue
#
#  - 백엔드 주소를 VITE_API_BASE_URL로 주입해 프로덕션 빌드
#  - 빌드는 이미 떠 있는 node:20 컨테이너(amr_react_dashboard)에서 수행
#    (호스트에 Node 설치 불필요, esbuild 플랫폼 불일치 회피)
#  - Firebase Hosting으로 dist/ 배포
# =============================================================
set -euo pipefail

API_URL="${1:-}"
FB_PROJECT="${2:-}"
DASH_DIR="$HOME/rescue_amr_backend/admin_dashboard"

if [ -z "$API_URL" ]; then
    echo "❌ 백엔드 HTTPS 주소가 필요합니다."
    echo "   사용법: ./deploy_dashboard.sh https://....trycloudflare.com [project-id]"
    exit 1
fi

echo "🏗️  [1/2] 대시보드 프로덕션 빌드 (API_BASE=$API_URL)..."
docker exec -e "VITE_API_BASE_URL=$API_URL" amr_react_dashboard npm run build

if [ ! -d "$DASH_DIR/dist" ]; then
    echo "❌ dist/ 가 생성되지 않았습니다. 빌드 로그를 확인하세요."
    exit 1
fi

echo "🚀 [2/2] Firebase Hosting 배포..."
cd "$DASH_DIR"
if [ -n "$FB_PROJECT" ]; then
    firebase deploy --only hosting --project "$FB_PROJECT"
else
    firebase deploy --only hosting
fi

echo ""
echo "✅ 배포 완료! 출력된 Hosting URL로 접속하세요."
echo "⚠️  주의: cloudflared 터널 창은 계속 열어두어야 데이터가 흐릅니다."
echo "    (터널을 닫거나 재시작하면 주소가 바뀌어 재빌드/재배포가 필요합니다.)"
