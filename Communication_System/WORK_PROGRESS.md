# WORK PROGRESS

## Purpose

이 파일은 `Communication_System` 작업을 시작하기 전에 반드시 먼저 읽는 Warming-up 문서이다.

`README.md`는 시스템 개요를 설명하고, `TODO_LIST.md`는 전체 수행 항목을 단계별로 정리한다.
본 문서는 현재까지 완료된 작업, 진행 중인 작업, 다음에 수행할 작업, 작업 중 발생한 이슈를 간단히 기록하여 다음 작업자가 빠르게 상황을 파악하도록 돕는다.

---

## Mandatory Work Rule

모든 작업을 시작하기 전에 다음 순서로 문서를 확인한다.

1. `WORK_PROGRESS.md`
2. `README.md`
3. `TODO_LIST.md`

작업을 마친 뒤에는 필요하면 본 문서의 완료 작업, 진행 작업, 이슈, 다음 작업 항목을 갱신한다.

---

## Current Project Status

현재 프로젝트는 재난 현장 다중 로봇 시스템에 실시간 양방향 음성 통신 기능을 추가하기 위한 초기 설계 단계이다.

기존 전체 시스템 흐름은 다음과 같다.

1. 선발 로봇이 SLAM 기반 Mapping 수행
2. 현장에서 사람 발견 시 위치 정보 저장
3. Map 및 위치 정보를 관제 PC로 전송
4. 관제 PC가 후발 로봇에 목표 위치 송출
5. 후발 로봇이 대상자 위치로 이동
6. 얼굴 탐지 및 관제 PC와 통신하여 신원 확인
7. 후발 로봇과 함께 운용되는 Android 모바일 또는 태블릿을 통해 구조 대상자와 관제 인원이 실시간 음성 통신

로봇 본체에 별도 스피커와 마이크를 부착하기 어려우므로, Android 모바일 또는 태블릿을 후발 로봇 위에 올려놓고 현장 음성 단말로 운용하기로 결정했다.

---

## Completed Work

- [x] 프로젝트 목적 정리
- [x] 전체 시스템 개요 작성
- [x] 관제 PC, 선발 로봇, 후발 로봇, Android 태블릿의 역할 초안 정리
- [x] WebRTC 기반 실시간 음성 통신 구조 초안 정리
- [x] Android APK 직접 배포 전략 초안 정리
- [x] 전체 개발 단계별 TODO 목록 작성
- [x] 작업 진행 상태 관리를 위한 `WORK_PROGRESS.md` 생성
- [x] `README.md`를 상세 보고서 형식으로 확장
- [x] 동일 WiFi 기반 PC와 Android 장치 연결 구조 초안 작성
- [x] WebRTC, WebSocket, FastAPI, ROS2 Bridge 역할 초안 작성
- [x] 테스트 및 검증 기준 초안 작성
- [x] `SYSTEM_REQUIREMENTS.md` 작성
- [x] `TODO_LIST.md` Phase 0 요구사항 정의 항목 완료 처리
- [x] `HARDWARE_VALIDATION_REPORT.md` 작성
- [x] Android 버전 확인 결과 반영: Android 16
- [x] WiFi 성능 확인 결과 반영: 245 Mb/s, 5.3 GHz
- [x] Android 장치 로봇 장착 불가 이슈 문서화
- [x] Android 단말 운용 방식 확정: 후발 로봇 위에 올려놓고 운용
- [x] Phase 2 `NETWORK_CONFIGURATION.md` 작성
- [x] Phase 3 FastAPI/WebSocket Signaling Server 기본 구현
- [x] Offer, Answer, ICE Candidate relay 기본 처리 구현
- [x] Signaling session manager 단위 테스트 추가
- [x] 정적 프론트엔드 기반 작성: 관제 PC 대시보드
- [x] 정적 프론트엔드 기반 작성: Android 단말 화면
- [x] FastAPI, uvicorn, pydantic, websockets 설치 완료
- [x] Signaling Server 실행 및 HTTP health 검증
- [x] WebSocket Signaling Flow 자동 테스트 통과
- [x] 브라우저 WebRTC Offer/Answer/ICE 코드 작성

