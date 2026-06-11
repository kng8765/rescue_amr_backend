# WiFi HTTPS Android Voice Test Guide

## 1. Why This Step Is Needed

USB + `adb reverse` 테스트에서는 Android Chrome이 `http://127.0.0.1:8000/android`를 보안 출처로 취급하므로 마이크 권한을 사용할 수 있다.

USB 없이 같은 WiFi에서 접속하면 주소가 다음처럼 바뀐다.

```text
http://<CONTROL_PC_IP>:8000/android
```

이 주소는 Android Chrome에서 보안 출처가 아니므로 `getUserMedia()` 마이크 권한이 막힐 수 있다. 따라서 USB 없이 브라우저 WebRTC 음성 테스트를 하려면 HTTPS 구성이 필요하다.

## 2. Prerequisites

- 관제 PC와 Android 단말이 같은 WiFi에 연결되어 있어야 한다.
- Android에서 관제 PC IP로 접속 가능해야 한다.
- 관제 PC 방화벽이 `8000/tcp` 접속을 허용해야 한다.
- Android Chrome에서 인증서를 신뢰해야 한다.

## 3. Find Control PC IP

관제 PC 터미널에서 IP를 확인한다.

```bash
hostname -I
```

예시:

```text
192.168.0.10
```

여러 IP가 나오면 Android와 같은 WiFi 대역의 IP를 사용한다.

## 4. Generate HTTPS Certificate

예시 IP가 `192.168.0.10`이면:

```bash
cd /home/hig/rescue_amr_project
Communication_System/scripts/generate_https_cert.sh 192.168.0.10
```

생성 파일:

- `Communication_System/certs/voice-local-ca.crt`
- `Communication_System/certs/voice-local-ca.key`
- `Communication_System/certs/voice-server.crt`
- `Communication_System/certs/voice-server.key`

Android에는 `voice-local-ca.crt`를 설치한다. `voice-server.crt`는 서버가 사용하는 인증서이며 Android에 직접 설치하지 않는다.

## 5. Start HTTPS Server

```bash
cd /home/hig/rescue_amr_project
Communication_System/scripts/run_voice_server_https.sh
```

서버 로그에 다음처럼 표시된다.

```text
Uvicorn running on https://0.0.0.0:8000
```

## 6. Android Certificate Trust

Android Chrome에서 로컬 테스트 CA를 신뢰하지 않으면 마이크 권한 또는 페이지 접속이 막힐 수 있다.

이 경우 `voice-local-ca.crt`를 Android로 복사한 뒤 CA 인증서로 설치한다.

ADB 사용 예시:

```bash
adb push Communication_System/certs/voice-local-ca.crt /sdcard/Download/voice-local-ca.crt
```

Android에서:

1. 설정
2. 보안 및 개인정보 보호
3. 기타 보안 설정
4. 기기 저장공간에서 인증서 설치
5. CA 인증서 설치 선택
6. `voice-local-ca.crt` 선택

중요:

- “개인 인증서”, “VPN 및 앱 사용자 인증서”, “WiFi 인증서”로 설치하면 개인키를 요구할 수 있다.
- 이 테스트에서 설치해야 하는 것은 개인키가 필요한 사용자 인증서가 아니라 CA 인증서이다.
- Android가 강하게 경고하는 것은 정상이다. 테스트 후에는 설치한 CA 인증서를 삭제한다.

Android 버전과 제조사 UI에 따라 메뉴 이름은 다를 수 있다.

## 7. Open Pages

관제 PC 브라우저:

```text
https://127.0.0.1:8000/
```

또는:

```text
https://<CONTROL_PC_IP>:8000/
```

Android Chrome:

```text
https://<CONTROL_PC_IP>:8000/android
```

## 8. Test Procedure

1. PC 관제 화면에서 `Connect`
2. Android 화면에서 `Connect`
3. PC 관제 화면에서 `Create Session`
4. PC 관제 화면에서 `Start Call`
5. 양쪽 마이크 권한 허용
6. USB 없이 음성 송수신 확인

## 9. If HTTPS Still Fails

다음 항목을 확인한다.

- Android와 PC가 같은 WiFi인지 확인
- Android 브라우저에서 `https://<CONTROL_PC_IP>:8000/android` 페이지가 열리는지 확인
- PC 방화벽에서 `8000/tcp` 허용
- 인증서가 Android에 설치 및 신뢰되었는지 확인
- 인증서를 생성할 때 사용한 IP와 실제 접속 IP가 같은지 확인

브라우저 인증서 신뢰 문제가 계속되면 다음 단계는 Android 네이티브 앱으로 전환하는 것이 더 안정적이다.
