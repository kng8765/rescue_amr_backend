import { useCallback, useEffect, useRef, useState } from "react";
import AresShell from "../AresShell";
import { navigate } from "../aresRouting";
import useClock from "../useClock";

const API_BASE = "http://localhost:8001/api";
// 로봇 인덱스(0-based) → WebRTC 브릿지 포트
// TB_01 (192.168.108.101): run_ares_vision.sh TB_01 8002
// TB_05 (192.168.108.105): run_ares_vision.sh TB_05 8003
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
  const [robotPaths, setRobotPaths] = useState({});
  const [cameraCoverage, setCameraCoverage] = useState({});

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
    let robotRes, survivorRes;

    // ── 1단계: Flask 서버 응답 여부 ─────────────────────────────────
    try {
      [robotRes, survivorRes] = await Promise.all([
        fetch(`${API_BASE}/robots`),
        fetch(`${API_BASE}/survivor-logs?limit=200`),
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

    // ── 3단계: 생존자 로그 ───────────────────────────────────────────
    if (survivorRes.ok) {
      const logs = await survivorRes.json();
      const confirmed = new Set(logs.filter((l) => l.survivor_id).map((l) => l.survivor_id)).size;
      const unknown = logs.filter((l) => !l.survivor_id).length;
      setSurvivorStats({ confirmed, unknown });
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [fetchStatus]);

  // 로봇 위치를 맵 퍼센트로 변환 (pos_x/y가 미터 단위라 가정, 맵 범위 0~20m)
  const MAP_RANGE = 20;
  const toMapPct = (v) => v != null ? Math.min(95, Math.max(5, (v / MAP_RANGE) * 100)) : null;

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
                  {/* flask static 폴더의 실시간 PNG 지도로 바인딩 */}
                  <img 
                    src={`http://localhost:8001/static/maps/robot5_map.png?t=${Date.now()}`} // 캐시 방지 타임스탬프 탑재
                    alt="ARES SLAM MAP"
                    style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain", zIndex: 1 }}
                    onError={(e) => {
                      // 지도가 아직 생성 전이라 404가 뜰 경우를 대비한 기본 그리드 배경 방어선
                      e.target.style.display = 'none'; 
                    }}
                  />
                  <div className="map-svg-bg" style={{ position: "absolute", inset: 0, zIndex: 0 }} />
                  
                  {/* WebRTC로 들어오는 카메라 가시 영역 레이어 드로잉 */}
                  {Object.keys(cameraCoverage).map((id) => {
                    const points = cameraCoverage[id] || [];
                    return points.map((p, idx) => {
                      const pctX = toMapPct(p.x);
                      const pctY = toMapPct(p.y);
                      if (pctX === null || pctY === null) return null;
                      return (
                        <div
                          key={`${id}-cov-${idx}`}
                          style={{
                            position: "absolute",
                            left: `${pctX}%`,
                            top: `${pctY}%`,
                            width: "12px",
                            height: "12px",
                            transform: "translate(-50%, -50%)",
                            background: "rgba(46, 204, 113, 0.15)", // 투명한 초록색 음영 칠하기
                            borderRadius: "50%",
                            pointerEvents: "none",
                            zIndex: 3,
                          }}
                        />
                      );
                    });
                  })}

                  {/* 실시간 궤적을 그리는 SVG 오버레이 선 생성 */}
                  <svg 
                      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", zIndex: 5 }}
                      viewBox="0 0 100 100" 
                    >
                      {/* [추가] 카메라 가시 영역을 연한 초록색 다각형(또는 선)으로 채우기 */}
                      {Object.keys(cameraCoverage).map((id) => {
                        const points = cameraCoverage[id] || [];
                        if (points.length < 2) return null;

                        const coveragePointsStr = points
                          .map(p => {
                            const xPct = toMapPct(p.x);
                            // 💡 만약 지도가 뒤집혀서 나온다면 100 - toMapPct(p.y) 형태로 Y축을 반전해보세요.
                            const yPct = toMapPct(p.y); 
                            return `${xPct},${yPct}`;
                          })
                          .join(" ");

                        return (
                          <polygon
                            key={`${id}-coverage`}
                            points={coveragePointsStr}
                            fill="rgba(46, 204, 113, 0.15)" // 이미지에 있던 투명한 초록색 음영
                            stroke="rgba(46, 204, 113, 0.5)" // 경계선은 조금 더 진하게
                            strokeWidth="1"
                          />
                        );
                      })}

                      {/* 기존 로봇 궤적 (polyline) 코드 위치 */}
                      {Object.keys(robotPaths).map((id) => {
                        // ... 기존 polyline 렌더링 코드
                      })}
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
                    
                    const x = toMapPct(currentX);
                    const y = toMapPct(currentY);
                    
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

            {/* 생존자 카운트 */}
            <div className="casualty-grid-lg">
              <div className="casualty-box-lg survivor">
                <div className="casualty-num-lg">{survivorStats.confirmed}</div>
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
                  // 모든 로봇의 explored_area / total_area 합산
                  const withData = robots.filter(r => r.explored_area != null && r.total_area > 0);
                  if (withData.length === 0) return null;
                  const explored = withData.reduce((s, r) => s + r.explored_area, 0);
                  const total    = withData.reduce((s, r) => s + r.total_area, 0);
                  return Math.min(100, Math.round((explored / total) * 100));
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

                // 2. [추가] 경로 데이터의 가장 마지막 좌표(최신 위치)를 캡처하여 로봇 마커 위치도 실시간 강제 갱신
                if (data.poses && data.poses.length > 0) {
                  const latestPose = data.poses[data.poses.length - 1];
                  setLiveTelemetry(prev => ({
                    ...prev,
                    [id]: {
                      ...prev[id],
                      pos_x: latestPose.x,
                      pos_y: latestPose.y
                    }
                  }));
                }
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
