# 🚀 ARES (Autonomous Rescue AMR System) Framework

본 프레임워크는 자율주행 AMR(Turtlebot4)의 전역 위치 정보 및 YOLO 비전 기반 생존자 식별 임베딩 벡터를 실시간으로 수집하고, **확장 PostgreSQL(pgvector)** 인프라와 매칭하여 **React 실시간 대시보드**에 통합 관제 피드를 동기화하는 로봇-백엔드 통합 제어 시스템입니다.

---

## 🏗️ 1. 시스템 아키텍처 개요

본 프레임워크는 로봇 제어 망(ROS2)과 인프라 망(Docker 컨테이너)이 분리되어 톱니바퀴처럼 맞물려 작동합니다.

1. **[YOLO 비전 / AI Dummy Node]**: 현장에서 얼굴 임베딩 벡터 포착 후 ROS2 토픽 발행
2. **[ROS2-DB Bridge Node]**: ROS2 토픽을 가로채 백엔드 Flask API로 HTTP POST 라우팅 전달
3. **[Flask Backend Engine]**: 들어온 임베딩 데이터를 인공지능 전용 PostgreSQL(`pgvector`) 내부 코사인 유사도 연산 매칭 수행 및 인시던트 로그 동시 영구 저장
4. **[React Live Dashboard]**: 백엔드 REST API를 2초 주기로 폴링(Polling)하여 관제실 Incident Log 피드에 실시간 렌더링 출력

---

## 💻 2. 사전 준비 사항 (Prerequisites)

프로젝트를 로컬 컴퓨터에서 구동하기 위해 아래 개발 환경 설치가 선행되어야 합니다.

* **OS**: Ubuntu 22.04 LTS 이상 추천
* **로봇 레이어**: ROS2 Humble 설치 및 환경 변수 빌드 완료
* **인프라 레이어**: Docker Engine 및 Docker Compose V2 가동 환경

---

## 🛠️ 3. 가동 및 인프라 구축 절차 (Quick Start)

팀원들이 테스트 환경을 구축할 때는 터미널 창을 **총 3개** 열고 아래 순서대로 세션을 가동해야 파이프라인이 정상 동작합니다.

### 1️⃣ 세션 1: Docker 백엔드 및 DB 엔진 가동 (Port 8001 / 8080)

중앙 데이터베이스와 Flask 서버를 빌드하고 컨테이너를 올립니다. 호스트 PC의 `.db_data`와 `pgadmin_config` 볼륨 캐시가 자동으로 분리 영구 보존되도록 설계되어 있습니다.

```bash
cd ~/rescue_amr_project/database
# 1. 실행 권한이 없다면 부여 후 인프라 초기화 가동
chmod +x init_and_run.sh
./init_and_run.sh

# 2. Flask 서버 가동 상태 모니터링 로그 확인
docker compose logs -f flask_app

```

> **💡 팀원 필수 체크**: Flask 서버가 기동하면서 `[ARES 백엔드] 데이터베이스 테이블 무결성 검증 및 생성 완료!` 문구를 출력하는지 확인해야 합니다.

### 2️⃣ 세션 2: ROS2 데이터 중계 브릿지 노드 구동

로봇 도메인 망과 DB 웹 도메인 망 사이에서 가교 역할을 수행하는 브릿지를 실행합니다.

```bash
cd ~/rescue_amr_project/turtlebot4_ws
source install/setup.bash
ros2 run rescue_bt_manager bt_db_bridge.py

```
해당 브릿지는 추후 수정 예정!

### 3️⃣ 세션 3: AI 특징 벡터 탐지 더미 노드 실행 (테스트용)

현장에서 로봇이 얼굴을 인식하고 실시간으로 DB 유사도 검색 기능을 검증해볼 수 있는 분할 더미 노드 스크립트입니다.

```bash
cd ~/rescue_amr_project/vision_ws/src/yolo/yolo
python3 dummy_vector.py

```

---

## 📊 4. 관제 및 모니터링 확인 방법

도커(Docker) 환경에서 실행 중인 PostgreSQL 데이터베이스를 pgAdmin 웹 인터페이스를 통해 연결하고 데이터를 확인하는 방법입니다.

## 🛠️ Step 1. pgAdmin 웹 접속
웹 브라우저를 열고 아래 주소로 접속한 뒤, 제공된 계정 정보로 로그인합니다.

* 접속 주소: http://localhost:8080
* 로그인 ID: devkibeom@gmail.com
* 비밀번호: admin_pwd

## 🔌 Step 2. 서버(DB) 연결 등록하기
로그인 후 좌측 상단 메뉴에서 Add New Server 아이콘을 클릭하고 아래 정보를 입력합니다.
## 🔹 General 탭

* Name: ARES_DB (원하는 다른 이름으로 설정해도 무방)

## 🔹 Connection 탭 (🚨 똑같이 입력)

* Host name/address: rescue_db (도커 내부 통신용 서비스 이름)
* Port: 5432
* Maintenance database: rescue_amr_db
* Username: admin
* Password: rokey1234

설정을 모두 입력한 후 하단의 Save 버튼을 눌러 저장합니다.

## 🔍 Step 3. 데이터 확인하기
연결이 완료되면 좌측 트리 메뉴를 통해 실시간으로 적재된 데이터를 확인할 수 있습니다.
### 📂 데이터베이스 탐색 경로
Servers ➔ ARES_DB ➔ Databases ➔ rescue_amr_db ➔ Schemas ➔ public ➔ Tables
### 📈 실시간 데이터 조회

   1. Tables 경로 아래에 생성된 incident_logs 테이블을 확인합니다.
   2. 테이블을 마우스 우클릭합니다.
   3. View/Edit Data ➔ All Rows를 선택합니다.
   4. 터미널이나 더미 데이터를 통해 전송된 생존자 탐지 기록이 엑셀 표 형태로 실시간 리스트업되는 것을 확인할 수 있습니다.

---

## ⚠️ 5. 주의 사항 및 커스텀 가이드 (개발자 노트)

* **외래키(FK) 무결성 보장**: `survivor_logs` 테이블의 생존자 `id`는 부모 테이블인 `survivors` 테이블의 기본키(PK)를 강하게 참조하고 있습니다.
* **테스트 데이터 세팅**: 따라서 더미 노드를 돌리기 전, pgAdmin의 **Query Tool**을 이용하여 조원들의 이름과 256차원 기준 특징 벡터를 부모 테이블에 먼저 `INSERT` 시켜주어야 매칭 시스템(`similarity` 백분율 산출 연산)이 정상 구동됩니다.
* **Git 커밋 주의**: 본 프레임워크는 패키지 종속성 자동 관리를 지원하므로, 로컬 환경의 `node_modules` 폴더 및 `.db_data` 영구 볼륨 스토리지 폴더는 배포 시 `.gitignore`에 의해 제외되도록 설정되어 있으니 안심하고 push하셔도 됩니다.