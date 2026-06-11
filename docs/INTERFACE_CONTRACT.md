# ARES 인터페이스 계약 (AMR팀 통합)

이 문서는 **AMR팀(`amr_vision`)의 topic contract**에 맞춰, 우리 백엔드/브릿지가 소비하는
ROS2 인터페이스의 **이름과 형식**을 정리한다. Source of truth는 AMR팀
`rescue_interfaces/docs/topic_contract.md`이며, **public 토픽 이름은 임의로 바꾸지 않고**
launch remap으로 맞춘다.

## 메시지 패키지: `rescue_interfaces` (구 `interfaces` 대체)

| 메시지 | 주요 필드 |
| --- | --- |
| `SurvivorDetection` | header, detection_id, **class_name(`person`/`exit_sign`)**, confidence, pose(PoseStamped), has_map_pose, bbox(RegionOfInterest), image_uri |
| `SurvivorDetectionArray` | header, SurvivorDetection[] detections |
| `CoverageStatus` | header, mode, state, total_goals, visited_goals, coverage_ratio, current_goal(PoseStamped), message |
| `CoverageGoal[]Array`, `VictimInfo` | (계획/표시용) |

> ⚠️ 구버전 `interfaces/TargetPose`는 더 이상 사용하지 않는다. 탐지는 `SurvivorDetectionArray`.

## 토픽 계약 ↔ 우리 소비자

| 계약 토픽 | 타입 | 우리 소비자 | 비고 |
| --- | --- | --- | --- |
| `/robot5/survivor/annotated` | sensor_msgs/Image | `webrtc_bridge` → 영상 트랙 | ✅ |
| `/robot5/survivor/detections` | rescue_interfaces/**SurvivorDetectionArray** | `robot_status_bridge` → `/survivor-logs` | person만 적재, 신원 미상 |
| `/robot5/map` | nav_msgs/OccupancyGrid | `webrtc_bridge`(DataChannel map), `robot_status_bridge`(PNG) | ✅ |
| `/coverage/path` | nav_msgs/Path | `webrtc_bridge` → DataChannel path | **로봇 prefix 없음** |
| `/coverage/status` | rescue_interfaces/**CoverageStatus** | `webrtc_bridge` → DataChannel coverage_status | 탐색 진행률/모드 |
| `/robot5/battery_state` | sensor_msgs/BatteryState | `webrtc_bridge` → DataChannel battery | 표준 |
| `/survivor/identity_results` | std_msgs/String(JSON) | (신원 결과 — 중앙 식별) | 향후 연동 |

### 비계약 확장 (AMR이 발행 안 하면 무시)
- `/robot5/camera_coverage` (OccupancyGrid): 카메라 스윕 셀 오버레이용 우리 자체 토픽. 계약 외.
- robot pose: `pose_topic`(기본 `/{robot}/pose`) 또는 `/{robot}/{robot_pose,amcl_pose,odom}` 폴백.

## Frame 합의
- 글로벌 map frame: `map` · Robot5 base: `robot5/base_link` · OAK-D RGB optical: `oakd_rgb_camera_optical_frame`

## 빌드/실행 시 주의
- `ares_bridges`는 `rescue_interfaces`에 **exec_depend** 한다.
- 브릿지 실행 환경에 **`rescue_interfaces`가 소싱**돼 있어야 탐지/탐색 메시지 구독이 활성화된다.
  (없으면 `_HAS_DETECTIONS`/`_HAS_COVERAGE_STATUS=False`로 graceful 비활성화 — 영상/맵/pose는 동작)
- 코드 내 토픽 이름을 바꾸지 말고 launch namespace/remap으로 `/robot5/...` public 이름을 만든다.
