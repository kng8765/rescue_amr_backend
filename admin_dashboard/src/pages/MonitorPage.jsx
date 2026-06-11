import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AresShell from "../AresShell";
import { navigate } from "../aresRouting";
import useClock from "../useClock";

const API_BASE = "http://localhost:8001/api";
// 로봇 인덱스(0-based) → WebRTC 브릿지 포트 (로봇별 1포트 — 견고한 분리 구조)
// 브릿지 실행(정본): ros2 launch ares_bridges ares_bridge.launch.py robot_id:=<id> port:=<port>
//   idx0 → port 8002 → 예: robot5(TB_05, 192.168.108.105)
//   idx1 → port 8003 → 예: 두 번째 로봇
// ROS 네트워크(Fast DDS): ROS_DOMAIN_ID=1, RMW=rmw_fastrtps_cpp, ROS_SUPER_CLIENT=True
//   ROS_DISCOVERY_SERVER=";192.168.108.105:11811;" (TB_05) / ";192.168.108.101:11811;" (TB_01)
const WEBRTC_PORT = (idx) => 8002 + idx;
const WEBRTC_BASE = (idx) => `http://localhost:${WEBRTC_PORT(idx)}`;
const ICE_SERVERS = [
  { urls: "stun:stun.l.google.com:19302" },
  { urls: "turn:openrelay.metered.ca:80",  username: "openrelayproject", credential: "openrelayproject" },
  { urls: "turn:openrelay.metered.ca:443", username: "openrelayproject", credential: "openrelayproject" },
];

// ICE candidate 수집 완료까지 대기 (최대 timeoutMs)
function waitForIceGathering(pc, timeoutMs = 1800) {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(tid);
      pc.removeEventListener("icegatheringstatechange", onChange);
      resolve();
    };
    const onChange = () => { if (pc.iceGatheringState === "complete") done(); };
    pc.addEventListener("icegatheringstatechange", onChange);
    const tid = setTimeout(done, timeoutMs);
  });
}
const POLL_INTERVAL = 3000; // 3초 로봇 상태 폴링

