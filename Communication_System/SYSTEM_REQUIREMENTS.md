# System Requirement Document

## 1. Document Purpose

본 문서는 구조 로봇 음성 통신 시스템의 초기 요구사항을 정의한다.

대상 시스템은 후발 로봇과 함께 운용되는 Android 모바일 또는 태블릿과 관제 PC를 동일 WiFi 네트워크로 연결하여, 현장 구조 대상자와 관제 인원이 실시간 양방향 음성 통신을 수행하도록 하는 시스템이다.

초기 구상은 Android 장치를 후발 로봇에 고정 장착하는 방식이었으나, 로봇 본체에 별도 스피커와 마이크를 부착하기 어려운 상황이다. 따라서 Android 모바일 또는 태블릿을 후발 로봇 위에 올려놓고, 내장 마이크와 스피커를 사용하는 현장 음성 단말로 운용한다.

---

## 2. System Scope

### 2.1 포함 범위

- 관제 PC와 Android 모바일 또는 태블릿 간 실시간 음성 통신
- 동일 WiFi 네트워크 기반 내부망 연결
- WebRTC 기반 음성 송수신
- WebSocket 기반 Signaling
- 관제 PC의 Voice Server 및 Signaling Server
- Android 앱의 음성 송수신 기능
- ROS2 이벤트와 음성 통신 상태 연동
- APK 직접 배포 방식
- 현장 운용을 위한 장치 설정 및 복구 기능

### 2.2 제외 범위

초기 버전에서는 다음 항목을 필수 범위에서 제외한다.

- Zoom, Discord 등 외부 음성 통신 서비스 사용
- Google Play Store 배포
- LTE 또는 5G 외부망 통신
- 다자간 음성 통신
- 영상 통화
- AI 음성 분석
- 클라우드 서버 기반 중계

단, 위 항목은 향후 확장 기능으로 고려할 수 있다.

---

## 3. Operating Assumptions

초기 시스템은 다음 환경을 가정한다.

- 관제 PC, 선발 로봇, 후발 로봇, Android 모바일 또는 태블릿은 동일 WiFi에 연결된다.
- 관제 PC는 Ubuntu 22.04와 ROS2 Humble 환경을 사용한다.
- 관제 PC는 고정 IP를 사용하는 것을 권장한다.
- Android 장치는 Android 11 이상을 권장하며, 현재 확인된 Android 버전은 Android 16이다.
- 현재 확인된 WiFi 성능은 245 Mb/s, 5.3 GHz이다.
- Android 장치는 후발 로봇 위에 올려놓는 현장 음성 단말로 운용한다.
- 관제 PC는 Signaling Server와 Voice Session Manager를 실행한다.
- Android 앱은 관제 PC의 IP와 포트를 알고 있어야 한다.
- 음성 데이터는 WebRTC로 송수신한다.
- ROS2는 음성 데이터 자체가 아니라 통화 요청, 연결 상태, 종료 상태를 연동한다.

---

## 4. Functional Requirements

### FR-01. 동일 WiFi 연결

시스템은 관제 PC와 Android 장치가 동일 WiFi 네트워크에 연결된 상태에서 동작해야 한다.

검증 기준:

- Android 장치에서 관제 PC IP로 Ping이 가능해야 한다.
- Android 앱에서 관제 PC의 Signaling Server에 접속할 수 있어야 한다.

### FR-02. 관제 PC Signaling Server

관제 PC는 WebRTC 연결 생성을 위한 Signaling Server를 제공해야 한다.

처리해야 하는 메시지는 다음과 같다.

- Device Register
- Session Create
- SDP Offer
- SDP Answer
- ICE Candidate
- Call Start
- Call End
- Heartbeat
- Reconnect

검증 기준:

- Android 앱이 WebSocket으로 연결된다.
- Offer, Answer, ICE Candidate 교환이 정상 수행된다.

### FR-03. WebRTC 음성 송수신

시스템은 WebRTC를 통해 관제 PC와 Android 장치 간 음성 데이터를 송수신해야 한다.

검증 기준:

- Android 마이크 입력이 관제 PC에서 들려야 한다.
- 관제 PC 마이크 입력이 Android 장치 스피커에서 들려야 한다.
- 양방향 음성이 동시에 송수신되어야 한다.

### FR-04. Full Duplex 통신

초기 목표 통신 방식은 Full Duplex이다.

선정 근거:

- 구조 대상자가 버튼을 조작하지 않아도 된다.
- 관제 인원이 실시간으로 반응을 확인할 수 있다.
- 응급 상황에서 대화 흐름이 끊기지 않는다.
- WebRTC 기본 구조와 잘 맞는다.

추가 고려:

