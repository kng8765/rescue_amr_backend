import { useEffect, useState } from "react";
import AresShell from "../AresShell";

// 백엔드 API 주소. 배포 시 빌드 환경변수 VITE_API_BASE_URL(예: 터널 HTTPS 주소)로 주입하고,
// 값이 없으면 로컬 개발 기본값을 사용합니다.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

// 백엔드가 <span class='highlight'> 같은 HTML 태그를 섞어서 보내므로,
// React에서 이를 그대로 예쁘게 렌더링하기 위한 컴포넌트입니다.
function HighlightedMessage({ log }) {
  return <span dangerouslySetInnerHTML={{ __html: log.msg }} />;
}

export default function ReportPage() {
  const [logs, setLogs] = useState([]);

  // 🚀 Flask 백엔드에서 실시간 로그 가져오기
  const fetchLogs = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/logs`);
      if (response.ok) {
        const data = await response.json();
        setLogs(data); // 백엔드에서 받은 데이터로 상태 덮어쓰기
      }
    } catch (error) {
      console.error("❌ 백엔드 로그 수신 실패:", error);
    }
  };

  // 페이지가 열리면 2초마다 자동으로 새로고침 (Polling)
  useEffect(() => {
    fetchLogs(); // 최초 1회 즉시 실행
    const timer = setInterval(fetchLogs, 2000);
    return () => clearInterval(timer); // 페이지를 떠날 때 타이머 해제
  }, []);

  return (
    <AresShell route="report" title="Incident 보고서" subtitle="INCIDENT LOG REPORT">
      <main className="content">
        <section className="page-head">
          <div>
            <h1>현장 Incident Log</h1>
            <p>ARES RESCUE OPERATION RECORD</p>
          </div>
          <div className="live-badge"><span className="dot" />LIVE RECORD</div>
        </section>

        <section className="report-summary">
          <ReportStat icon="ti-list-details" value={logs.length} label="전체 기록" />
          <ReportStat icon="ti-clock-check" value={logs.length > 0 ? logs[0].time : "-"} label="최근 기록 시각" />
          <ReportStat icon="ti-database" value="PostgreSQL" label="저장 방식" />
        </section>

        <section className="panel">
          <div className="panel-header">
            <span className="panel-title"><i className="ti ti-file-analytics" /> Incident Log</span>
            <button className="btn" type="button" onClick={fetchLogs}>
              <i className="ti ti-refresh" /> 새로고침
            </button>
          </div>
          <div className="log-list">
            {logs.length > 0 ? logs.map((log, index) => (
              <div className="log-item" key={`${log.time}-${index}`}>
                <span className="log-time">{log.time}</span>
                <span className="log-msg"><HighlightedMessage log={log} /></span>
              </div>
            )) : <div className="empty">기록된 Incident Log가 없습니다.</div>}
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