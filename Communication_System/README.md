# Rescue Robot Voice Communication System

## Current Implementation Status

현재 구현은 **FastAPI WebSocket Signaling Server + 브라우저 WebRTC 음성 통신** 구조이다.

관제 PC 음성 UI는 두 가지 경로로 사용할 수 있다.

| UI | 위치 | 용도 |
| --- | --- | --- |
| Standalone voice dashboard | `Communication_System/frontend/control_dashboard` | 음성 기능 단독 테스트용 |
| Integrated admin dashboard | `admin_dashboard/src/features/voice` | 관제 모니터링 화면 통합 운용용 |

Android 현장 단말은 현재 네이티브 APK가 아니라 `Communication_System/frontend/android_device` 브라우저 화면을 사용한다.

현재 검증된 기본 흐름은 다음과 같다.

```text
admin_dashboard Monitor 화면
  <-> FastAPI Voice Signaling Server
  <-> Android Chrome 음성 단말 화면
  <-> WebRTC PeerConnection 양방향 음성
```

음성 데이터 자체는 서버를 거치지 않고 WebRTC PeerConnection으로 송수신된다. FastAPI 서버는 세션 생성, SDP Offer/Answer, ICE Candidate 중계, 연결 상태 관리만 담당한다.

## 0. WiFi 변경 시 운영 가이드

이 시스템은 관제 PC가 Voice Server를 실행하고, PC 브라우저와 Android 모바일/태블릿 브라우저가 같은 WiFi 안에서 관제 PC 서버에 접속하는 구조이다.

로컬 단위 테스트는 ROS Humble pytest 플러그인 자동 로드와 충돌할 수 있으므로 다음 스크립트로 실행한다.

```bash
cd /home/hig/rescue_amr_project
Communication_System/scripts/run_tests.sh
```

WiFi를 변경하면 가장 먼저 바뀌는 값은 보통 `CONTROL_PC_IP`이다. 예를 들어 기존 WiFi에서 관제 PC IP가 `192.168.0.10`이었고 새 WiFi에서 `192.168.123.48`이 되면, Android가 접속해야 하는 주소와 HTTPS 인증서의 IP 정보도 함께 바뀐다.

### 0.1 WiFi 변경 후 확인할 값

관제 PC에서 현재 WiFi IP를 확인한다.

```bash
hostname -I
```

여러 IP가 나오면 Android 모바일/태블릿이 연결된 WiFi와 같은 대역의 IP를 사용한다. 예를 들어 Android IP가 `192.168.123.xxx`라면 관제 PC도 `192.168.123.xxx` 형태의 IP를 선택한다.

### 0.2 어떤 코드를 고쳐야 하는가

일반적인 WiFi 변경에서는 소스 코드를 고칠 필요가 없다. 다음 항목만 새 IP 기준으로 다시 수행하면 된다.

- HTTPS 인증서 재생성
- Voice Server 재실행
- PC와 Android 브라우저 접속 주소 변경
- Android 화면의 Server 주소 입력값 확인

현재 프론트엔드는 접속한 페이지의 host를 기준으로 WebSocket 주소를 자동 생성한다. 따라서 PC와 Android가 올바른 `https://<CONTROL_PC_IP>:8000/...` 페이지로 접속하면, WebSocket도 자동으로 `wss://<CONTROL_PC_IP>:8000/ws/...`를 사용한다.

코드를 수정해야 하는 경우는 포트를 바꾸거나, 서버 주소를 고정값으로 박아 넣는 방식으로 바꿀 때뿐이다.

| 변경 상황 | 수정/조치 위치 | 설명 |
| --- | --- | --- |
| WiFi만 변경됨 | 코드 수정 없음 | 새 관제 PC IP로 인증서 재생성 후 새 URL로 접속 |
| 관제 PC IP 변경됨 | `generate_https_cert.sh <새 IP>` 실행 | 인증서의 Subject Alternative Name에 새 IP가 들어가야 함 |
| 서버 포트 변경 | 실행 환경 변수 `VOICE_PORT`와 접속 URL 변경 | 예: `VOICE_PORT=8443 Communication_System/scripts/run_voice_server_https.sh` |
| 서버 host 변경 | 실행 환경 변수 `VOICE_HOST` 변경 | 기본값은 `0.0.0.0`이며 보통 수정하지 않음 |
| standalone 프론트 기본 WebSocket 주소 로직 변경 | `frontend/shared.js`의 `defaultWsBase()` | 현재는 페이지 주소 기반 자동 설정 |
| admin dashboard 음성 서버 기본 주소 변경 | `admin_dashboard`의 `VITE_VOICE_WS_URL` | 미설정 시 현재 host의 `:8000`을 자동 사용 |

### 0.3 새 WiFi에서 HTTPS 인증서 다시 만들기

브라우저 WebRTC 마이크 권한은 일반 WiFi IP의 `http://` 페이지에서 막힐 수 있다. USB 없이 Android Chrome으로 테스트하려면 HTTPS를 사용한다.

예를 들어 새 관제 PC IP가 `192.168.123.48`이면 다음을 실행한다.

```bash
cd /home/hig/rescue_amr_project
Communication_System/scripts/generate_https_cert.sh 192.168.123.48
```

생성되는 주요 파일은 다음과 같다.

| 파일 | 용도 |
| --- | --- |
| `Communication_System/certs/voice-local-ca.crt` | Android 모바일/태블릿에 설치할 CA 인증서 |
| `Communication_System/certs/voice-local-ca.key` | CA 개인키, 외부 배포 금지 |
| `Communication_System/certs/voice-server.crt` | Voice Server가 사용할 서버 인증서 |
| `Communication_System/certs/voice-server.key` | Voice Server가 사용할 서버 개인키, 외부 배포 금지 |

