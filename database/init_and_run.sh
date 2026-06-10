#!/bin/bash

echo "🚒 [ARES] 인프라 구축 및 자동 가동 스크립트를 시작합니다..."

# 1. 도커 실행 권한 자동 체크 및 부여
if ! groups $USER | grep &>/dev/null "\bdocker\b"; then
    echo "🔑 도커 실행 권한이 없어 자동으로 사용자를 docker 그룹에 추가합니다..."
    sudo groupadd docker 2>/dev/null
    sudo usermod -aG docker $USER
    echo "⚠️ 권한 적용을 위해 새로운 셸 세션을 엽니다."
fi

# 2. 기존에 꼬여있을 수 있는 구버전 .db_data 권한 및 파일 정리
if [ -d ".db_data" ]; then
    echo "🧹 이전 계정 정보가 남아있을 수 있어 기존 .db_data를 안전하게 정리합니다..."
    sudo rm -rf .db_data
fi

# 3. 점유 중인 포트의 docker-proxy 좀비 프로세스 강제 정리
echo "🧹 포트 점유 중인 좀비 docker-proxy 프로세스를 정리합니다..."
for PORT in 5432 8001 8080 3000; do
    PIDS=$(sudo lsof -ti :$PORT 2>/dev/null)
    if [ -n "$PIDS" ]; then
        echo "  ⚡ 포트 $PORT 점유 PID $PIDS 강제 종료"
        sudo kill -9 $PIDS 2>/dev/null
    fi
done

# 4. 기존 컨테이너 sudo로 강제 정리
echo "🧹 기존 컨테이너를 sudo로 강제 정리합니다..."
sudo docker compose down --remove-orphans 2>/dev/null || true
for NAME in amr_flask_server amr_react_dashboard amr_postgres_db amr_db_admin; do
    sudo docker rm -f $NAME 2>/dev/null || true
done

# 5. 도커 컴포즈 버전 자동 감지 및 알맞은 명령어로 가동
if docker compose version &>/dev/null; then
    echo "🐳 최신 도커 컴포즈(V2)를 감지했습니다. 인프라를 가동합니다."
    sudo docker compose up --build -d
elif docker-compose version &>/dev/null; then
    echo "🐳 구버전 도커 컴포즈(V1)를 감지했습니다. 하이픈(-) 명령어로 우회하여 가동합니다."
    sudo docker-compose up --build -d
else
    echo "❌ 도커 컴포즈가 설치되어 있지 않습니다. 도커 설치를 먼저 확인해 주세요."
    exit 1
fi

echo "✅ [ARES] 모든 인프라(PostgreSQL, pgAdmin, Flask)가 정상적으로 백그라운드에서 가동되었습니다!"
echo "🌐 웹 브라우저에서 http://localhost:3000 로 접속하세요."
