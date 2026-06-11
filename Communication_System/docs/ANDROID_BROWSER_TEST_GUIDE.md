# Android Browser Voice Test Guide

## 1. Purpose

본 문서는 관제 PC와 Android 모바일/태블릿 브라우저를 이용해 WebRTC 음성 통화 Prototype을 테스트하기 위한 준비 절차를 정리한다.

현재 구현은 Android 네이티브 APK가 아니라 브라우저 기반 WebRTC 테스트 UI이다.

- 관제 PC 화면: `http://127.0.0.1:8000/`
- Android 단말 화면: `http://127.0.0.1:8000/android` 또는 `https://<CONTROL_PC_IP>:<PORT>/android`

## 2. Important Browser Constraint

Android Chrome에서 `getUserMedia()`로 마이크를 사용하려면 보안 출처가 필요하다.

허용되는 대표 조건:

- `https://...`
- `http://localhost`
- `http://127.0.0.1`

주의:

- `http://<CONTROL_PC_IP>:8000/android`는 같은 WiFi 내부망이라도 일반적으로 보안 출처가 아니므로 Android Chrome에서 마이크 권한이 막힐 수 있다.
- 따라서 초기 테스트는 `adb reverse`로 Android 브라우저에서도 `127.0.0.1:8000`에 접속하는 방식을 권장한다.

## 3. Recommended Test Method: USB + ADB Reverse

### 3.1 Android 설정

Android 단말에서 다음을 설정한다.

1. 개발자 옵션 활성화
2. USB 디버깅 활성화
3. 화면 자동 꺼짐 비활성화 또는 충분히 길게 설정
4. 배터리 절전 모드 비활성화
5. Chrome 사용 권장
6. Chrome의 마이크 권한 허용

### 3.2 PC 설정

PC에 `adb`가 필요하다.

Ubuntu 예시:

```bash
sudo apt update
sudo apt install android-tools-adb
```

Android 단말을 USB로 연결한 뒤 장치 인식 확인:

```bash
adb devices
```

Android 화면에 USB 디버깅 허용 팝업이 나오면 허용한다.

### 3.3 Port Reverse

관제 PC의 `8000` 포트를 Android 단말의 `127.0.0.1:8000`으로 연결한다.

```bash
adb reverse tcp:8000 tcp:8000
```

### 3.4 Server Start

관제 PC에서 서버를 실행한다.

```bash
Communication_System/scripts/run_voice_server.sh
```

### 3.5 Browser Open

관제 PC 브라우저:

```text
http://127.0.0.1:8000/
```

Android Chrome:

```text
http://127.0.0.1:8000/android
```

## 4. Test Procedure

1. 관제 PC 화면에서 `Connect` 클릭
2. Android 화면에서 `Connect` 클릭
3. 관제 PC 화면에서 `Create Session` 클릭
4. 관제 PC 화면에서 `Start Call` 클릭
5. 양쪽 브라우저에서 마이크 권한 요청이 나오면 허용
6. Android 단말과 관제 PC 사이의 음성 송수신 확인
7. 관제 PC 화면에서 `End Call` 클릭

## 5. If USB/ADB Cannot Be Used

USB 연결이나 ADB 사용이 어렵다면 같은 WiFi에서 Android가 관제 PC IP로 접속해야 한다.

예시:

```text
http://192.168.0.10:8000/android
```

하지만 이 방식은 Android Chrome의 마이크 권한이 막힐 가능성이 높다. 이 경우 다음 중 하나가 필요하다.

- HTTPS 개발 서버 구성
- 신뢰 가능한 인증서 설치
- Android 네이티브 앱으로 전환

초기 검증은 ADB reverse 방식을 우선 사용한다.

## 6. Current PC Environment Note

현재 작업 환경에서는 `adb` 명령이 확인되지 않았다. PC + Android 테스트를 진행하려면 `android-tools-adb` 설치가 필요하다.