Android에 설치하는 파일은 `voice-local-ca.crt`이다. `voice-server.crt`나 `.key` 파일을 Android에 설치하지 않는다.

### 0.4 HTTPS Voice Server 실행

```bash
cd /home/hig/rescue_amr_project
Communication_System/scripts/run_voice_server_https.sh
```

정상 실행 시 서버는 다음 주소에서 열린다.

```text
https://0.0.0.0:8000
```

`0.0.0.0`은 모든 네트워크 인터페이스에서 접속을 받겠다는 뜻이다. 실제 브라우저에서는 `0.0.0.0`으로 접속하지 말고 아래 주소를 사용한다.

### 0.5 각 기기가 접속해야 하는 사이트 주소

같은 WiFi에서 USB 없이 테스트할 때는 HTTPS 주소를 사용한다.

| 기기 | 접속 주소 | 용도 |
| --- | --- | --- |
| 관제 PC standalone | `https://127.0.0.1:8000/` | 음성 기능 단독 관제 화면 |
| 관제 PC standalone | `https://<CONTROL_PC_IP>:8000/` | 실제 WiFi IP로 음성 기능 단독 관제 화면 접속 |
| 관제 PC 통합 모니터링 | `http://localhost:5174/#monitor` 또는 배포된 `admin_dashboard` 주소 | 관제 모니터링 화면 안의 음성 통신 패널 |
| Android 모바일/태블릿 | `https://<CONTROL_PC_IP>:8000/android` | 현장 음성 단말 화면 |
| 상태 확인 | `https://<CONTROL_PC_IP>:8000/health` | 서버 정상 동작 확인 |

예를 들어 관제 PC IP가 `192.168.123.48`이면 다음처럼 접속한다.

```text
관제 PC:
https://127.0.0.1:8000/

관제 PC 통합 모니터링:
http://localhost:5174/#monitor

Android 모바일/태블릿:
https://192.168.123.48:8000/android

상태 확인:
https://192.168.123.48:8000/health
```

USB와 ADB reverse로 테스트할 때만 Android에서 다음 HTTP 주소를 사용할 수 있다.

```text
http://127.0.0.1:8000/android
```

일반 WiFi 접속에서는 Android가 `http://<CONTROL_PC_IP>:8000/android`로 접속하면 마이크 권한이 막힐 수 있으므로 `https://<CONTROL_PC_IP>:8000/android`를 사용한다.

admin dashboard에서 통합 음성 패널을 사용할 때는 `VOICE SERVER` 값을 다음처럼 맞춘다.

```text
USB + adb reverse 테스트:
ws://127.0.0.1:8000

WiFi HTTPS 테스트:
wss://<CONTROL_PC_IP>:8000
```

### 0.6 Android 모바일/태블릿에 인증서 설치하는 방법

먼저 관제 PC에서 Android로 CA 인증서를 복사한다.

ADB를 사용할 수 있으면 다음 명령을 사용한다.

```bash
adb push Communication_System/certs/voice-local-ca.crt /sdcard/Download/voice-local-ca.crt
```

ADB가 없으면 USB 파일 전송, 메신저, 내부 파일 서버 등으로 `voice-local-ca.crt`만 Android의 다운로드 폴더에 복사한다.

Android에서 다음 순서로 설치한다.

1. `설정` 열기
2. `보안 및 개인정보 보호` 또는 `보안` 메뉴 열기
3. `기타 보안 설정` 또는 `암호화 및 사용자 인증 정보` 열기
4. `기기 저장공간에서 인증서 설치` 선택
5. `CA 인증서` 선택
6. `Download/voice-local-ca.crt` 선택
7. 경고 문구 확인 후 설치

주의할 점은 다음과 같다.

- 설치 대상은 `CA 인증서`이다.
- `개인 인증서`, `VPN 및 앱 사용자 인증서`, `WiFi 인증서`로 설치하지 않는다.
- `.key` 파일은 Android로 복사하지 않는다.
- 테스트가 끝나면 설치한 CA 인증서를 삭제한다.
- Android 버전과 제조사에 따라 메뉴 이름은 조금 다를 수 있다.

인증서 설치 후 Android Chrome에서 다음 주소를 연다.

```text
https://<CONTROL_PC_IP>:8000/android
```

인증서 경고가 계속 나오면 다음을 확인한다.

- 인증서를 만들 때 넣은 IP와 실제 접속 IP가 같은지 확인
- Android와 관제 PC가 같은 WiFi에 있는지 확인
- 관제 PC 방화벽에서 `8000/tcp` 접속을 허용했는지 확인
- Android에 설치한 파일이 `voice-local-ca.crt`인지 확인

### 0.7 WiFi 변경 후 전체 절차 요약

1. 관제 PC와 Android 모바일/태블릿을 새 WiFi에 연결한다.
2. 관제 PC에서 `hostname -I`로 새 IP를 확인한다.
3. `Communication_System/scripts/generate_https_cert.sh <새 CONTROL_PC_IP>`를 실행한다.
4. Android에 `Communication_System/certs/voice-local-ca.crt`를 CA 인증서로 설치한다.
5. `Communication_System/scripts/run_voice_server_https.sh`로 서버를 실행한다.
6. 관제 PC에서 standalone 테스트는 `https://127.0.0.1:8000/`를 열고, 통합 테스트는 `admin_dashboard`의 `#monitor` 화면을 연다.
7. Android에서 `https://<CONTROL_PC_IP>:8000/android`를 연다.
8. Android에서 `Connect`를 누른다.
9. standalone 테스트에서는 관제 PC에서 `Connect`, `Create Session`, `Start Call`을 누른다.
10. admin dashboard 통합 테스트에서는 `음성 통신` 패널에서 `연결`, `세션`, `통화`를 누른다.
11. 양쪽 마이크 권한을 허용하고 음성 송수신을 확인한다.

