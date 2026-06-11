# TODO LIST

## Phase 0. Requirements Definition

- [x] Full Duplex 방식 확정
- [x] 음성 통신 범위 정의
- [x] 태블릿 역할 정의
- [x] 관제 PC 역할 정의
- [x] 네트워크 구조 확정
- [x] System Requirement Document 작성

---

## Phase 1. Hardware Validation

- [ ] Android 태블릿 선정
- [x] Android 버전 확인
- [x] WiFi 성능 확인
- [ ] 마이크 품질 측정
- [ ] 스피커 품질 측정
- [ ] 3m 음성 테스트
- [ ] 5m 음성 테스트
- [ ] 10m 음성 테스트
- [x] Hardware Validation Report 작성

---

## Phase 2. Network Setup

- [ ] 관제 PC 연결
- [ ] 선발 로봇 연결
- [ ] 후발 로봇 연결
- [ ] 태블릿 연결
- [ ] Ping Test
- [ ] Bandwidth Test
- [ ] WiFi 재연결 테스트
- [ ] 자동 복구 테스트
- [x] Network Configuration Document 작성

---

## Phase 3. WebRTC Infrastructure

- [ ] Python 환경 구성
- [ ] aiortc 설치
- [x] FastAPI 구축
- [x] WebSocket 구축
- [x] Offer 처리
- [x] Answer 처리
- [x] ICE Candidate 처리
- [x] 브라우저 WebRTC Offer/Answer/ICE 흐름 구현
- [x] WebSocket Signaling Flow 자동 테스트 작성
- [x] Signaling Server 실행 검증
- [ ] PC 브라우저 ↔ Android 브라우저 음성 통화 성공
- [ ] PC ↔ PC 음성 통화 성공
- [ ] 지연 시간 측정
- [ ] 패킷 손실 측정
- [ ] WebRTC Prototype 완료

---

## Phase 4. Android Application

### Development

- [ ] Android Studio 프로젝트 생성
- [ ] AudioRecord 구현
- [ ] AudioTrack 구현
- [ ] Android WebRTC SDK 적용
- [ ] 음성 송신 구현
- [ ] 음성 수신 구현

### Packaging

- [ ] Application ID 결정
- [ ] App Icon 제작
- [ ] Version Name 정의
- [ ] Version Code 정의
- [ ] APK 서명 키 생성
- [ ] Release APK 생성

### Installation Test

- [ ] APK 설치 테스트
- [ ] 앱 실행 테스트
- [ ] 마이크 권한 확인
- [ ] 네트워크 권한 확인
- [x] Android 브라우저 테스트 절차 문서 작성
- [x] ADB reverse 설정 스크립트 작성
- [x] WiFi HTTPS Android 테스트 절차 문서 작성
- [x] HTTPS 개발 인증서 생성 스크립트 작성
- [ ] WebRTC 연결 확인

- [ ] Android Voice App v1 완료
- [ ] Release Build Guide 작성

---

## Phase 5. Control PC Software

- [ ] 사용자 관리
- [ ] 연결 관리
- [ ] 세션 관리
- [x] 정적 관제 대시보드 UI 기반 작성
- [x] 관제 대시보드 WebRTC Offer 생성 구현
- [ ] GUI 구현
- [ ] Echo Cancellation 적용
- [ ] Noise Suppression 적용
- [ ] Automatic Gain Control 적용
- [ ] Control Station Application v1 완료

---

## Phase 6. ROS2 Integration

- [ ] /audio_connected 정의
- [ ] /audio_disconnected 정의
- [ ] /victim_call_request 정의
- [ ] ROS2 ↔ Voice Server 연동
- [ ] 상태 동기화 구현
- [ ] ROS2 Communication Module 완료

---

## Phase 7. Robot Integration

- [x] 후발 로봇 위 Android 단말 배치 방식 확정
- [ ] 후발 로봇 위 Android 단말 안정성 확인
- [ ] 전원 공급 구성
- [ ] 네트워크 자동 연결
- [ ] 연결 상태 UI 구현
- [ ] 통화 상태 UI 구현
- [x] Android 단말 정적 UI 기반 작성
- [x] Android 단말 WebRTC Answer 생성 구현
- [ ] 신원 확인 이벤트 연동
- [ ] 통화 요청 기능 연동
- [ ] Robot Integration 완료

---

## Phase 8. Deployment

- [ ] APK 배포 절차 문서 작성
- [ ] USB 설치 테스트
- [ ] ADB 설치 테스트
- [ ] 내부 서버 다운로드 테스트
- [ ] 관제 서버 IP 설정
- [ ] 자동 실행 설정
- [ ] 절전 모드 비활성화
- [ ] WiFi 자동 연결 설정
- [ ] 재부팅 후 자동 실행 테스트
- [ ] Deployment Guide 작성
- [ ] Installation Guide 작성

### Device Hardening

- [ ] 화면 자동 꺼짐 비활성화
- [ ] 배터리 최적화 비활성화
- [ ] 앱 자동 실행 설정
- [ ] WiFi 자동 재연결 설정
- [ ] 앱 충돌 복구 기능 구현

---

## Phase 9. Field Testing

- [ ] 음성 품질 평가
- [ ] 지연 시간 측정
- [ ] 통신 안정성 평가
- [ ] 소음 환경 테스트
- [ ] 이동 중 통화 테스트
- [ ] WiFi 약화 환경 테스트
- [ ] Field Test Report 작성

---

## Phase 10. Final Validation

- [ ] 인명 탐지
- [ ] 위치 전송
- [ ] 후발 로봇 이동
- [ ] 얼굴 탐지
- [ ] 신원 확인
- [ ] 음성 연결
- [ ] 실시간 대화
- [ ] 전체 시나리오 성공
- [ ] 장애 상황 검증
- [ ] 복구 상황 검증
- [ ] Final Demonstration 완료
- [ ] Final Report 작성

---

# Milestones

- [ ] M1 : PC ↔ PC 음성 통화 성공
- [ ] M2 : PC ↔ Android 음성 통화 성공
- [ ] M3 : ROS2 연동 완료
- [ ] M4 : 후발 로봇 통합 완료
- [ ] M5 : 현장 테스트 완료
- [ ] M6 : 최종 시연 완료
