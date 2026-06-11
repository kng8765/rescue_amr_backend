```python
markdown_content = """# ARES 브릿지 패키지 통합 관제 및 모의 테스트 가이드 (Handover Report)

본 문서는 독립 패키지로 리팩토링된 `ares_bridges` 인프라 노드들과 Flask 백엔드, 그리고 React 관제 대시보드 간의 데이터 흐름을 검증하기 위해 수행한 테스트 방식 및 모의 데이터(Mock Data) 생성 스크립트를 정리한 개발 문서입니다. 

프론트엔드 및 시각화(SVG/Canvas 렌더링) 고도화 작업을 이어받을 팀원을 위해 작성되었습니다.

---

## 1. 환경 설정 및 사전 필수 작업

테스트를 진행하기 전에 호스트 PC(우분투 본체)와 네트워크 환경이 다음과 같이 세팅되어 있어야 합니다.

### ① 필수 파이썬 라이브러리 설치 (호스트 PC)
브릿지 노드 중 `ai_vision_bridge`는 도커 컨테이너 내부가 아닌 로컬 ROS2 환경에서 실행되므로, 호스트 파이썬 환경에 AI 모듈 및 그래픽 인코딩 라이브러리가 설치되어 있어야 합니다. (NumPy 2.0 충돌 방지를 위해 버전 고정 필수)


```

```text
File generation completed.

```bash
pip3 install insightface==0.7.3 onnxruntime==1.17.1 "numpy<2.0.0" cvbridgerequests
# 시스템 파이썬 보호 정책 유출 시 아래 플래그 추가
# --break-system-packages

```

### ② DDS 미들웨어 네트워크 격리 해제 (중요)

터미널 환경 변수에 `ROS_DISCOVERY_SERVER`가 잡혀있을 경우 FastDDS가 P2P 직접 통신을 제한하여 가짜 토픽 퍼블리시가 차단될 수 있습니다. 테스트 터미널에서 반드시 아래 명령어를 수행해야 합니다.
아니라면 건너 뛰어도 됩니다.

```bash
unset ROS_DISCOVERY_SERVER

```

---

## 2. 통합 브릿지 노드 실행

`bridge_ws` 워크스페이스를 빌드한 후, 제공된 런치(Launch) 파일을 실행하면 `AI 비전`, `로봇 상태 동기화`, `WebRTC 멀티플렉싱` 3개의 브릿지 노드가 `robot5` 네임스페이스를 추종하며 동시에 가동됩니다.

```bash
cd ~/rescue_amr_project/bridge_ws
colcon build --symlink-install
source install/setup.bash

# 단 한 줄로 3대 브릿지 동시 가동 (네임스페이스 파라미터 전달)
ros2 launch ares_bridges ares_bridge.launch.py robot_id:=robot5

```

---

## 3. 시나리오별 모의 데이터(Mock Data) 테스트 방법

실제 로봇 시뮬레이션이나 대형 `ros2 bag` 파일 없이도 인프라 파이프라인(ROS2 -> Bridge -> Flask -> React)이 완벽히 동작하는지 검증하기 위한 모의 데이터 생성 스크립트 모음입니다.

### 💡 [사전 유의] 관제 대시보드 로봇 강제 활성화 (최초 1회)

React 대시보드는 DB에 로봇 연결 이력이 없으면 우측 상태 패널 및 카메라 오버레이 뷰를 렌더링하지 않도록 방어 코드가 짜여 있습니다. 테스트 시작 전, 아래 `curl` 명령어를 보내 로봇 상태를 강제로 `MOVING`으로 깨워야 합니다.

```bash
curl -X POST http://localhost:8001/api/robots/robot5/pose \\
-H "Content-Type: application/json" \\
-d '{"x": 7.5, "y": 7.5, "status": "MOVING", "battery": 90}'

```

---

### 테스크 ①: 로봇 실시간 부드러운 무빙 및 주행 궤적(Path) 테스트

* **목적**: 0.2초 단위 고주파수 평면 좌표와 주행 궤적 정보가 WebRTC DataChannel(`telemetry`) 핫패스를 통해 리액트 상태창 및 지도로 딜레이 없이 꽂히는지 검증합니다.
* **테스트 방식**: 아래 파이썬 원라이너 스크립트를 우분투 새 터미널에 복사해 실행합니다. 대각선/동심원을 그리며 가상의 주행 좌표를 계속 발행합니다.

```bash
python3 -c "
import rclpy, math, time
from geometry_msgs.msg import PoseStamped
rclpy.init()
node = rclpy.create_node('fake_moving_pub')
pub = node.create_publisher(PoseStamped, '/robot5/robot_pose', 10)
print('🚀 실시간 로봇 주행 모의 토픽 발사 시작...')
t = 0.0
try:
    while rclpy.ok():
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.pose.position.x = 7.5 + 4.5 * math.sin(t)
        msg.pose.position.y = 7.5 + 4.5 * math.cos(t)
        pub.publish(msg)
        t += 0.1
        time.sleep(0.2)