### 0.8 USB + ADB reverse 빠른 테스트 절차

마이크 권한과 인증서 문제를 줄이기 위해 개발 중 첫 테스트는 USB + ADB reverse 방식을 권장한다.

```bash
cd /home/hig/rescue_amr_project
Communication_System/scripts/run_voice_server.sh
adb devices
adb reverse tcp:8000 tcp:8000
```

Android Chrome에서 다음 주소를 연다.

```text
http://127.0.0.1:8000/android
```

Android 화면에서 `Connect`를 누른다.

admin dashboard 통합 화면은 다음 주소로 연다.

```text
http://localhost:5174/#monitor
```

`음성 통신` 패널에서 `VOICE SERVER`가 다음 값인지 확인한다.

```text
ws://127.0.0.1:8000
```

그 다음 `연결`, `세션`, `통화` 순서로 누르고 PC와 Android 양쪽의 마이크 권한을 허용한다.

ADB에서 장치가 `unauthorized`로 보이면 Android 화면의 USB 디버깅 허용 팝업을 승인해야 한다.

### 0.9 admin dashboard 통합 음성 패널 실행

통합 테스트에서는 `Communication_System`의 standalone 관제 페이지 대신 `admin_dashboard`의 Monitor 화면을 사용한다.

개발 서버 실행 예시는 다음과 같다.

```bash
cd /home/hig/rescue_amr_project/admin_dashboard
npx vite --configLoader runner --host 0.0.0.0
```

Vite가 `node_modules/.vite` 권한 문제를 일으키면 `/tmp` 캐시를 사용하는 임시 Vite config로 실행할 수 있다. 현재 개발 환경에서는 다음 형태로 실행해 검증했다.

```bash
npx vite --config /tmp/ares-admin-vite.config.js --configLoader runner --host 0.0.0.0
```

브라우저에서 다음 주소를 연다.

```text
http://localhost:<VITE_PORT>/#monitor
```

예를 들어 Vite가 `5174` 포트로 실행되면 다음 주소를 사용한다.

```text
http://localhost:5174/#monitor
```

Monitor 오른쪽 `음성 통신` 패널의 기본 기능은 다음과 같다.

| 버튼/상태 | 의미 |
| --- | --- |
| `VOICE SERVER` | FastAPI Voice Server WebSocket 주소 |
| `연결` | 관제 화면을 control role로 signaling server에 연결 |
| `세션` | control과 Android client를 묶는 voice session 생성 |
| `통화` | PC 마이크 권한 요청 후 WebRTC Offer 전송 |
| `종료` | 통화 종료 및 local audio track 정리 |
| `Android` | 연결된 Android 단말의 device id |
| `Mic`, `Speaker` | 관제 PC의 마이크/스피커 상태 |

통합 테스트에서 권장 순서는 다음과 같다.

1. Voice Server 실행
2. Android `/android` 화면 접속
3. Android에서 `Connect`
4. admin dashboard `#monitor` 화면 접속
5. `VOICE SERVER` 주소 확인
6. `연결`
7. Android 단말 ID 표시 확인
8. `세션`
9. `통화`
10. PC와 Android의 마이크 권한 허용

세션 생성 시 Voice Server는 같은 control 또는 Android client가 포함된 기존 세션을 `ended`로 정리한 뒤 새 세션을 만든다. admin dashboard와 standalone 관제 화면도 현재 연결된 Android client id가 포함된 활성 세션을 우선 사용한다. 이 처리는 Android 페이지 새로고침이나 WiFi 재접속으로 `android-2499`, `android-5077`처럼 client id가 바뀌는 상황에서 오래된 세션으로 offer를 보내는 문제를 줄이기 위한 것이다.

### 0.10 Troubleshooting

| 증상 | 원인 후보 | 조치 |
| --- | --- | --- |
| Android가 `unauthorized`로 표시됨 | USB 디버깅 미승인 | Android 화면의 RSA fingerprint 팝업에서 허용 |
| Android에서 `SERVER ONLINE`이 되지 않음 | `adb reverse` 누락 또는 WiFi 주소 오류 | USB 테스트는 `adb reverse tcp:8000 tcp:8000`, WiFi 테스트는 `https://<CONTROL_PC_IP>:8000/android` 사용 |
| `통화` 클릭 후 마이크가 차단됨 | 비보안 출처에서 `getUserMedia()` 호출 | PC는 `localhost`, Android WiFi는 HTTPS 사용 |
| admin dashboard에서 WebSocket 오류 | `VOICE SERVER` 주소 불일치 | USB 테스트는 `ws://127.0.0.1:8000`, WiFi HTTPS 테스트는 `wss://<CONTROL_PC_IP>:8000` |
| `Target client is not connected: android-xxxx` | PC가 이전 Android client id가 들어간 오래된 세션을 사용 중 | Android와 PC 화면을 새로고침하고, `연결` -> `세션` -> `통화` 순서로 새 세션을 만든다. 서버 코드를 수정한 뒤라면 Voice Server도 재시작해야 함 |
| Android HTTPS 접속 시 인증서 경고 | CA 인증서 미설치 또는 IP 불일치 | `voice-local-ca.crt`를 Android CA로 설치하고 인증서 생성 IP와 접속 IP 확인 |
| `8000` 포트 bind 실패 | 기존 Voice Server 실행 중 | 기존 서버를 종료하거나 같은 서버를 재사용 |