---

## In Progress

- [x] PC와 Android 태블릿 간 음성 통신 구조 검토
- [x] 관제 PC Voice Server 및 Signaling Server 역할 구체화
- [ ] 실제 장비와 네트워크 환경 기반 요구사항 확정
- [x] Android 장치 물리적 배치 방식 재결정
- [ ] PC ↔ PC WebRTC audio prototype 구현
- [x] FastAPI/uvicorn/pydantic 설치 완료 후 Signaling Server import 검증
- [x] Signaling Server 실행 및 프론트엔드 WebSocket 연결 검증
- [ ] 실제 브라우저 2대 또는 탭 2개에서 음성 통화 검증

---

## Planned Work

우선순위가 높은 다음 작업은 아래와 같다.

- [ ] Android 태블릿 또는 모바일 실제 기종 확정
- [ ] 마이크 및 스피커 품질 실측
- [ ] 3m, 5m, 10m 음성 테스트 수행
- [x] 로봇 장착 대안 결정: 후발 로봇 위에 Android 단말 배치
- [ ] 실제 WiFi AP, IP 대역, 고정 IP 또는 DHCP 예약 방식 확정
- [ ] WebRTC, WebSocket, FastAPI, aiortc 기반 통신 구조 상세 설계 문서 작성
- [ ] PC ↔ PC 음성 통신 Prototype 구현 계획 수립
- [ ] PC ↔ Android 음성 통신 구현 계획 수립
- [ ] ROS2와 음성 통신 시스템의 연동 지점 정의
- [ ] 현장 테스트 기준 수립

---

## Known Issues

- 아직 실제 Android 태블릿 또는 모바일 기종이 확정되지 않았다.
- WiFi 공유기, 네트워크 대역, 고정 IP 사용 여부가 확정되지 않았다.
- Android 버전은 Android 16으로 확인되었다.
- WiFi 성능은 245 Mb/s, 5.3 GHz로 확인되었다.
- Android 장치의 로봇 장착 가능성이 없는 것으로 확인되어 기존 장착형 설계와 충돌한다.
- WebRTC Signaling Server 기본 relay 구현은 완료되었고 자동 테스트를 통과했다.
- 브라우저 WebRTC media 송수신 코드는 추가되었지만 실제 장비 또는 브라우저 2개에서 음성 품질 검증이 필요하다.
- FastAPI 관련 Python 패키지 설치와 서버 실행 검증은 완료되었다.
- 관제 PC GUI 구현 방식은 PyQt로 가정되어 있으나 상세 화면 설계가 필요하다.
- ROS2 Topic 이름은 TODO 단계의 후보이며 실제 기존 로봇 시스템과의 호환성 검토가 필요하다.
- 현장 소음, 마이크 품질, 스피커 출력, Echo Cancellation 성능은 실측이 필요하다.

---

## Work Log

### 2026-06-10