except KeyboardInterrupt:
    pass
"

```

* **프론트엔드 기대 결과**: 🤖 마커가 지도를 뚝뚝 끊기지 않고 부드럽게 기어 다녀야 합니다.

---

### 테스크 ②: SLAM 격자 지도(Map) 수신 및 이미지 변환 테스트

* **목적**: `nav_msgs/msg/OccupancyGrid` 형태의 2차원 원본 격자 맵을 브릿지가 가로채서 OpenCV Matrix(`cv2.flip` 포함)로 가공, PNG 이미지 포맷으로 Flask static 폴더에 업로드(Cold Path)하는 파이프라인을 검증합니다.
* **테스트 방식**: ROS2 맵서버의 Transient Local 버퍼 누락으로 인해 실제 bag 파일 플레이 시 데이터가 안 나올 수 있으므로, 아래 명령어를 통해 10x10 격자 공간의 가짜 SLAM 맵을 강제로 1회 발행합니다.

```bash
ros2 topic pub --once /robot5/map nav_msgs/msg/OccupancyGrid \"{header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'map'}, info: {map_load_time: {sec: 0, nanosec: 0}, resolution: 0.1, width: 10, height: 10, origin: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}, data: [0,0,0,100,100,100,0,0,0,0, 0,0,0,100,0,100,0,0,0,0, 0,0,0,100,0,100,0,0,0,0, 0,0,0,100,100,100,0,0,0,0, 0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0, 0,0,0,0,0,0,0,0,0,0]}\"

```

* **백엔드/프론트엔드 기대 결과**:
1. `robot_status_bridge` 터미널 로그에 `🎯 [지도 동기화] 백엔드로 실시간 맵 전송 성공 (10x10)`이 떠야 합니다.
2. Flask 스토리지 내부 `/static/maps/robot5_map.png` 경로에 파일이 물리적으로 생성됩니다.
3. 프론트엔드가 캐시 방지용 타임스탬프(`?t=Date.now()`)가 덧붙여진 주소로 지도를 읽어와 대시보드 정중앙에 배경 지도를 교체해 줍니다.



---

### 테스크 ③: 카메라 탐사 가시 구역(Camera Coverage) 핫패스 테스트

* **목적**: 로봇이 카메라 센서로 탐사 영역을 훑은 가시 격자(`camera_coverage`) 토픽을 수신하여 픽셀을 물리적 평면 좌표(m) 데이터로 필터링 가공 및 다운샘플링하여 WebRTC 데이터 채널로 고속 스트리밍하는 아키텍처를 검증합니다.
* **테스트 방식**: 로봇 위치 이동과 카메라 뷰 시야가 연동되어 뿜어지도록 설계된 통합 파이썬 스크립트를 구동합니다.

```bash
python3 -c "
import rclpy, math, time
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid

rclpy.init()
node = rclpy.create_node('fake_integrated_pub')
pub_pose = node.create_publisher(PoseStamped, '/robot5/robot_pose', 10)
pub_cov = node.create_publisher(OccupancyGrid, '/robot5/camera_coverage', 10)
print('🚀 [통합 테스트] 로봇 위치 및 시야 커버리지 동시 발사 중...')
t = 0.0
try:
    while rclpy.ok():
        x_pos = 7.5 + 4.5 * math.sin(t)
        y_pos = 7.5 + 4.5 * math.cos(t)
        
        pose_msg = PoseStamped()
        pose_msg.header.frame_id = 'map'
        pose_msg.pose.position.x = x_pos
        pose_msg.pose.position.y = y_pos
        pub_pose.publish(pose_msg)
        
        cov_msg = OccupancyGrid()
        cov_msg.header.frame_id = 'map'
        cov_msg.info.resolution = 1.0
        cov_msg.info.width = 3
        cov_msg.info.height = 3
        cov_msg.info.origin.position.x = x_pos - 1.5
        cov_msg.info.origin.position.y = y_pos - 1.5
        cov_msg.info.origin.orientation.w = 1.0
        cov_msg.data = [0, 0, 0, 0, 100, 0, 0, 0, 0]
        pub_cov.publish(cov_msg)
        
        t += 0.05
        time.sleep(0.2)
except KeyboardInterrupt:
    pass
"