현재 연결 상태를 직접 확인하려면 다음 API를 사용한다.

```bash
curl -k https://127.0.0.1:8000/api/status
```

응답의 `clients`에는 현재 WebSocket으로 연결된 control/android client가 표시되고, `sessions`에는 생성된 voice session 목록이 표시된다. 오류 메시지의 `android-xxxx`가 `clients`에 없다면 이미 끊긴 Android client를 대상으로 중계하려는 상태이다.

## 1. Project Overview

본 프로젝트는 재난 현장 탐색 및 구조 지원을 위한 다중 로봇 시스템에 실시간 양방향 음성 통신 기능을 추가하는 것을 목표로 한다.

기존 시스템은 선발 로봇이 현장에 먼저 투입되어 SLAM 기반 Mapping을 수행하고, 현장에서 사람을 발견하면 해당 위치 정보를 저장한 뒤 Map 데이터와 위치 정보를 관제 PC로 전송하는 구조이다. 관제 PC는 전달받은 정보를 바탕으로 후발 로봇에게 목표 위치를 송출하고, 후발 로봇은 사람에게 접근하여 얼굴을 탐지한 뒤 관제 PC와의 통신을 통해 신원 확인을 수행한다.

본 통신 시스템은 이 흐름에 Android 모바일 또는 태블릿 기반 음성 통신 장치를 추가한다. 로봇 본체에 별도 스피커와 마이크를 부착하기 어려우므로, Android 모바일 또는 태블릿을 후발 로봇 위에 올려놓는 현장 음성 단말로 운용한다. 관제 시설의 PC는 관제 인원이 사용하는 음성 통신 단말 역할을 수행한다.

최종 목표는 현장 구조 대상자와 관제 시설 인원이 Zoom, Discord와 같은 외부 서비스를 사용하지 않고, 본 프로젝트에서 직접 구축한 시스템을 통해 같은 WiFi 네트워크 안에서 실시간 음성 대화를 수행하는 것이다.

---

## 2. Target Scenario

전체 구조 시나리오는 다음과 같다.

1. 선발 로봇이 현장에 투입된다.
2. 선발 로봇이 SLAM을 이용해 현장 지도를 생성한다.
3. 선발 로봇이 사람을 탐지한다.
4. 탐지된 사람의 위치 좌표를 저장한다.
5. 선발 로봇이 Map과 사람 위치 정보를 관제 PC로 전송한다.
6. 관제 PC가 후발 로봇에게 목표 위치를 전송한다.
7. 후발 로봇이 목표 위치로 이동한다.
8. 후발 로봇이 사람에게 접근하여 얼굴 탐지를 수행한다.
9. 관제 PC와의 통신을 통해 신원 확인을 수행한다.
10. 후발 로봇과 함께 운용되는 Android 모바일 또는 태블릿이 음성 통신 세션을 시작한다.
11. 현장 구조 대상자는 로봇의 모바일 장치를 통해 말한다.
12. 관제 인원은 관제 PC를 통해 말한다.
13. 양측은 실시간 Full Duplex 음성 통신을 수행한다.

---

## 3. System Goal

본 시스템의 핵심 목표는 다음과 같다.

```text
구조 대상자
  <-> Android Mobile or Tablet
  <-> Same WiFi Network
  <-> Control PC
  <-> 관제 인원
```

필수 목표는 다음과 같다.

- 동일 WiFi 네트워크 안에서 PC와 Android 모바일 또는 태블릿을 연결한다.
- 외부 음성 통신 서비스 없이 자체 제작한 앱과 서버로 통신한다.
- 구조 대상자와 관제 인원이 실시간 양방향 음성 대화를 수행한다.
- 후발 로봇의 이동, 얼굴 탐지, 신원 확인 흐름과 음성 통신 기능을 연동한다.
- 통신 연결 상태를 관제 PC와 Android 장치 양쪽에서 확인할 수 있어야 한다.
- 연결 끊김, WiFi 재연결, 앱 재시작 상황에서도 복구 가능한 구조를 갖춘다.

---

## 4. System Participants

### 4.1 선발 로봇

선발 로봇은 음성 통신의 직접 참여자는 아니지만, 전체 구조 시나리오에서 음성 통신이 시작되기 전 단계의 정보를 제공한다.

주요 역할은 다음과 같다.

- SLAM 기반 Mapping 수행
- 현장 인명 탐지
- 탐지 위치 좌표 저장
- Map 데이터와 사람 위치 정보를 관제 PC로 전송
- 후발 로봇 투입을 위한 사전 정보 제공

### 4.2 관제 PC

관제 PC는 전체 시스템의 중심 노드이다. 기존 로봇 제어 및 정보 통합 기능에 더해 음성 통신 서버와 관제자용 음성 통신 클라이언트 역할을 수행한다.

주요 역할은 다음과 같다.

- 선발 로봇으로부터 Map 및 사람 위치 정보 수신
- 후발 로봇에 이동 목표 전송
- 후발 로봇 상태 모니터링
- 신원 확인 데이터 송수신
- Android 모바일 또는 태블릿과 WebRTC 음성 통신 연결
- Signaling Server 운영
- Voice Session 관리
- 관제 인원용 GUI 제공
- ROS2 시스템과 음성 통신 상태 연동

### 4.3 후발 로봇

후발 로봇은 구조 대상자에게 접근하는 물리적 플랫폼이다. Android 모바일 또는 태블릿은 후발 로봇에 장착되는 것을 초기 목표로 했으나, 현재는 장착 가능성이 없는 것으로 확인되었다. 따라서 Android 장치는 후발 로봇에 장착하기 위한 별도 거치 구조를 제작하거나, 후발 로봇과 분리된 독립 음성 통신 단말로 운용하는 방안을 결정해야 한다.

