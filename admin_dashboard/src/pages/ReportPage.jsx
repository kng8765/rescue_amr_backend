import { useState, useEffect, useCallback } from "react";
import AresShell from "../AresShell";

const API_BASE = "http://localhost:8001/api";
const POLL_INTERVAL = 5000; // 5초마다 갱신

// incident_logs + survivor_logs 둘 다 합쳐서 보여줌
// incident_logs: YOLO/로봇 이벤트 (기존 /logs)
// survivor_logs: 생존자 감지 이벤트 (신규 /survivor-logs)
async function fetchAllLogs() {
  const [incidentRes, survivorRes] = await Promise.all([
    fetch(`${API_BASE}/logs`),
    fetch(`${API_BASE}/survivor-logs?limit=50`),
  ]);

  const incidents = incidentRes.ok ? await incidentRes.json() : [];
  const survivors = survivorRes.ok ? await survivorRes.json() : [];

  // survivor_logs → incident_logs와 동일한 포맷으로 변환
  const survivorFormatted = survivors.map((s) => {
    let msg;
    if (s.survivor_name) {
      msg = `[생존자 식별] ${s.survivor_name} 님 감지 (유사도: ${s.similarity ?? "-"}%) — ${s.robot_id}`;
    } else {
      msg = `[미식별 대상] 좌표 (${s.detected_x?.toFixed(1)}, ${s.detected_y?.toFixed(1)}) — ${s.robot_id}`;
    }
    return { time: s.time, msg, _key: `sv-${s.log_number}` };
  });

  // incident_logs 포맷 통일
  const incidentFormatted = incidents.map((i) => ({
    time: i.time,
    msg: i.msg,
    _key: `inc-${i.time}-${i.msg}`,
  }));

  // 시간 역순 정렬 (최신 위로)
  const all = [...incidentFormatted, ...survivorFormatted].sort((a, b) =>
    b.time.localeCompare(a.time)
  );

  return all;
}

// HTML 태그 포함 메시지 안전 렌더링 (백엔드에서 <span class='highlight'>... 형태로 옴)
function LogMessage({ msg }) {
  // 백엔드 HTML 태그 허용 (신뢰된 서버 데이터)
  // eslint-disable-next-line react/no-danger
  return <span dangerouslySetInnerHTML={{ __html: msg }} />;
}

export default function ReportPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchAllLogs();
      setLogs(data);
      setLastUpdated(new Date().toLocaleTimeString("ko-KR", { hour12: false }));
      setError(null);
    } catch (e) {
      setError("서버에 연결할 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [load]);

  return (
    <AresShell route="report" title="실시간 구조활동 기록">
      <main className="content">
        <section className="report-summary report-summary-2">
          <ReportStat icon="ti-list-details" value={loading ? "…" : logs.length} label="전체 기록" />
          <ReportStat
            icon="ti-clock-check"
            value={lastUpdated ?? "-"}
            label="마지막 갱신"
          />
        </section>

        <section className="panel">
          <div className="panel-header">
            <span className="panel-title">
              <i className="ti ti-file-analytics" />구조활동 내용
            </span>
            <button className="btn" type="button" onClick={load} disabled={loading}>
              <i className="ti ti-refresh" /> {loading ? "로딩 중…" : "새로고침"}
            </button>
          </div>

          {error && (
            <div className="empty" style={{ color: "var(--red-light)", padding: "1.5rem" }}>
              <i className="ti ti-wifi-off" /> {error}
            </div>
          )}

          <div className="log-list">
            {!error && !loading && logs.length === 0 && (
              <div className="empty">기록된 활동이 없습니다.</div>
            )}
            {logs.map((log) => (
              <div className="log-item" key={log._key}>
                <span className="log-time">{log.time}</span>
                <span className="log-msg">
                  <LogMessage msg={log.msg} />
                </span>
              </div>
            ))}
          </div>
        </section>
      </main>
    </AresShell>
  );
}

function ReportStat({ icon, value, label }) {
  return (
    <div className="stat">
      <i className={`ti ${icon}`} />
      <div>
        <div className="stat-val">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}
