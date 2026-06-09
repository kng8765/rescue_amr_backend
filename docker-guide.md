---
# 🚒 소방청 ARES 관제 인프라 도커(Docker) 구동 가이드라인

본 문서는 `rescue_amr_project` 내의 데이터베이스(PostgreSQL), pgAdmin, Flask API 백엔드, 그리고 React(Vite) 관제 대시보드 프론트엔드를 도커 컨테이너 환경에서 한 번에 빌드하고 통합 구동하기 위한 가이드입니다.

도커가 설치되어 있지 않은 팀원들도 순서대로 따라 하면 즉시 관제 화면을 띄우고 테스트할 수 있습니다.

---

## 📋 1. 사전 준비 (도커 및 컴포즈 설치)

컨테이너 환경을 구동하기 위해 아래 명령어를 터미널에 순서대로 복사·붙여넣기 하여 도커 엔진과 도커 컴포즈 플러그인을 설치해 주세요.

### 🐧 Ubuntu / Linux 환경 설치 명령어
```bash
# 1. 패키지 인덱스 업데이트 및 필수 패키지 설치
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# 2. Docker 공식 GPG 키 추가
sudo mkdir -p /etc/apt/keyrings
curl -fsSL [https://download.docker.com/linux/ubuntu/gpg](https://download.docker.com/linux/ubuntu/gpg) | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 3. Docker 저장소 등록
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] [https://download.docker.com/linux/ubuntu](https://download.docker.com/linux/ubuntu) \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Docker 엔진 및 Compose 최신 플러그인 설치
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 5. [선택/권장] sudo 없이 docker 명령어를 쓰기 위한 사용자 그룹 추가
# (명령어 실행 후 터미널을 완전히 껐다 켜거나 재로그인해야 적용됩니다.)
sudo usermod -aG docker $USER

```

---

## 🚀 2. 초기화 및 원클릭 인프라 가동

데이터베이스 폴더 권한 오류 방지 및 원활한 환경 구축을 위해 자동화 스크립트(`init_and_run.sh`)가 준비되어 있습니다.

```bash
# 1. 데이터베이스 작업 디렉토리로 이동
cd ~/rescue_amr_project/database

# 2. 실행 권한 부여 (처음 한 번만 실행)
chmod +x init_and_run.sh

# 3. 인프라 전체 가동 스크립트 실행
./init_and_run.sh

```

> 💡 **스크립트가 내부적으로 수행하는 작업:**
> * 구버전 로컬 캐시 데이터(`.db_data`) 및 권한 잠김 현상을 안전하게 초기화합니다.
> * 최신 도커 컴포즈 엔진(V2) 기반으로 모든 가상 이미지 패키지(`PostgreSQL + pgvector`, `Node.js 20`, `Python 3.10-slim`)를 내려받고 연동합니다.
> 
> 

---

## 🔍 3. 시스템 연동 및 로그 확인 (모니터링)

컨테이너들이 백그라운드(`-d`)에서 정상적으로 실행되면, 내부에서 의존성 라이브러리를 설치하고 초기 테이블을 매핑하기 시작합니다. 아래 명령어로 작동 상태를 실시간 모니터링할 수 있습니다.

### 🖥️ React 프론트엔드 대시보드 구동 로그 확인

Vite 개발 서버가 `Node 20` 환경에서 정상적으로 올라왔는지 검사합니다.

```bash
docker compose logs -f react_dashboard

```

* **정상 작동 신호:** 터미널 로그 맨 밑에 `➜  Local:   http://localhost:3000/` 문구가 에러 없이 찍혀 있으면 성공입니다.

### ⚙️ Flask 백엔드 API & DB 연동 로그 확인

```bash
docker compose logs -f flask_app

```

* **정상 작동 신호:** 초기 구동 시 DB 로딩 시간에 의해 `Connection refused` 예외가 일시적으로 발생할 수 있으나, 백엔드가 스스로 재부팅을 시도하여 로그 하단에 `[ARES 백엔드] 데이터베이스 테이블 생성 및 연동 완료!`가 출력되면 완벽히 결합된 상태입니다.

---

## 🛑 4. 컨테이너 종료 및 주의사항

### ⚠️ [중요] Permission Denied (권한 오류) 대처법

도커 컴포즈 빌드 중에 `.db_data: permission denied` 에러를 만나며 실패하는 경우, root 권한으로 자동 생성된 로컬 DB 폴더를 도커 빌드 엔진이 읽으려고 시도해 발생하는 문제입니다. 당황하지 말고 아래 명령어로 밀어준 뒤 다시 실행하면 해결됩니다.

```bash
# 컨테이너 종료 및 잠긴 임시 폴더 삭제 후 깨끗하게 재빌드
docker compose down
sudo rm -rf .db_data
docker compose up --build -d

```

### 🔌 인프라 안전하게 종료하기

개발을 마치고 도커 백그라운드 프로세스를 모두 클린하게 내리고 싶을 때 사용합니다.

```bash
docker compose down

```