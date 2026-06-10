import { useEffect, useState, useRef, useCallback } from "react";
import AresShell from "../AresShell";
import { navigate } from "../aresRouting";
import useClock from "../useClock";

const API_BASE = "http://localhost:8001/api";
const WEBRTC_BASE = "http://localhost:8002";
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
function CameraPanel({ title, tone, robotId, cameraTime }) {
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const [connState, setConnState] = useState("idle"); // idle | connecting | connected | error

  const connect = useCallback(async () => {
    // 이미 연결 중이거나 연결됐으면 스킵
    if (pcRef.current) return;

    setConnState("connecting");
    try {
      const pc = new RTCPeerConnection({ iceServers: [] });
      pcRef.current = pc;

      // 수신 트랙을 video 엘리먼트에 연결
      pc.ontrack = (e) => {
        if (videoRef.current && e.streams[0]) {
          videoRef.current.srcObject = e.streams[0];
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

      const res = await fetch(`${WEBRTC_BASE}/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sdp: offer.sdp, type: offer.type }),
      });

      if (!res.ok) throw new Error(`시그널링 실패: ${res.status}`);

      const answer = await res.json();
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
    } catch (err) {
      console.error(`[WebRTC][${robotId}] 연결 오류:`, err);
      if (pcRef.current) { pcRef.current.close(); pcRef.current = null; }
      setConnState("error");
    }
  }, [robotId]);

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
  const [robots, setRobots] = useState([]);        // rescue_robots 테이블
  const [survivorStats, setSurvivorStats] = useState({ confirmed: 0, unknown: 0 });
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
      setRobots(data);
      // 응답은 왔지만 테이블이 비어있는 경우
      setConnStatus({ backend: 'ok', db: data.length === 0 ? 'empty' : 'ok' });
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
                  {connStatus.backend === 'error' && <span style={{ color: 'var(--red-light)', fontSize: '0.75rem' }}>⚠ 서버 오프라인</span>}{connStatus.db === 'empty' && <span style={{ color: 'var(--yellow)', fontSize: '0.75rem' }}>⚠ 로봇 미연결</span>}
                </div>
                <div className="map-area">
                  <div className="map-svg-bg" />
                  {/* DB에서 받은 로봇 마커 */}
                  {robots.length === 0 && connStatus.backend === 'ok' && (
                    <div className="cam-no-signal" style={{ position: "absolute", inset: 0, background: "transparent", fontSize: "0.8rem" }}>
                      로봇 데이터 없음
                    </div>
                  )}
                  {robots.map((robot, i) => {
                    const x = toMapPct(robot.pos_x);
                    const y = toMapPct(robot.pos_y);
                    if (x == null || y == null) return null;
                    return (
                      <div
                        key={robot.id}
                        className={`robot-marker ${i > 0 ? "orange" : ""}`}
                        style={{ left: `${x}%`, top: `${y}%` }}
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
              <StatusBadge icon="ti-robot-off" color="var(--yellow)"
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
              robots.map((robot) => (
                <RobotStatus
                  key={robot.id}
                  name={robot.id}
                  status={robot.status}
                  battery={robot.battery ?? null}
                  color={robotColor(robot.status)}
                />
              ))
            )}

            <button className="report-link wide" type="button" onClick={() => navigate("report")}>
              <i className="ti ti-file-report" /> 사고 보고서
            </button>
          </div>
        </section>

        {/* ── 카메라 패널 (WebRTC) ──────────────────────────────────────── */}
        {/* 로봇이 있으면 첫 두 대, 없으면 기본 2개 슬롯 */}
        {(robots.length > 0 ? robots.slice(0, 2) : [{ id: "ROBOT-01" }, { id: "ROBOT-02" }]).map((robot, i) => (
          <CameraPanel
            key={robot.id}
            title={`카메라 · ${robot.id}`}
            tone={i === 0 ? "green" : "orange"}
            robotId={robot.id}
            cameraTime={cameraTime}
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