- 현장 소음 또는 하울링 문제가 크면 Push-To-Talk 옵션을 추가한다.

### FR-05. Android 앱 자동 연결

Android 앱은 실행 후 관제 PC 서버에 자동으로 연결을 시도해야 한다.

검증 기준:

- 앱 실행 후 사용자가 별도 조작하지 않아도 서버 접속을 시도한다.
- 연결 실패 시 일정 주기로 재시도한다.
- 연결 성공 여부를 화면에 표시한다.

### FR-06. 통화 상태 표시

관제 PC와 Android 앱은 통화 상태를 표시해야 한다.

필수 상태:

- Server Disconnected
- Server Connected
- Call Ready
- Calling
- Call Connected
- Call Ended
- Reconnecting
- Error

### FR-07. ROS2 상태 연동

Voice Server는 ROS2와 연동하여 통화 요청과 통화 상태를 송수신해야 한다.

초기 후보 Topic:

- `/victim_call_request`
- `/audio_connected`
- `/audio_disconnected`
- `/audio_status`

검증 기준:

- ROS2 이벤트로 통화 요청을 발생시킬 수 있어야 한다.
- WebRTC 연결 완료 시 ROS2에 연결 상태가 반영되어야 한다.
- 통화 종료 또는 끊김 시 ROS2에 종료 상태가 반영되어야 한다.

### FR-08. APK 직접 배포

Android 앱은 APK 파일로 직접 배포할 수 있어야 한다.

검증 기준:

- Release APK를 생성할 수 있어야 한다.
- ADB로 설치할 수 있어야 한다.
- USB 또는 내부 파일 서버를 통해 설치할 수 있어야 한다.

---

## 5. Non-Functional Requirements

### NFR-01. 지연 시간

음성 통신의 왕복 지연은 실시간 대화가 가능한 수준이어야 한다.

초기 목표:

- 권장 지연 시간: 300ms 이하
- 허용 지연 시간: 500ms 이하

### NFR-02. 연결 시간

통화 요청 후 음성 연결이 완료되는 시간은 짧아야 한다.

초기 목표:

- 권장 연결 시간: 5초 이하
- 허용 연결 시간: 10초 이하

### NFR-03. 연속 운용

시스템은 현장 테스트 기준으로 일정 시간 이상 안정적으로 동작해야 한다.

초기 목표:

- 연속 통화: 30분 이상
- 앱 대기 상태 유지: 2시간 이상

### NFR-04. 복구성

WiFi 끊김, 서버 재시작, Android 앱 재시작 상황에서 복구 가능해야 한다.

필수 복구 동작:

- WebSocket 재연결
- WebRTC 세션 재생성
- 통화 상태 초기화
- 사용자에게 연결 상태 표시

### NFR-05. 현장 사용성

현장 구조 대상자는 앱을 직접 조작하지 않는 상황을 가정한다.

요구사항:

- Android 화면은 항상 켜진 상태를 유지한다.
- 앱은 자동 연결을 기본 동작으로 한다.
- 통화 상태는 멀리서도 확인 가능해야 한다.
- 버튼은 최소화한다.

### NFR-06. 보안 및 폐쇄망 운용

초기 시스템은 동일 WiFi 내부망 운용을 전제로 한다.

요구사항:

- 외부 클라우드 서버에 의존하지 않는다.
- 관제 PC IP와 포트는 내부망에서만 접근 가능하도록 구성한다.
- 현장 네트워크에서는 불필요한 외부 통신을 최소화한다.

---

## 6. Hardware Requirements

### 6.1 Control PC

권장 사양:

- Ubuntu 22.04
- ROS2 Humble
- WiFi 또는 Ethernet 네트워크 연결
- 마이크 입력 장치
- 스피커 또는 헤드셋 출력 장치
- Python 3 실행 환경

### 6.2 Android Mobile or Tablet

권장 사양:

- Android 11 이상
- WiFi 지원
- 내장 마이크
- 내장 스피커
- 장시간 화면 켜짐 설정 가능
- 배터리 최적화 해제 가능
- 후발 로봇 위에 안정적으로 배치 가능

현재 확인된 조건:

- 기종: 미정
- Android 버전: Android 16
- WiFi 성능: 245 Mb/s, 5.3 GHz
- 마이크: 모바일 내장 마이크 사용 예정
- 스피커: 모바일 내장 스피커 사용 예정
- 로봇 운용 방식: 후발 로봇 위에 올려놓고 운용

현재 조건에서는 로봇 본체 개조 또는 외장 음향 장치 부착을 요구하지 않는다. 대신 단말이 주행 중 흔들리거나 떨어지지 않도록 미끄럼 방지 패드, 임시 고정 밴드, 보호 케이스 중 하나를 현장 운용 절차에 포함한다.