- `README.md`와 `TODO_LIST.md` 확인
- 프로젝트가 초기 설계 및 문서화 단계임을 확인
- 모든 작업 전 확인할 Warming-up 문서로 `WORK_PROGRESS.md` 생성
- `README.md`를 상세 보고서 형식으로 확장
- 구조 시나리오, 시스템 참여자, 동일 WiFi 네트워크 구조, WebRTC 기반 음성 통신 방식, 관제 PC 소프트웨어, Android 앱, ROS2 연동, 테스트 기준, 위험 요소를 문서화
- `SYSTEM_REQUIREMENTS.md` 작성
- `TODO_LIST.md`의 Phase 0 요구사항 정의 항목을 완료 상태로 갱신
- 실제 장비 모델, IP 대역, ROS2 Topic 상세, GUI 화면 구성은 Open Decision으로 유지
- 사용자 제공 하드웨어 정보를 반영
- Android 버전 Android 16 확인
- WiFi 성능 245 Mb/s, 5.3 GHz 확인
- 모바일 내장 마이크 및 내장 스피커 사용 계획 기록
- 로봇 장착 가능성 없음으로 인한 설계 리스크 기록
- `HARDWARE_VALIDATION_REPORT.md` 작성
- `TODO_LIST.md`의 Phase 1 중 Android 버전 확인, WiFi 성능 확인, Hardware Validation Report 작성 항목 완료 처리
- Android 단말을 후발 로봇 위에 올려놓고 운용하기로 결정
- `README.md`, `SYSTEM_REQUIREMENTS.md`, `HARDWARE_VALIDATION_REPORT.md`에 확정된 단말 운용 방식을 반영
- `docs/NETWORK_CONFIGURATION.md` 작성
- `docs/WEBRTC_PROTOTYPE_PLAN.md` 작성
- `control_pc/voice_server`에 FastAPI/WebSocket 기반 Signaling Server 기본 구현 추가
- `session_create`, `offer`, `answer`, `ice_candidate`, `call_start`, `call_end`, `heartbeat` 처리 추가
- `control_pc/tests/test_session_manager.py` 단위 테스트 추가
- `frontend/control_dashboard` 정적 관제 대시보드 UI 추가
- `frontend/android_device` 정적 Android 단말 UI 추가
- `frontend/shared.js` WebSocket signaling client 기반 추가
- FastAPI, uvicorn, pydantic, websockets 설치 완료
- `voice_server.app` import 검증 완료
- `session_manager` 기본 단위 테스트 재확인 완료
- FastAPI에서 `/`, `/android`, `/frontend/*` 정적 프론트엔드 서빙 추가
- 관제 대시보드에 WebRTC Offer 생성, 마이크 송신, remote audio 수신 코드 추가
- Android 단말 화면에 WebRTC Answer 생성, 마이크 송신, remote audio 수신 코드 추가
- `scripts/signaling_flow_test.py` 추가 및 WebSocket relay 검증 통과
- `scripts/run_voice_server.sh` 추가
- `docs/ANDROID_BROWSER_TEST_GUIDE.md` 작성
- `scripts/android_adb_reverse_check.sh` 추가
- USB 없이 Android 브라우저 테스트를 위한 HTTPS 실행 옵션 추가
- `scripts/generate_https_cert.sh` 추가
- `scripts/run_voice_server_https.sh` 추가
- `docs/WIFI_HTTPS_ANDROID_TEST_GUIDE.md` 작성

---

## Next Recommended Action

다음 작업자는 실제 브라우저에서 PC ↔ Android WebRTC 음성 통화를 검증하는 것이 좋다.

현재 Signaling Server relay와 브라우저 WebRTC Offer/Answer/ICE 코드는 구현되어 있으므로 다음 순서로 진행한다.

- Signaling Server 실행
- 관제 PC에서 `http://<CONTROL_PC_IP>:8000/` 접속
- Android 단말은 USB + ADB reverse 방식으로 `http://127.0.0.1:8000/android` 접속 권장
- ADB가 없으면 `android-tools-adb` 설치 후 `adb reverse tcp:8000 tcp:8000` 설정
- USB 없이 테스트하려면 `generate_https_cert.sh <CONTROL_PC_IP>`로 인증서를 만들고 `run_voice_server_https.sh`로 HTTPS 서버 실행
- 양쪽에서 WebSocket 연결
- 관제 대시보드에서 Session 생성 후 Start Call
- 양쪽 마이크 권한 허용 및 실제 음성 송수신 확인
- 지연 시간과 패킷 손실 측정
- Android Studio 프로젝트 생성 및 동일 signaling protocol 연동

병행해서 실제 Android 기종 확정, 마이크 및 스피커 실측, 3m/5m/10m 음성 테스트를 진행한다.
