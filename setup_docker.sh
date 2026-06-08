#!/bin/bash
# =============================================================
#  ARES 인프라 사전 준비: Docker Engine + Docker Compose V2 설치
#  대상 OS: Ubuntu 22.04 (jammy) / amd64
#  사용법:  chmod +x setup_docker.sh && ./setup_docker.sh
# =============================================================
set -euo pipefail

echo "🐳 [1/6] 기존 충돌 패키지 정리..."
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do
    sudo apt-get remove -y "$pkg" 2>/dev/null || true
done

echo "🐳 [2/6] 사전 패키지 설치..."
sudo apt-get update -qq
sudo apt-get install -y -qq ca-certificates curl gnupg

echo "🐳 [3/6] Docker 공식 GPG 키 등록..."
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "🐳 [4/6] apt 저장소 추가..."
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -qq

echo "🐳 [5/6] Docker Engine + Compose V2 플러그인 설치..."
sudo apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "🐳 [6/6] 서비스 활성화 및 사용자 권한 부여..."
sudo systemctl enable --now docker
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker "$USER"

echo ""
echo "✅ 설치 완료!"
echo "--------------------------------------------------"
docker --version
docker compose version
echo "--------------------------------------------------"
echo "⚠️  docker 그룹 권한을 적용하려면 다음 중 하나를 실행하세요:"
echo "     newgrp docker      (현재 셸에 즉시 적용)"
echo "     또는 로그아웃 후 재로그인"
echo ""
echo "👉 이후 인프라 가동:  cd database && ./init_and_run.sh"
