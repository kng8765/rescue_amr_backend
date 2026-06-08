#!/bin/bash
# =============================================================
#  ARES 대시보드 Firebase 호스팅 도구 설치
#   - firebase CLI (자체 Node 포함 독립 바이너리, 호스트 Node 불필요)
#   - cloudflared (백엔드 Flask를 임시 HTTPS로 공개하는 터널)
#  사용법: chmod +x setup_hosting_tools.sh && ./setup_hosting_tools.sh
# =============================================================
set -euo pipefail

echo "🔧 [1/2] cloudflared 설치..."
if command -v cloudflared >/dev/null 2>&1; then
    echo "   이미 설치됨: $(cloudflared --version)"
else
    TMP_DEB="/tmp/cloudflared-amd64.deb"
    curl -fsSL -o "$TMP_DEB" \
        https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
    sudo dpkg -i "$TMP_DEB"
    rm -f "$TMP_DEB"
    echo "   완료: $(cloudflared --version)"
fi

echo "🔧 [2/2] firebase CLI 설치 (독립 실행 바이너리)..."
if command -v firebase >/dev/null 2>&1; then
    echo "   이미 설치됨: $(firebase --version)"
else
    curl -fsSL https://firebase.tools | sudo bash
    echo "   완료: $(firebase --version)"
fi

echo ""
echo "✅ 호스팅 도구 설치 완료!"
echo "--------------------------------------------------"
echo "다음 순서로 배포하세요:"
echo "  1) 백엔드 터널 열기:  cloudflared tunnel --url http://localhost:8001"
echo "       → 출력되는 https://....trycloudflare.com 주소를 복사"
echo "  2) Firebase 로그인:   firebase login"
echo "  3) 배포 실행:         ./deploy_dashboard.sh https://....trycloudflare.com"