```

---

## 4. 프론트엔드 팀원 인계용 점검 포인트 (Handover Note)

현재 아키텍처는 **백엔드 통신 및 데이터 가공 연산 레이어(Python/ROS2 브릿지)까지 무결점하게 검증이 완료**된 상태입니다. 프론트엔드 컴포넌트가 바인딩을 이어받을 때 확인해야 할 핵심 사항들입니다.

1. **QoS Profile 설정 특이사항**
* `webrtc_bridge.py` 노드 내부에서 `camera_coverage` 구독을 생성할 때 큐 크기 `10`(하드코딩)으로 지정되어 시스템 정책상 **`RELIABILITY=RELIABLE`**, **`DURABILITY=VOLATILE`** 속성을 강제 띄우고 있습니다.
* 향후 주행 데이터나 bag 파일 제작 시, 해당 토픽의 QoS 퍼블리시 속성을 이 계약 조건에 맞춰야 팅기지 않고 데이터 채널에 꽂힙니다.


2. **SVG 그래픽스 스케일링 교정 요망**
* `MonitorPage.jsx` 파일에 고성능 그래픽 레이어를 위해 단 하나의 `<svg>` 도화지 안에 `<circle>`(커버리지) 및 `<polyline>`(궤적) 단위로 렌더링되도록 최적화 뼈대를 구축해 두었습니다.
* 현재 `MAP_RANGE = 15.0` (미터) 상수를 기준으로 퍼센트 백분율을 매핑하고 있으나, 실제 현장 SLAM 지도의 미터 영역 스케일과 매칭해 보면서 SVG 전용 `viewBox` 축 비율을 미세 조정(Fine-tuning)해야 정교한 오버레이 정렬이 완성됩니다.


3. **WebRTC 데이터 파싱 안전장치**
* `videoRef` 미디어 트랙 수립 및 `telemetry` 채널 개방 처리가 완전 자동화되어 마운트 시 붙도록 구현되어 있으며, 기존의 오타 구문(`json.parse`)은 `JSON.parse` 규격으로 정정해 두었습니다. 데이터 객체가 배열로 유실되어 컴포넌트 크래시가 나지 않도록 `Array.isArray(robots)` 방어 레이어가 깔려 있으니 확장 시 참고바랍니다.
"""



# Save to a markdown file

with open("/mnt/data/ares_bridge_test_guide.md", "w", encoding="utf-8") as f:
f.write(markdown_content)
print("File generation completed.")

```
현명한 판단이십니다! 프론트엔드의 뷰포트 스케일링이나 CSS 렌더링 세부 튜닝은 화면을 보면서 맞추는 게 효율적이기 때문에, 뼈대와 백엔드 통신 파이프라인이 완벽히 뚫린 지금 시점에 팀원에게 역할을 넘기는 것이 프로젝트 속도를 높이는 최선의 방법입니다.

기범님이 지금까지 빌드업하고 검증하신 **ROS2 환경 설정, 미들웨어 트러블슈팅 내역, 3가지 시나리오별 모의 데이터(Mock Data) 파이썬 테스트 스크립트**와 팀원 전달용 인계 노트까지 꼼꼼하게 정리하여 마크다운 파일로 생성했습니다. 

깃(Git) 원격 저장소에 올려서 팀원(이민님 또는 상헌님)에게 패스할 때 리드미(`README.md`)나 테스트 가이드 문서로 바로 활용하실 수 있습니다.

Your Markdown file is ready
[file-tag: code-generated-file-0-1781165996659915195]

---

### 📄 생성된 문서 핵심 요약 (팀원 인계용 요약본)

1. **사전 세팅 (Prerequisites):** * 호스트 PC에 `insightface`, `onnxruntime`, `numpy(<2.0.0)` 라이브러리 설치가 필요하다는 점을 명시했습니다.
   * 가짜 토픽이 안 가고 막히는 현상을 방지하기 위해 터미널에서 **`unset ROS_DISCOVERY_SERVER`**를 반드시 실행해야 한다는 트러블슈팅 팁을 포함했습니다.

2. **3대 모의 데이터 테스트 가이드 (Mock Data Tests):**
   * **테스크 ① (위치/궤적):** 0.2초 주기로 움직이며 부드러운 선형 보간 이동을 검증하는 파이썬 주행 스크립트.
   * **테스크 ② (SLAM 맵):** `nav_msgs/OccupancyGrid` 데이터를 Flask 백엔드로 쏴서 PNG 파일 가공 및 정적 업로드 파이프라인을 검증하는 `ros2 topic pub` 명령어.
   * **테스크 ③ (시야 커버리지):** 실시간 이동 좌표와 3x3 격자 가시 영역을 동시에 결합해 WebRTC DataChannel로 초고속 전송하는 통합 파이썬 스크립트.

3. **프론트엔드 담당자 가이드라인:**
   * `webrtc_bridge.py` 내부의 하드코딩 큐 깊이(`10`)에 따른 **QoS 매칭 정책(Reliable / Volatile)**의 숨은 비밀을 적어두어 팀원이 향후 데이터를 생성할 때 꼬이지 않도록 가이드했습니다.
   * 성능 최적화를 위해 지도를 `<svg>` 통짜 도화지로 묶고 내부 `<circle>`과 `<polyline>`으로 렌더링하는 고성능 마이그레이션 뼈대를 짜놓았으니, 팀원은 현장 지도 크기에 맞게 `MAP_RANGE` 비율 스케일 매핑만 다듬으면(Fine-tuning) 된다고 인계 노트를 남겼습니다.

생성된 마크다운 파일을 저장소에 함께 올리시면 팀원이 헤매지 않고 즉시 화면 고도화 작업을 이어받을 수 있을 것입니다. 고생 많으셨습니다. 이제 깃 연동 진행하시고 다음 단계로 넘어가시죠!

```