주요 역할은 다음과 같다.

- 관제 PC로부터 목표 위치 수신
- 목표 위치까지 자율 이동
- 구조 대상자 접근
- 얼굴 탐지 수행
- 신원 확인 이벤트 발생
- Android 장치를 통해 음성 통신 제공

### 4.4 Android 모바일 또는 태블릿

Android 장치는 현장 음성 단말이다. 구조 대상자가 별도 장비를 들고 있지 않아도 로봇 또는 로봇 근처에 배치된 장치를 통해 관제 인원과 대화할 수 있어야 한다.

주요 역할은 다음과 같다.

- 마이크를 통해 현장 음성 수집
- 스피커를 통해 관제 인원의 음성 출력
- 관제 PC의 Signaling Server에 접속
- WebRTC Peer Connection 생성
- 음성 송수신 처리
- 연결 상태 표시
- 통화 시작, 종료, 재연결 처리
- 현장 운용을 위한 화면 유지 및 자동 복구

현재 확인된 Android 장치 조건은 다음과 같다.

| 항목 | 확인 결과 |
| --- | --- |
| 기종 | 미정 |
| Android 버전 | Android 16 |
| WiFi 성능 | 245 Mb/s, 5.3 GHz |
| 마이크 | 모바일 내장 마이크 사용 예정 |
| 스피커 | 모바일 내장 스피커 사용 예정 |
| 로봇 장착 방식 | 후발 로봇 위에 올려놓고 운용 |

로봇 본체 개조 없이 단말을 운용하는 방식으로 확정되었으므로, 다음 단계에서는 주행 중 낙하 방지, 화면 유지, 전원 공급, 음성 수음 거리 검증을 수행해야 한다.

---

## 5. Communication Architecture

본 시스템은 데이터 종류에 따라 통신 채널을 분리한다.

| 통신 종류 | 사용 기술 | 목적 |
| --- | --- | --- |
| 로봇 상태 및 임무 데이터 | ROS2 | 위치, 상태, 임무, 이벤트 송수신 |
| WebRTC 연결 제어 | WebSocket | Offer, Answer, ICE Candidate 교환 |
| 실시간 음성 데이터 | WebRTC | 낮은 지연 시간의 양방향 음성 통신 |
| 관제 GUI 내부 제어 | React admin dashboard 또는 standalone browser UI | 세션 제어 및 상태 표시 |

음성 데이터는 ROS2 Topic으로 직접 전송하지 않는다. ROS2는 로봇 상태와 이벤트 중심의 통신에는 적합하지만, 실시간 음성 스트리밍에서는 지연 시간, 지터 처리, Echo Cancellation, Codec 처리, 패킷 손실 대응 기능을 직접 구현해야 하는 부담이 크다. 따라서 음성은 WebRTC로 처리하고, ROS2는 음성 연결 요청과 상태 동기화에 사용한다.

---

## 6. Network Design

### 6.1 기본 네트워크 구조

현재 PC, 선발 로봇, 후발 로봇은 같은 WiFi 네트워크에 연결되어 정보를 송수신하는 구조이다. Android 모바일 또는 태블릿도 동일한 WiFi 네트워크에 연결하여 관제 PC와 직접 통신한다.

예시 구조는 다음과 같다.

```text
WiFi AP
  |-- Control PC          192.168.0.10
  |-- Lead Robot          192.168.0.20
  |-- Follow Robot        192.168.0.30
  |-- Android Tablet      192.168.0.40
```

권장 방식은 다음과 같다.

- 관제 PC는 고정 IP 사용
- 선발 로봇, 후발 로봇, Android 장치는 DHCP 예약 또는 고정 IP 사용
- 모든 장치는 동일 Subnet에 배치
- 관제 PC의 Signaling Server 포트를 Android 장치에서 접근 가능하게 설정
- 현장 운용 전 Ping, 대역폭, 지연 시간, WiFi 재연결 테스트 수행

### 6.2 NAT와 STUN/TURN

본 프로젝트의 초기 목표는 동일 WiFi 내부망 통신이다. 이 경우 PC와 Android 장치가 같은 Subnet에 있으므로 일반적으로 STUN/TURN 서버 없이도 WebRTC 연결이 가능하다.

다만 다음 상황에서는 추가 구성이 필요할 수 있다.

- PC와 Android 장치가 서로 다른 네트워크에 있는 경우
- 공유기 설정으로 Client Isolation이 켜져 있는 경우
- 방화벽이 WebSocket 또는 WebRTC UDP 트래픽을 차단하는 경우
- LTE/5G 또는 외부망 확장을 계획하는 경우

초기 개발에서는 내부망 직접 연결을 우선 구현하고, 이후 외부망 확장 단계에서 STUN/TURN 서버를 추가한다.

### 6.3 Port Plan

초기 포트 계획은 다음과 같다.

| 구성 요소 | 프로토콜 | 포트 예시 | 설명 |
| --- | --- | --- | --- |
| FastAPI HTTP API | TCP | 8000 | 상태 확인, 설정 조회 |
| WebSocket Signaling | TCP | 8000 또는 8765 | WebRTC Offer, Answer, ICE Candidate 교환 |
| WebRTC Media | UDP | 동적 포트 | 실제 음성 미디어 전송 |
| ROS2 DDS | UDP | DDS 설정에 따름 | 기존 로봇 시스템 통신 |

현장 테스트 전에는 방화벽과 공유기 설정에서 위 통신이 차단되지 않는지 확인해야 한다.

---

## 7. Voice Communication Method

### 7.1 Full Duplex 방식

