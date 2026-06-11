# Network Configuration Document

## 1. Network Policy

본 시스템은 관제 PC, 선발 로봇, 후발 로봇, Android 단말이 동일 WiFi 내부망에 연결된 상태를 기준으로 구축한다.

Android 단말은 후발 로봇에 별도 브라켓을 제작하지 않고, 후발 로봇 상단에 올려놓는 현장 음성 단말로 운용한다. 따라서 네트워크 관점에서는 후발 로봇과 Android 단말을 별도 노드로 관리한다.

## 2. Recommended IP Plan

| Node | Recommended IP | Note |
| --- | --- | --- |
| Control PC | `192.168.0.10` | 고정 IP 권장 |
| Lead Robot | `192.168.0.20` | DHCP 예약 또는 고정 IP |
| Follow Robot | `192.168.0.30` | DHCP 예약 또는 고정 IP |
| Android Voice Device | `192.168.0.40` | DHCP 예약 권장 |

실제 AP 대역이 다르면 위 주소는 동일한 규칙으로 변경한다.

## 3. Required Ports

| Service | Protocol | Port | Direction |
| --- | --- | --- | --- |
| FastAPI status API | TCP | `8000` | Android/PC -> Control PC |
| WebSocket signaling | TCP | `8000` | Android/PC -> Control PC |
| WebRTC media | UDP | Dynamic | PC <-> Android |
| ROS2 DDS | UDP | DDS configuration | Robots <-> Control PC |

## 4. Phase 2 Validation Checklist

- [ ] 관제 PC가 WiFi AP에 연결되어 있다.
- [ ] 후발 로봇이 동일 WiFi AP에 연결되어 있다.
- [ ] Android 단말이 동일 WiFi AP에 연결되어 있다.
- [ ] Android 단말에서 관제 PC IP로 Ping이 가능하다.
- [ ] Android 브라우저 또는 앱에서 `http://<CONTROL_PC_IP>:8000/health`에 접근 가능하다.
- [ ] WebSocket signaling 연결이 가능하다.
- [ ] WiFi 끊김 후 Android 단말이 같은 AP에 재연결된다.
- [ ] 재연결 후 signaling session을 다시 생성할 수 있다.

## 5. Control PC Server Start

```bash
cd Communication_System/control_pc
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m voice_server.main
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Status API:

```bash
curl http://127.0.0.1:8000/api/status
```
