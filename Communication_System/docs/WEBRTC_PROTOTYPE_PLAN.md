# WebRTC Prototype Plan

## 1. Current Implementation Scope

현재 구현된 범위는 Phase 3의 기반인 관제 PC Signaling Server이다.

완료된 기능:

- FastAPI 기반 `/health`, `/api/status` API
- WebSocket endpoint: `/ws/{client_id}`
- client role 구분: `control`, `android`, `test`
- signaling message schema
- session 생성
- offer, answer, ice candidate relay
- call start/end 상태 전환
- heartbeat 및 status broadcast

아직 구현하지 않은 기능:

- 실제 WebRTC media 송수신
- PC 마이크/스피커 연결
- Android WebRTC SDK 연동
- ROS2 bridge
- 관제 GUI

## 2. Signaling Message Format

```json
{
  "type": "offer",
  "session_id": "SESSION_ID",
  "source": "control-1",
  "target": "android-1",
  "payload": {
    "type": "offer",
    "sdp": "..."
  }
}
```

지원하는 `type` 값:

- `register`
- `session_create`
- `offer`
- `answer`
- `ice_candidate`
- `call_start`
- `call_end`
- `heartbeat`
- `reconnect`
- `status`
- `error`

## 3. Local Signaling Test

터미널 1:

```bash
cd Communication_System/control_pc
source .venv/bin/activate
PYTHONPATH=. python -m voice_server.main
```

터미널 2:

```bash
cd Communication_System
python3 scripts/pc_signaling_client.py --role control --client-id control-1 --device-id control-pc
```

터미널 3:

```bash
cd Communication_System
python3 scripts/pc_signaling_client.py --role android --client-id android-1 --device-id robot-top-phone
```

이후 WebSocket client에서 `session_create` 메시지를 보내면 서버가 session 상태를 생성한다.

## 4. Next Build Step

다음 구현 순서는 다음과 같다.

1. `aiortc` 기반 PC-to-PC audio prototype 작성
2. Signaling Server와 `aiortc` peer connection 연결
3. Android Studio 프로젝트 생성
4. Android WebRTC SDK에서 동일 signaling protocol 사용
5. PC-to-Android 양방향 음성 통화 검증