본 프로젝트는 무전기처럼 관제 PC와 현장 로봇 사이에서 음성 통신을 수행하는 것이 목표지만, 실제 구현은 Push-To-Talk 기반 Half Duplex보다 Full Duplex를 우선 목표로 한다.

Full Duplex를 우선하는 이유는 다음과 같다.

- 구조 대상자가 버튼을 누를 필요 없이 말할 수 있다.
- 관제 인원이 대상자의 반응을 즉시 들을 수 있다.
- 응급 상황에서 대화 흐름이 끊기지 않는다.
- WebRTC는 Full Duplex 음성 통신에 적합한 기본 구조를 제공한다.

다만 현장 소음이나 하울링 문제가 크면 옵션으로 Push-To-Talk 모드를 추가할 수 있다.

### 7.2 WebRTC 선택 이유

WebRTC를 사용하는 이유는 다음과 같다.

- 실시간 음성 통신을 위해 설계된 표준 기술이다.
- Opus Codec을 사용하여 음질과 대역폭 효율이 좋다.
- 지터 버퍼, 패킷 손실 대응, 지연 시간 최적화 기능을 제공한다.
- Echo Cancellation, Noise Suppression, Automatic Gain Control 적용이 가능하다.
- Android와 PC 양쪽에서 구현 가능한 SDK와 라이브러리가 존재한다.
- 향후 영상 통화로 확장할 수 있다.

### 7.3 Signaling 필요성

WebRTC는 실제 음성 데이터 전송은 Peer-to-Peer로 수행하지만, 연결을 만들기 위해서는 Signaling 과정이 필요하다.

Signaling Server는 다음 데이터를 교환한다.

- Session 생성 요청
- SDP Offer
- SDP Answer
- ICE Candidate
- 연결 상태
- 통화 시작 및 종료 이벤트

본 프로젝트에서는 관제 PC가 Signaling Server를 실행하고, Android 앱이 WebSocket으로 접속하는 구조를 우선 적용한다.

---

## 8. Control PC Software Design

관제 PC 소프트웨어는 서버 기능과 사용자 인터페이스 기능을 함께 수행한다.

### 8.1 구성 요소

| 구성 요소 | 역할 |
| --- | --- |
| FastAPI Server | 상태 확인, 설정 조회, 간단한 REST API 제공 |
| WebSocket Signaling Server | WebRTC 연결 제어 메시지 교환 |
| Voice Session Manager | Android 장치와 관제 PC 간 통화 세션 관리 |
| ROS2 Bridge | 로봇 시스템 이벤트와 음성 통신 상태 연동, 향후 통합 항목 |
| Integrated Control GUI | `admin_dashboard` Monitor 화면에 통합된 음성 통신 패널 |
| Standalone Control GUI | `Communication_System/frontend/control_dashboard` 단독 음성 테스트 화면 |

### 8.2 관제 GUI 요구사항

관제 PC GUI는 다음 기능을 제공해야 한다.

- Android 장치 연결 상태 표시
- 후발 로봇 ID 또는 장치 ID 표시
- 통화 가능 상태 표시
- 통화 시작 버튼
- 통화 종료 버튼
- 마이크 입력 상태 표시
- 스피커 출력 상태 표시
- 연결 끊김 경고
- 재연결 상태 표시
- 신원 확인 이벤트와 음성 연결 상태 표시

현재 구현은 PyQt가 아니라 브라우저 기반 UI로 구성되어 있다. 단독 음성 테스트는 `Communication_System/frontend/control_dashboard`를 사용하고, 실제 관제 통합 테스트는 `admin_dashboard`의 Monitor 화면에 추가된 `음성 통신` 패널을 사용한다.

운용 시에는 서버 프로세스와 관제 UI 프로세스를 분리한다.

```text
Voice Server:
Communication_System/scripts/run_voice_server.sh
또는
Communication_System/scripts/run_voice_server_https.sh

Admin Dashboard:
admin_dashboard Vite dev server 또는 배포된 정적 빌드
```

---

## 9. Android Application Design

Android 단말은 후발 로봇 위에 올려놓는 모바일 또는 태블릿에서 실행된다. 현재 구현은 네이티브 APK가 아니라 Android Chrome에서 `Communication_System/frontend/android_device` 브라우저 화면을 여는 방식이다. 로봇 본체에 별도 스피커와 마이크를 부착하지 않고 Android 단말의 내장 마이크와 스피커를 사용한다.

### 9.1 핵심 기능

- 관제 PC IP 및 포트 설정
- WebSocket Signaling Server 접속
- WebRTC Peer Connection 생성
- 마이크 권한 요청
- 네트워크 권한 사용
- 음성 송신
- 음성 수신
- 스피커 출력
- 연결 상태 표시
- 통화 상태 표시
- 자동 재연결
- 브라우저 새로고침 또는 앱 재시작 후 재접속

### 9.2 권장 UI

현장 운용 앱은 복잡한 화면보다 상태 확인이 쉬운 화면이 적합하다.

필수 표시 항목은 다음과 같다.

- 서버 연결 상태
- 통화 연결 상태
- 마이크 활성 상태
- 스피커 활성 상태
- 배터리 상태
- WiFi 상태
- 후발 로봇 또는 장치 ID

버튼은 최소화한다.

- Connect
- Start Call
- End Call
- Reconnect
- Settings

현장에서는 사람이 직접 조작하지 못할 가능성이 높으므로, 향후 기본 동작은 화면 실행 후 자동 서버 연결과 자동 통화 대기 상태 진입으로 확장한다. 현재 브라우저 UI에서는 Android 화면의 `Connect` 버튼으로 서버 연결을 시작한다.