function formatDuration(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ─── Ring 차트 (구조율/배터리 평균) ────────────────────────────────────────
function Ring({ percent, tone, label, sub, size = 76 }) {
  const radius = size === 76 ? 30 : 22;
  const center = size / 2;
  const circumference = Math.round(2 * Math.PI * radius);
  const fill = Math.round(((percent ?? 0) / 100) * circumference);
  return (
    <div className="circle-wrap">
      <div className="circle-ring" style={{ width: size, height: size }}>
        <svg width={size} height={size}>
          <circle className="ring-bg" cx={center} cy={center} r={radius} />
          <circle
            className={`ring-fill ${tone}`}
            cx={center} cy={center} r={radius}
            strokeDasharray={`${fill} ${circumference - fill}`}
          />
        </svg>
        <div className="circle-val">
          <span className="circle-num">{percent ?? "—"}%</span>
          <span className="circle-lbl-sm">{label}</span>
        </div>
      </div>
      <div className="ring-label">{sub}</div>
    </div>
  );
}

// ─── 카메라 패널 (WebRTC) ────────────────────────────────────────────────────
function CameraPanel({ title, tone, robotId, robotIndex, cameraTime, onTelemetry }) {
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const [connState, setConnState] = useState("idle"); // idle | connecting | connected | error

  const connect = useCallback(async () => {
    // 이미 연결 중이거나 연결됐으면 스킵
    if (pcRef.current) return;

    setConnState("connecting");
    try {
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      pcRef.current = pc;

      // 영상 트랙을 받기 전에 데이터 채널(telemetry) 선제 개방
      const dataChannel = pc.createDataChannel("telemetry");
      dataChannel.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (onTelemetry) onTelemetry(robotId, data); // 부모에게 실시간 데이터 전달
      };

      // 수신 트랙을 video 엘리먼트에 연결
      pc.ontrack = (e) => {
        const stream = e.streams[0];
        if (videoRef.current && stream) {
          videoRef.current.srcObject = stream;
          // autoPlay만으로 재생 안 되는 브라우저 대응 (팀원 코드 참고)
          void videoRef.current.play().catch(() => {});
          setConnState("connected");
        }
      };

      pc.onconnectionstatechange = () => {
        const s = pc.connectionState;
        if (s === "failed" || s === "disconnected" || s === "closed") {
          setConnState("error");
          pcRef.current = null;
        }
      };

      // 수신 전용 트랜시버 추가
      pc.addTransceiver("video", { direction: "recvonly" });

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      await waitForIceGathering(pc); // ICE candidate 수집 완료 후 전송

      const res = await fetch(`${WEBRTC_BASE(robotIndex)}/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
      });

      if (!res.ok) throw new Error(`시그널링 실패: ${res.status}`);

      const answer = await res.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err) {
      // ERR_CONNECTION_REFUSED = 로봇 미연결 상태 (정상), warn으로 조용히 처리
      const msg = err?.message ?? String(err);
      if (!msg.includes("fetch") && !msg.includes("Failed to fetch")) {
        console.warn(`[WebRTC][${robotId}]`, msg);
      }
      if (pcRef.current) { pcRef.current.close(); pcRef.current = null; }
      setConnState("error");
    }
  }, [robotId, robotIndex]);

  // 컴포넌트 마운트 시 자동 연결 시도
  useEffect(() => {
    connect();
    return () => {
      if (pcRef.current) { pcRef.current.close(); pcRef.current = null; }
    };
  }, [connect]);

  // 에러 상태일 때 5초 뒤 재시도
  useEffect(() => {
    if (connState !== "error") return;
    const id = setTimeout(connect, 5000);
    return () => clearTimeout(id);
  }, [connState, connect]);

  const stateLabel = {
    idle: "대기 중",
    connecting: "연결 중…",
    connected: null, // 연결되면 오버레이 숨김
    error: "연결 실패 — 재시도 중…",
  }[connState];

  return (
    <section className="cell cam-cell">
      <PanelHeader title={title} tone={tone} />
      <div className="cam-feed">
        {/* 실제 WebRTC 비디오 */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{ width: "100%", height: "100%", objectFit: "cover", display: connState === "connected" ? "block" : "none" }}
        />
        {/* 연결 전/실패 오버레이 */}
        {connState !== "connected" && (
          <div className="cam-overlay">
            <div className="cam-static" />
            <div className="cam-no-signal">
              <span className="big">{connState === "error" ? "⚠️" : "📷"}</span>
              {stateLabel}
              <br />{robotId}
            </div>
          </div>
        )}
        <div className="cam-scanline" />
        <div className={`cam-rec ${tone === "orange" ? "orange-rec" : ""}`}>
          <span className="rec-dot" />
          {connState === "connected" ? "녹화중" : "대기"}
        </div>
        <div className="cam-timestamp">{cameraTime}</div>
      </div>
    </section>
  );
}

// ─── 메인 페이지 ─────────────────────────────────────────────────────────────
export default function MonitorPage() {
  const cameraTime = useClock({ hour12: false });
  // 로그인 시각 기준 경과 시간 — sessionStorage에서 읽어 계산
  // 페이지 이동/리마운트와 무관하게 유지됨
  const getElapsed = () => {
    const t = sessionStorage.getItem("ares_login_time");
    return t ? Math.floor((Date.now() - Number(t)) / 1000) : 0;
  };

  const [missionSeconds, setMissionSeconds] = useState(getElapsed);
  const [robots, setRobots] = useState([]);        // rescue_robots 테이블 — 항상 배열
  const [liveTelemetry, setLiveTelemetry] = useState({});
  const [survivorStats, setSurvivorStats] = useState({ confirmed: 0, unknown: 0 });
  const [registeredTotal, setRegisteredTotal] = useState(0); // sync 시 supabase에서 읽어온 등록 총원
  const [robotPaths, setRobotPaths] = useState({});
  const [cameraCoverage, setCameraCoverage] = useState({});
  const [mapWalls, setMapWalls] = useState({}); // SLAM 실시간 점유격자(벽) — WebRTC map

  // 연결 상태 3단계 분리
  // backend: 'ok' | 'error'   — Flask 서버 자체 응답 여부
  // db:      'ok' | 'empty' | 'error'  — 테이블 데이터 존재 여부
  const [connStatus, setConnStatus] = useState({ backend: 'ok', db: 'ok' });

  // 1초마다 로그인 시각 기준 재계산
  useEffect(() => {
    const id = setInterval(() => setMissionSeconds(getElapsed()), 1000);
    return () => clearInterval(id);
  }, []);

  // 로봇 상태 + 생존자 통계 폴링
  const fetchStatus = useCallback(async () => {
    let robotRes, survivorRes, registeredRes;

    // ── 1단계: Flask 서버 응답 여부 ─────────────────────────────────
    try {
      [robotRes, survivorRes, registeredRes] = await Promise.all([
        fetch(`${API_BASE}/robots`),
        fetch(`${API_BASE}/survivor-logs?limit=200`),
        fetch(`${API_BASE}/survivors`),  // 등록 명단(벡터 제외) — 총원 카운트용
      ]);
    } catch {
      // fetch 자체 실패 = 서버가 꺼져있음
      setConnStatus({ backend: 'error', db: 'ok' });
      return;
    }

    // ── 2단계: 로봇 데이터 파싱 ─────────────────────────────────────
    if (robotRes.ok) {
      const data = await robotRes.json();
      // endpoints.py가 { db_status, robots: [] } 형태로 반환
      const robotList = Array.isArray(data.robots) ? data.robots
                      : Array.isArray(data)        ? data
                      : [];
      setRobots(robotList);
      const dbSt = data.db_status ?? (robotList.length === 0 ? 'empty' : 'ok');
      setConnStatus({ backend: 'ok', db: dbSt });
    } else {
      setConnStatus({ backend: 'ok', db: 'error' });
    }

    // ── 3단계: 생존자 로그 (식별/미식별) ─────────────────────────────
    if (survivorRes.ok) {
      const logs = await survivorRes.json();
      const confirmed = new Set(logs.filter((l) => l.survivor_id).map((l) => l.survivor_id)).size;
      const unknown = logs.filter((l) => !l.survivor_id).length;
      setSurvivorStats({ confirmed, unknown });
    }

    // ── 4단계: 등록 총원 (sync된 supabase 신원자 수) ─────────────────
    if (registeredRes && registeredRes.ok) {
      const list = await registeredRes.json();
      setRegisteredTotal(Array.isArray(list) ? list.length : 0);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [fetchStatus]);

  // 라이브 데이터(맵 벽·커버리지·경로·로봇)의 월드 좌표 범위를 자동 산출해 화면에 맞춤.
  // 고정 범위(±음수 미처리) 대신 동적 fit → 원점/음수 좌표도 정확, 종횡비 유지.
  // 화면 맞춤 범위는 '맵/커버리지/경로'(저빈도)로만 산출 — 로봇 pose(5Hz)는 제외해
  // pose 갱신마다 범위·레이어 메모가 무효화되는 걸 방지(로봇은 맵 안에 있으므로 충분).
  const mapBounds = useMemo(() => {
    const xs = [], ys = [];
    const push = (p) => {
      if (p && p.x != null && p.y != null && !isNaN(p.x) && !isNaN(p.y)) { xs.push(p.x); ys.push(p.y); }
    };
    Object.values(mapWalls).forEach(a => (a || []).forEach(push));
    Object.values(cameraCoverage).forEach(a => (a || []).forEach(push));
    Object.values(robotPaths).forEach(a => (a || []).forEach(push));
    if (xs.length === 0) return null;
    const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
    const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
    const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 2) * 1.15; // 여유 15%
    return { cx, cy, span };
  }, [mapWalls, cameraCoverage, robotPaths]);

  // 월드(m) → 화면 % (중심정렬·종횡비 유지·Y축 반전: ROS +y 위 → 화면 위)
  const toX = (x) => (x == null || !mapBounds) ? null : ((x - mapBounds.cx) / mapBounds.span + 0.5) * 100;
  const toY = (y) => (y == null || !mapBounds) ? null : (0.5 - (y - mapBounds.cy) / mapBounds.span) * 100;

  // 지도 레이어를 메모이즈 — 해당 데이터가 바뀔 때만 다시 그림.
  // (pose/배터리 5Hz 갱신 때마다 수천 개 점을 리렌더하던 게 끊김 원인)
  const wallEls = useMemo(() => Object.keys(mapWalls).flatMap(id =>
    (mapWalls[id] || []).map((p, idx) => {
      const x = toX(p.x), y = toY(p.y);
      if (x === null || y === null) return null;
      return <rect key={`${id}-w-${idx}`} x={x - 0.4} y={y - 0.4} width="0.8" height="0.8" fill="rgba(30,41,59,0.9)" />;
    })
  ), [mapWalls, mapBounds]);

  const coverageEls = useMemo(() => Object.keys(cameraCoverage).flatMap(id =>
    (cameraCoverage[id] || []).map((p, idx) => {
      const x = toX(p.x), y = toY(p.y);
      if (x === null || y === null) return null;
      return <rect key={`${id}-cov-${idx}`} x={x - 1.1} y={y - 1.1} width="2.2" height="2.2" fill="rgba(46,204,113,0.18)" />;
    })
  ), [cameraCoverage, mapBounds]);

  const pathEls = useMemo(() => Object.keys(robotPaths).map(id => {
    const pts = (robotPaths[id] || [])
      .map(p => { const x = toX(p.x), y = toY(p.y); return (x === null || y === null) ? null : `${x},${y}`; })
      .filter(Boolean).join(" ");
    return pts ? <polyline key={`${id}-path`} points={pts} fill="none" stroke="rgba(21,101,192,0.85)" strokeWidth="0.6" strokeLinejoin="round" /> : null;
  }), [robotPaths, mapBounds]);

  // 상태별 색상
  const robotColor = (status) => ({
    IDLE: "var(--blue)",
    MOVING: "var(--green)",
    SUCCESS: "var(--green)",
    ERROR: "var(--red-light)",
  }[status] ?? "var(--blue)");

  return (
    <AresShell route="monitor" title="로봇 실시간 모니터링" subtitle="ROBOT LIVE MONITORING">
      <main className="grid-monitor">

        {/* ── 지도 패널 ─────────────────────────────────────────────────── */}
        <section className="cell gui-cell">
          <PanelHeader
            title="로봇 모니터링"
            tone="green"
            action={<span className="alert-chip tiny"><span className="dot" />실시간</span>}
          />
          <div className="gui-inner">
            <div className="dash">
              <div className="dash-center">
                <div className="sub-header split">
                  <span><span className="dot green" />지도</span>
                  {connStatus.backend === 'error' && <span style={{ color: 'var(--red-light)', fontSize: '0.75rem' }}>⚠ 서버 오프라인</span>}{connStatus.db === 'empty' && <span style={{ color: '#f59e0b', fontSize: '0.75rem' }}>⚠ 로봇 미연결</span>}
                </div>
                <div className="map-area">
                  {/* 라이브 SLAM 지도: 정적 PNG 제거 — WebRTC DataChannel(map/coverage/path)로 실시간 렌더 */}
                  <div className="map-svg-bg" style={{ position: "absolute", inset: 0, zIndex: 0 }} />

                  {/* 실시간 궤적을 그리는 SVG 오버레이 선 생성 */}
                  <svg
                      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 5 }}
                      viewBox="0 0 100 100" preserveAspectRatio="none"
                    >
                      {/* ① 커버리지(초록 면) ② SLAM 맵(벽 점) ③ 경로(선) — 데이터 바뀔 때만 다시 그림 */}
                      {coverageEls}
                      {wallEls}
                      {pathEls}
                    </svg>

                  {/* DB에서 받은 로봇 마커 */}
                  {robots.length === 0 && connStatus.backend === 'ok' && (
                    <div className="cam-no-signal" style={{ position: "absolute", inset: 0, background: "transparent", fontSize: "0.8rem" }}>
                      로봇 데이터 없음
                    </div>
                  )}
                  {Array.isArray(robots) && robots.map((robot, i) => {
                    // WebRTC 실시간 좌표 우선 추종
                    const currentX = liveTelemetry[robot.id]?.pos_x ?? robot.pos_x;
                    const currentY = liveTelemetry[robot.id]?.pos_y ?? robot.pos_y;
                    
                    const x = toX(currentX);
                    const y = toY(currentY);

                    // 💡 좌표 가독성 오류나 유실 시 렌더링 스킵 방어선
                    if (x === null || y === null || isNaN(x) || isNaN(y)) return null;
                    
                    return (
                      <div
                        key={robot.id}
                        className={`robot-marker ${i > 0 ? "orange" : ""}`}
                        style={{ 
                          left: `${x}%`, 
                          top: `${y}%`, 
                          transition: "left 0.15s linear, top 0.15s linear" // 💡 순간이동 현상을 완전히 지워버리는 리액트 선형 보간 트랜지션
                        }}
                        title={`${robot.id} — ${robot.status}`}
                      >
                        🤖
                      </div>
                    );
                  })}

                  <div className="map-overlay-top">
                    <div className="overlay-title">임무 경과시간</div>
                    <div className="overlay-val">{formatDuration(missionSeconds)}</div>
                  </div>
                  <div className="map-legend">
                    <Legend color="var(--blue)" text="로봇(IDLE)" />
                    <Legend color="var(--green)" text="로봇(이동중)" />
                    <Legend color="var(--red-light)" text="로봇(오류)" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── 구조대상자 식별 현황 + 로봇 상태 패널 ──────────────────── */}
        <section className="cell status-cell">
          <PanelHeader title="구조대상자 식별 현황" tone="green" />
          <div className="status-dashboard">

            {/* 생존자 카운트 — 총 신원자(등록) / 식별 완료 / 미식별 */}
            <div className="casualty-grid-lg" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
              <div className="casualty-box-lg">
                <div className="casualty-num-lg">{registeredTotal}</div>
                <div className="casualty-label-lg">총 신원자</div>
              </div>
              <div className="casualty-box-lg survivor">
                <div className="casualty-num-lg">{survivorStats.confirmed}<span style={{ fontSize: "0.55em", opacity: 0.6 }}> / {registeredTotal}</span></div>
                <div className="casualty-label-lg">식별 완료</div>
              </div>
              <div className="casualty-box-lg unknown">
                <div className="casualty-num-lg">{survivorStats.unknown}</div>
                <div className="casualty-label-lg">미식별</div>
              </div>
            </div>

            {connStatus.backend === 'error' ? (
              <StatusBadge icon="ti-server-off" color="var(--red-light)"
                msg="Flask 서버 응답 없음 — Docker 컨테이너를 확인하세요" />
            ) : connStatus.db === 'error' ? (
              <StatusBadge icon="ti-database-off" color="var(--red-light)"
                msg="DB 쿼리 오류 — rescue_robots 테이블을 확인하세요" />
            ) : connStatus.db === 'empty' ? (
              <StatusBadge icon="ti-robot-off" color="#f59e0b"
                msg="로봇 데이터 없음 — bt_db_bridge 실행 여부 확인" />
            ) : (
              <>
                <div className="status-line">
                  <span className="status-label">활성 로봇</span>
                  <span className="status-value">{robots.filter(r => r.status !== "ERROR").length} / {robots.length}</span>
                </div>
                <div className="status-line">
                  <span className="status-label">갱신</span>
                  <span className="status-value">실시간</span>
                </div>
              </>
            )}

            <hr className="divider" />

            {/* Ring 차트 — 탐사 완료율 단일 */}
            <div className="ring-row" style={{ justifyContent: "center" }}>
              <Ring
                percent={(() => {
                  // 라이브 CoverageStatus(coverage_status) 우선, 없으면 DB coverage_ratio
                  const ratios = robots
                    .map(r => liveTelemetry[r.id]?.coverage_ratio ?? r.coverage_ratio)
                    .filter(v => v != null);
                  if (ratios.length === 0) return null;
                  const avg = ratios.reduce((s, v) => s + v, 0) / ratios.length;
                  return Math.min(100, Math.round(avg * 100));
                })()}
                tone="rescue"
                label="탐사"
                sub="탐사 완료율"
                size={76}
              />
            </div>

            <hr className="divider" />

            <div className="prog-label">로봇 상태</div>
            {robots.length === 0 ? (
              <div className="empty" style={{ fontSize: "0.8rem", padding: "0.5rem 0" }}>
                {connStatus.backend === 'error' ? "서버 오프라인" : "로봇 미연결"}
              </div>
            ) : (
              robots.map((robot) => {
                // DB 배터리보다 WebRTC 실시간 배터리를 우선 적용
                const currentBattery = liveTelemetry[robot.id]?.battery ?? robot.battery ?? null;
                
                return (
                  <RobotStatus
                    key={robot.id}
                    name={robot.id}
                    status={robot.status}
                    battery={currentBattery} 
                    color={robotColor(robot.status)}
                  />
                );
              })
            )}

            <button className="report-link wide" type="button" onClick={() => navigate("report")}>
              <i className="ti ti-file-report" /> 사고 보고서
            </button>
          </div>
        </section>

        {/* ── 카메라 패널 (WebRTC) ──────────────────────────────────────── */}
        {(Array.isArray(robots) && robots.length > 0 ? robots.slice(0, 2) : [{ id: "ROBOT-01" }, { id: "ROBOT-02" }]).map((robot, i) => (
          <CameraPanel
            key={robot.id}
            title={`카메라 · ${robot.id}`}
            tone={i === 0 ? "green" : "orange"}
            robotId={robot.id}
            robotIndex={i}
            cameraTime={cameraTime}
            // 자식(WebRTC)이 데이터를 받으면 부모의 State 업데이트
            onTelemetry={(id, data) => {
              if (data.type === "battery") {
                setLiveTelemetry(prev => ({ ...prev, [id]: { ...prev[id], battery: data.value } }));
              }
              else if (data.type === "path") {
                // 1. 궤적 선 데이터 누적
                setRobotPaths(prev => ({ ...prev, [id]: data.poses }));
              }
              else if (data.type === "camera_coverage") {
                setCameraCoverage(prev => ({ ...prev, [id]: data.points }));
              }
              else if (data.type === "pose") {
                // 로봇 현재 위치(map 좌표계) — ROS pose 토픽 기반 (정식 좌표 + 방향)
                setLiveTelemetry(prev => ({
                  ...prev,
                  [id]: { ...prev[id], pos_x: data.x, pos_y: data.y, yaw: data.yaw }
                }));
              }
              else if (data.type === "map") {
                // SLAM이 실시간 작성 중인 맵(벽 점유 셀) — 탐색 진행에 따라 갱신
                setMapWalls(prev => ({ ...prev, [id]: data.walls }));
              }
              else if (data.type === "coverage_status") {
                // AMR 계약 CoverageStatus — 탐색 진행률/모드 라이브 반영
                setLiveTelemetry(prev => ({
                  ...prev,
                  [id]: { ...prev[id], coverage_ratio: data.coverage_ratio, mode: data.mode }
                }));
              }
            }}
          />
        ))}
      </main>
    </AresShell>
  );
}

// ─── 서브 컴포넌트 ────────────────────────────────────────────────────────────
function StatusBadge({ icon, color, msg }) {
  return (
    <div style={{ color, fontSize: "0.8rem", padding: "0.35rem 0", display: "flex", alignItems: "center", gap: "0.4rem" }}>
      <i className={`ti ${icon}`} style={{ flexShrink: 0 }} />
      <span>{msg}</span>
    </div>
  );
}

function PanelHeader({ title, tone, action }) {
  return (
    <div className="panel-header">
      <span className="panel-title"><span className={`dot ${tone}`} />{title}</span>
      {action}
    </div>
  );
}

function Legend({ color, text }) {
  return (
    <div className="legend-item">
      <span className="legend-dot" style={{ background: color }} />{text}
    </div>
  );
}

function RobotStatus({ name, status, battery, color }) {
  const statusLabel = { IDLE: "대기", MOVING: "이동중", SUCCESS: "완료", ERROR: "오류" }[status] ?? status;
  return (
    <div className="robot-status-item">
      <span className="robot-dot" style={{ background: color }} />
      <span className="robot-name">{name}</span>
      <span className="robot-pct" style={{ color }}>
        {battery != null ? `${battery}%` : statusLabel}
      </span>
    </div>
  );
}
