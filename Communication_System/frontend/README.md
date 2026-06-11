# Voice Communication Frontend

이 디렉터리는 백엔드 패키지 설치 없이 먼저 확인할 수 있는 정적 프론트엔드 기반이다.

구성:

- `control_dashboard/`: 관제 PC용 음성 통신 대시보드
- `android_device/`: 후발 로봇 위 Android 단말용 현장 화면

두 화면은 현재 FastAPI 서버 없이도 브라우저에서 바로 열 수 있다. WebSocket 연결 버튼은 추후 `Communication_System/control_pc/voice_server`가 실행되면 같은 signaling protocol로 연결된다.

## Open

```bash
xdg-open Communication_System/frontend/control_dashboard/index.html
xdg-open Communication_System/frontend/android_device/index.html
```

GUI 앱을 열 수 없는 환경에서는 브라우저 주소창에 파일 경로를 직접 입력한다.

## Backend Connection

기본 WebSocket 주소:

```text
ws://127.0.0.1:8000/ws/{client_id}?role={role}&device_id={device_id}
```

관제 PC 예시:

```text
ws://127.0.0.1:8000/ws/control-1?role=control&device_id=control-pc
```

Android 단말 예시:

```text
ws://127.0.0.1:8000/ws/android-1?role=android&device_id=robot-top-phone
```

## Current Scope

완료:

- 연결 상태 UI
- 통화 상태 UI
- 장치 상태 UI
- WebSocket 연결/해제
- `session_create`, `call_start`, `call_end`, `heartbeat` 송신
- `status`, `register`, `error` 수신 표시
- 백엔드 미실행 상태에서도 UI 확인 가능

미완료:

- 실제 WebRTC 음성 송수신
- 마이크 권한 요청
- 스피커 출력 제어
- Android 네이티브 앱 패키징
- ROS2 상태 연동