### 9.3 배포 방식

현재 브라우저 기반 구현은 별도 APK 배포가 필요 없다. Android Chrome에서 Voice Server가 제공하는 `/android` 페이지를 열어 사용한다.

향후 네이티브 Android 앱으로 전환할 경우 Google Play Store를 사용하지 않고 내부망 또는 ADB 기반 직접 설치 방식을 사용할 수 있다.

연구 개발 및 재난 대응 환경에서는 폐쇄망 또는 내부망 배포가 더 적합하므로 APK 직접 설치 방식을 사용한다.

향후 APK 배포 방식은 다음을 지원한다.

- USB 파일 복사 후 수동 설치
- ADB 설치
- 내부 파일 서버에서 APK 다운로드
- 향후 OTA 업데이트 확장

예시 설치 명령은 다음과 같다.

```bash
adb install rescue-voice-app.apk
```

---

## 10. ROS2 Integration Design

ROS2는 음성 데이터 자체를 전송하지 않고, 음성 통신 상태와 로봇 이벤트를 연결하는 역할을 수행한다.

초기 후보 Topic은 다음과 같다.

| Topic | 방향 | 설명 |
| --- | --- | --- |
| `/victim_call_request` | Robot 또는 Control -> Voice Server | 구조 대상자 통화 요청 |
| `/audio_connected` | Voice Server -> ROS2 | 음성 통화 연결 완료 |
| `/audio_disconnected` | Voice Server -> ROS2 | 음성 통화 종료 또는 끊김 |
| `/audio_status` | Voice Server -> ROS2 | 현재 음성 통신 상태 |

연동 예시는 다음과 같다.

1. 후발 로봇이 목표 지점에 도착한다.
2. 얼굴 탐지 또는 신원 확인 이벤트가 발생한다.
3. ROS2에서 `/victim_call_request` 이벤트를 발생시킨다.
4. Voice Server가 Android 장치와 통화 세션을 준비한다.
5. WebRTC 연결이 완료되면 `/audio_connected`를 발행한다.
6. 통화 종료 또는 끊김이 발생하면 `/audio_disconnected`를 발행한다.

실제 Topic 이름과 메시지 타입은 기존 로봇 시스템의 네이밍 규칙과 메시지 구조를 확인한 뒤 확정해야 한다.

---

## 11. Technology Stack

### 11.1 Control PC

- Ubuntu 22.04
- ROS2 Humble
- Python 3
- FastAPI
- WebSocket
- Browser WebRTC API
- React admin dashboard integration
- Vite development server
- PulseAudio 또는 PipeWire

### 11.2 Android Device

- Android Chrome 기반 브라우저 UI
- Android 11 이상 권장
- Browser WebRTC API
- Microphone Permission
- WiFi Network

네이티브 Android 앱, Kotlin, Android Studio, Android WebRTC SDK는 향후 APK 전환 시 사용할 후보 기술이다.

### 11.3 Voice Communication

- WebRTC
- Opus Codec
- Echo Cancellation
- Noise Suppression
- Automatic Gain Control

---

## 12. Development Strategy

개발은 한 번에 전체 로봇 시스템에 통합하지 않고, 통신 기능을 단계적으로 검증한 뒤 로봇 시스템에 결합한다.

### Phase 0. Requirements Definition

- Full Duplex 통신 방식 확정
- 음성 통신 범위 정의
- 관제 PC와 Android 장치의 역할 정의
- 네트워크 구조 확정
- 시스템 요구사항 문서 작성

### Phase 1. Hardware Validation

- 사용할 Android 모바일 또는 태블릿 선정
- Android 버전 확인
- WiFi 성능 확인
- 마이크 품질 측정
- 스피커 출력 측정
- 3m, 5m, 10m 거리 음성 테스트

### Phase 2. Network Setup

- 관제 PC, 선발 로봇, 후발 로봇, Android 장치를 동일 WiFi에 연결
- IP 할당 방식 확정
- Ping Test 수행
- Bandwidth Test 수행
- WiFi 재연결 및 자동 복구 테스트 수행

### Phase 3. WebRTC Infrastructure

- Python 개발 환경 구성
- FastAPI 서버 구축
- WebSocket Signaling 구현
- SDP Offer, Answer 처리
- ICE Candidate 처리
- PC와 Android 브라우저 사이의 음성 통화 Prototype 구현
- 지연 시간과 패킷 손실 측정

### Phase 4. Android Browser Device UI

- Android Chrome 기반 현장 음성 단말 화면 구현
- Browser WebRTC API 적용
- 마이크 입력 및 스피커 출력 구현
- 관제 PC Signaling Server 접속 구현
- PC와 Android 사이의 음성 통화 구현
- USB + ADB reverse 테스트
- WiFi HTTPS 및 CA 인증서 테스트

### Phase 5. Control PC Software

- 통화 세션 관리
- standalone 관제 음성 UI 구현
- `admin_dashboard` Monitor 화면 음성 통신 패널 통합
- 마이크 및 스피커 장치 선택
- Echo Cancellation, Noise Suppression, Automatic Gain Control 적용
- 연결 끊김 및 재연결 처리

### Phase 6. ROS2 Integration

- ROS2 Topic 및 Message 정의
- Voice Server와 ROS2 Bridge 연동
- 통화 요청 이벤트 처리
- 음성 연결 상태를 로봇 시스템에 전달

### Phase 7. Robot Integration

- 후발 로봇 위에 Android 장치 배치
- 전원 공급 구성
- 앱 자동 실행 구성
- 이동, 얼굴 탐지, 신원 확인 이벤트와 음성 통신 연결

### Phase 8. Deployment

