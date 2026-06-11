import { useEffect, useState } from "react";
import { navigate } from "../aresRouting";

export default function SyncPage() {
  const [status, setStatus] = useState({ total: 0, current: 0, message: "시스템 초기화 준비 중...", is_running: true });

  useEffect(() => {
    // 1. 마운트 되자마자 백엔드 AI 분석 스레드 가동 요청
    fetch("http://localhost:8001/api/sync/start", { method: "POST" })
      .catch(err => console.error("Sync Start Error:", err));

    // 2. 1초마다 백엔드 진행 상태 폴링
    const interval = setInterval(async () => {
      try {
        const res = await fetch("http://localhost:8001/api/sync/status");
        const data = await res.json();
        setStatus(data);

        // 3. 작업이 모두 끝났으면 1.5초 뒤 메인 관제 화면으로 부드럽게 이동
        if (!data.is_running && data.message.includes("완료")) {
          clearInterval(interval);
          setTimeout(() => navigate("worker"), 1500);
        }
      } catch (err) {
        console.warn("API 폴링 대기 중...", err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const percent = status.total > 0 ? Math.round((status.current / status.total) * 100) : 0;

  return (
    <div style={{ width: "100vw", height: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", background: "#1e1e1e", color: "white" }}>
      <div style={{ fontSize: "3.5rem", fontWeight: "bold", marginBottom: "2rem", letterSpacing: "5px", color: "var(--red)" }}>
        🚒 ARES 관제 시스템
      </div>
      
      {/* 프로그레스 바 */}
      <div style={{ width: "450px", background: "#333", borderRadius: "10px", overflow: "hidden", height: "24px", marginBottom: "1.5rem" }}>
        <div style={{ width: `${percent}%`, background: "var(--red)", height: "100%", transition: "width 0.5s ease" }} />
      </div>
      
      {/* 상태 텍스트 */}
      <div style={{ fontSize: "1.1rem", color: "#ccc" }}>
        {status.message} {status.total > 0 && <span style={{color: "var(--green)"}}>({status.current} / {status.total}명)</span>}
      </div>
    </div>
  );
}