### 6.3 WiFi AP

권장 조건:

- 관제 PC, 로봇, Android 장치가 모두 접속 가능
- Client Isolation 비활성화
- 충분한 커버리지
- 현장 구조물에 의한 신호 약화 고려
- 고정 IP 또는 DHCP 예약 지원

---

## 7. Software Requirements

### 7.1 Control PC Software

필수 구성:

- FastAPI Server
- WebSocket Signaling Server
- WebRTC Voice Module
- Voice Session Manager
- ROS2 Bridge
- Control GUI
- Logging Module

### 7.2 Android Software

필수 구성:

- Kotlin 기반 Android 앱
- Android WebRTC SDK
- Microphone Permission 처리
- Network Permission 처리
- Server Setting 화면
- Connection State 화면
- Call State 화면
- 자동 재연결 로직

---

## 8. Interface Requirements

### 8.1 WebSocket Signaling Message

초기 메시지 타입은 다음과 같다.

| Message Type | Direction | Description |
| --- | --- | --- |
| `register` | Android -> PC | 장치 등록 |
| `heartbeat` | Android <-> PC | 연결 유지 확인 |
| `call_request` | PC -> Android | 통화 요청 |
| `offer` | Android 또는 PC -> Peer | SDP Offer |
| `answer` | Android 또는 PC -> Peer | SDP Answer |
| `ice_candidate` | Android <-> PC | ICE Candidate 교환 |
| `call_end` | Android 또는 PC -> Peer | 통화 종료 |
| `reconnect` | Android -> PC | 재연결 요청 |
| `error` | Android <-> PC | 오류 상태 전달 |

### 8.2 ROS2 Interface

초기 ROS2 인터페이스는 다음과 같다.

| Topic | Message 후보 | Description |
| --- | --- | --- |
| `/victim_call_request` | `std_msgs/String` 또는 Custom Msg | 구조 대상자 통화 요청 |
| `/audio_connected` | `std_msgs/Bool` 또는 Custom Msg | 음성 통화 연결 완료 |
| `/audio_disconnected` | `std_msgs/Bool` 또는 Custom Msg | 음성 통화 종료 |
| `/audio_status` | Custom Msg | 세션 상태, 장치 ID, 오류 코드 |

실제 메시지 타입은 기존 로봇 시스템의 메시지 구조와 맞춰 확정한다.

---

## 9. Test Requirements

### 9.1 Unit and Prototype Test

- WebSocket 접속 테스트
- Offer, Answer 교환 테스트
- ICE Candidate 교환 테스트
- PC ↔ PC 음성 통신 테스트
- PC ↔ Android 음성 통신 테스트

### 9.2 Network Test

- Ping Test
- Bandwidth Test
- WiFi 신호 약화 테스트
- AP 재시작 후 복구 테스트
- Android WiFi 재연결 테스트

### 9.3 Audio Test

- 3m 거리 음성 테스트
- 5m 거리 음성 테스트
- 10m 거리 음성 테스트
- 모터 소음 환경 테스트
- Echo Cancellation 테스트
- Noise Suppression 테스트

### 9.4 Integrated Scenario Test

- 선발 로봇 인명 탐지
- 위치 정보 전송
- 후발 로봇 이동
- 얼굴 탐지
- 신원 확인
- 음성 통화 연결
- 구조 대상자와 관제 인원 실시간 대화
- 통화 종료
- 장애 발생 후 복구

---

## 10. Open Decisions

아직 확정이 필요한 항목은 다음과 같다.

- 실제 Android 모바일 또는 태블릿 기종
- WiFi AP 모델
- IP 대역
- 관제 PC 고정 IP
- 후발 로봇 위 Android 장치 임시 고정 방식
- Android 장치 전원 공급 방식
- 관제 PC GUI 화면 구성
- ROS2 Topic 이름과 Message 타입
- STUN/TURN 서버 필요 여부
- Push-To-Talk 옵션 추가 여부

---

## 11. Initial Acceptance Criteria

초기 버전은 다음 조건을 만족하면 성공으로 판단한다.

- 관제 PC에서 Signaling Server가 실행된다.
- Android 앱이 같은 WiFi에서 관제 PC 서버에 접속한다.
- WebRTC 연결이 생성된다.
- 관제 PC와 Android 장치 사이에 Full Duplex 음성 통신이 가능하다.
- 통화 상태가 양쪽 화면에 표시된다.
- 통화 종료 후 다시 연결할 수 있다.
- ROS2에서 통화 요청 이벤트를 발생시킬 수 있다.
- 음성 연결 성공 또는 실패 상태가 ROS2에 반영된다.