- 브라우저 기반 접속 절차 문서화
- USB + ADB reverse 테스트 절차 문서화
- HTTPS 인증서 생성 및 Android CA 설치 절차 문서화
- 향후 APK 배포 절차 문서화
- 관제 서버 IP 설정 절차 정의
- 재부팅 후 자동 실행 테스트
- 현장 운용 설정 적용

### Phase 9. Field Testing

- 음성 품질 평가
- 지연 시간 측정
- 통신 안정성 평가
- 현장 소음 환경 테스트
- 이동 중 통화 테스트
- WiFi 약화 환경 테스트

### Phase 10. Final Validation

- 인명 탐지부터 실시간 음성 대화까지 전체 시나리오 검증
- 장애 상황 검증
- 복구 상황 검증
- 최종 시연 수행

---

## 13. Device Hardening

현장 운용을 위해 Android 장치에는 다음 설정이 필요하다.

- 화면 자동 꺼짐 비활성화
- 절전 모드 비활성화
- 배터리 최적화 비활성화
- WiFi 자동 재연결
- 앱 자동 실행
- 앱 충돌 후 자동 재시작
- 서버 연결 실패 시 재시도
- 통화 끊김 발생 시 재연결
- 장시간 실행 안정성 테스트

관제 PC에는 다음 설정이 필요하다.

- 고정 IP 설정
- 방화벽 포트 허용
- 서버 자동 실행
- 로그 저장 경로 설정
- 마이크 및 스피커 장치 고정
- ROS2 환경 자동 로드

---

## 14. Test and Validation Criteria

### 14.1 기능 검증

- Android 앱이 관제 PC 서버에 접속해야 한다.
- WebRTC 연결이 정상적으로 생성되어야 한다.
- Android에서 말한 음성이 PC에서 들려야 한다.
- PC에서 말한 음성이 Android에서 들려야 한다.
- 통화 시작과 종료가 정상 동작해야 한다.
- 연결 끊김 후 재연결이 가능해야 한다.
- ROS2 이벤트와 음성 연결 상태가 동기화되어야 한다.

### 14.2 성능 검증

초기 목표 성능은 다음과 같다.

| 항목 | 목표 |
| --- | --- |
| 음성 지연 시간 | 300ms 이하 권장 |
| 통화 연결 시간 | 5초 이하 권장 |
| 음성 테스트 거리 | 3m, 5m, 10m |
| 연속 통화 시간 | 30분 이상 |
| WiFi 재연결 복구 | 자동 복구 |
| 앱 비정상 종료 | 재실행 또는 수동 복구 가능 |

### 14.3 현장 검증

현장 테스트에서는 다음 항목을 확인한다.

- 로봇 이동 중 통화 품질
- 구조 대상자 위치에서 마이크 수음 품질
- 스피커 출력 크기
- 로봇 모터 소음이 음성에 미치는 영향
- 관제 PC에서 대상자 음성 인식 가능 여부
- 현장 WiFi 신호 약화 시 통화 유지 여부
- 끊김 발생 후 복구 가능 여부

---

## 15. Risk and Mitigation

| 위험 요소 | 영향 | 대응 방안 |
| --- | --- | --- |
| WiFi 신호 약화 | 음성 끊김, 연결 실패 | AP 위치 조정, 재연결 로직, 현장 대역폭 테스트 |
| 현장 소음 | 음성 인식 어려움 | Noise Suppression, 지향성 마이크, 스피커 출력 조정 |
| 하울링 또는 Echo | 통화 품질 저하 | Echo Cancellation, 마이크와 스피커 위치 조정 |
| Android 절전 정책 | 앱 중지, 네트워크 끊김 | 배터리 최적화 해제, 화면 유지, 자동 실행 |
| 방화벽 또는 AP 격리 | PC와 Android 연결 실패 | 포트 허용, Client Isolation 비활성화 |
| ROS2 연동 불일치 | 이벤트 동기화 실패 | Topic과 Message 타입 사전 정의 |
| 기기별 WebRTC 차이 | Android 앱 동작 차이 | 대상 태블릿 선정 후 장치별 검증 |

---

## 16. Success Criteria

최종 성공 기준은 다음 시나리오가 연속적으로 수행되는 것이다.

```text
선발 로봇 인명 탐지
-> 위치 정보와 Map 전송
-> 관제 PC에서 후발 로봇 임무 생성
-> 후발 로봇 목표 위치 이동
-> 얼굴 탐지
-> 신원 확인
-> Android 장치와 관제 PC 음성 연결
-> 구조 대상자와 관제 인원의 실시간 대화 성공
```

성공 판정 조건은 다음과 같다.

- 관제 PC와 Android 장치가 동일 WiFi에서 자동 연결된다.
- 통화 연결 후 양방향 음성이 정상 송수신된다.
- 구조 대상자가 별도 조작 없이 로봇 장치를 통해 말할 수 있다.
- 관제 인원이 PC에서 대상자 음성을 듣고 응답할 수 있다.
- 통화 상태가 관제 PC와 Android 장치에 표시된다.
- 통화 상태가 ROS2 시스템과 동기화된다.
- 현장 테스트에서 실사용 가능한 음질과 안정성을 확보한다.

---

## 17. Future Extensions

향후 확장 가능한 기능은 다음과 같다.

- 영상 통화
- 다자간 통화
- LTE 또는 5G 외부망 통신
- STUN/TURN 서버 기반 외부 네트워크 연결
- AI 음성 분석
- 구조 대상자 음성 자동 기록
- TTS 기반 자동 안내 방송
- 긴급 호출 버튼
- 관제 PC 다중 로봇 음성 세션 관리
- OTA 기반 Android 앱 업데이트
