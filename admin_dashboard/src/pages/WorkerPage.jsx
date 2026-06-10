import { useEffect, useMemo, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import AresShell from "../AresShell";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_KEY;
const supabase = SUPABASE_URL && SUPABASE_KEY ? createClient(SUPABASE_URL, SUPABASE_KEY) : null;

// 프로필 상세용 원형 얼굴 사진 (82px 고정, 부모 wrap 안에서만 사용)
function ProfilePhoto({ survivor }) {
  const [imgError, setImgError] = useState(false);
  const emoji = survivor.sex === "여" ? "👩" : "🧑";

  if (survivor.face && !imgError) {
    return (
      <img
        src={survivor.face}
        alt={survivor.name}
        onError={() => setImgError(true)}
        style={{
          width: "82px",
          height: "82px",
          borderRadius: "50%",
          objectFit: "cover",         // 얼굴 중심으로 크롭
          objectPosition: "center top", // 상단(얼굴) 우선
          border: "1px solid var(--border)",
          display: "block",
        }}
      />
    );
  }

  return (
    <div className="profile-photo-placeholder">
      {emoji}
    </div>
  );
}

export default function WorkerPage() {
  const [survivors, setSurvivors] = useState([]);
  const [loading, setLoading] = useState(true);   // 최초 1회만 true
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function fetchSurvivors(isFirst = false) {
      try {
        if (!supabase) throw new Error("Supabase 설정이 없습니다. .env를 확인하세요.");
        const { data, error } = await supabase
          .from("survivors")
          .select("id, name, sex, phone_number, face");
        if (error) throw error;
        if (cancelled) return;

        setSurvivors((prev) => {
          // 데이터가 실제로 바뀐 경우에만 state 업데이트 → 불필요한 리렌더 방지
          if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
          return data;
        });
        // 최초 fetch일 때만 선택 초기화
        if (isFirst && data.length > 0) setSelectedId(data[0].id);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (isFirst && !cancelled) setLoading(false);
      }
    }

    fetchSurvivors(true);
    const id = setInterval(() => fetchSurvivors(false), 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return survivors
      .filter((s) => {
        const text = `${s.name} ${s.phone_number ?? ""}`.toLowerCase();
        return !q || text.includes(q);
      })
      .sort((a, b) => a.name.localeCompare(b.name, "ko"));
  }, [query, survivors]);

  const selected = survivors.find((s) => s.id === selectedId) || filtered[0];

  return (
    <AresShell route="worker" title="구조대상자 신원정보">
      <main className="content">
        <section className="main-grid">
          <div className="card">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-id-badge-2" /> 목록</span>
            </div>

            <div className="filter-bar">
              <label className="search-wrap">
                <i className="ti ti-search" />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="이름, 전화번호 검색..."
                />
              </label>
            </div>

            {loading && <div style={{ padding: "1rem", color: "var(--gray)" }}>불러오는 중...</div>}
            {error && <div style={{ padding: "1rem", color: "var(--red-light)" }}>⚠ {error}</div>}

            {!loading && !error && (
              <table>
                <thead>
                  <tr><th>이름</th><th>성별</th><th>전화번호</th></tr>
                </thead>
                <tbody>
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={3} style={{ textAlign: "center", color: "var(--gray)", padding: "1.5rem" }}>
                        검색 결과가 없습니다.
                      </td>
                    </tr>
                  )}
                  {filtered.map((s) => (
                    <tr
                      key={s.id}
                      className={selected?.id === s.id ? "selected" : ""}
                      onClick={() => setSelectedId(s.id)}
                    >
                      {/* 리스트에는 이모지 아바타만 — 사진 없음 */}
                      <td>
                        <div className="name-cell">
                          <div className="avatar-placeholder">
                            {s.sex === "여" ? "👩" : "🧑"}
                          </div>
                          <span className="name-text">{s.name}</span>
                        </div>
                      </td>
                      <td>{s.sex ?? "-"}</td>
                      <td className="mono-cell">{s.phone_number ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <aside className="detail-panel">
            {selected
              ? <SurvivorProfile survivor={selected} />
              : <div className="placeholder-panel"><div className="ph-icon">👆</div><p>구조대상자를 선택하세요</p></div>
            }
          </aside>
        </section>
      </main>
    </AresShell>
  );
}

function SurvivorProfile({ survivor }) {
  return (
    <div className="profile-card">
      <div className="profile-top">
        {/* profile-photo-wrap이 82×82 고정이므로 그 안에 img가 딱 맞게 들어감 */}
        <div className="profile-photo-wrap">
          <ProfilePhoto survivor={survivor} />
        </div>
        <div className="profile-name">{survivor.name}</div>
        <div className="profile-role">주민등록번호: {survivor.id}</div>
      </div>
      <div className="profile-body">
        <Info label="성별" value={survivor.sex ?? "-"} />
        <Info label="전화번호" value={survivor.phone_number ?? "-"} mono />
        <Info
          label="얼굴 사진"
          value={survivor.face ? "등록됨" : "미등록"}
          warn={!survivor.face}
        />
      </div>
    </div>
  );
}

function Info({ label, value, mono, warn }) {
  return (
    <div className="info-row">
      <span className="info-label">{label}</span>
      <span
        className={`info-value ${mono ? "mono-cell" : ""}`}
        style={warn ? { color: "var(--red-light)" } : undefined}
      >
        {value}
      </span>
    </div>
  );
}
