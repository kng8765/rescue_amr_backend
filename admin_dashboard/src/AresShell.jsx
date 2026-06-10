import { useState } from "react";
import { navigate } from "./aresRouting";
import useClock from "./useClock";

const navItems = [
  { route: "worker", icon: "ti-users", label: <>구조대상자<br />관리</> },
  { route: "monitor", icon: "ti-robot", label: <>로봇<br />모니터링</> },
  { route: "report", icon: "ti-file-report", label: "보고서" },
];

export default function AresShell({ route, title, subtitle, children }) {
  const time = useClock();
  const [showLogout, setShowLogout] = useState(false);

  return (
    <div className="ares-app">
      {/* 로그아웃 확인 다이얼로그 */}
      {showLogout && (
        <div className="logout-overlay" onClick={() => setShowLogout(false)}>
          <div className="logout-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="logout-dialog-icon">🚪</div>
            <div className="logout-dialog-title">로그아웃</div>
            <div className="logout-dialog-msg">로그아웃 하시겠습니까?</div>
            <div className="logout-dialog-btns">
              <button className="logout-dialog-cancel" type="button" onClick={() => setShowLogout(false)}>취소</button>
              <button className="logout-dialog-confirm" type="button" onClick={() => navigate("login")}>로그아웃</button>
            </div>
          </div>
        </div>
      )}

      <aside className="ares-sidebar">
        {/* 로고 — 클릭 비활성화 */}
        <div className="sidebar-logo">
          <span className="emblem">🚒</span>
          <span>ARES<br />관제</span>
        </div>

        <nav className="sidebar-nav" aria-label="ARES navigation">
          {navItems.map((item) => (
            <button
              key={item.route}
              className={`nav-item ${route === item.route ? "active" : ""}`}
              type="button"
              onClick={() => navigate(item.route)}
            >
              <i className={`ti ${item.icon} icon`} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <button className="logout-btn" type="button" onClick={() => setShowLogout(true)}>
          <i className="ti ti-logout" />
          <span>로그아웃</span>
        </button>
      </aside>

      <div className="ares-main">
        <header className="ares-topbar">
          <div className="topbar-left">
            <span className="topbar-title">{title}</span>
            {subtitle && <span className="topbar-sub">{subtitle}</span>}
            {route === "monitor" && <span className="alert-chip"><span className="dot" />임무 진행중</span>}
          </div>
          <div className="topbar-right">
            <span className="topbar-time">{time}</span>
            <div className="topbar-user">
              <div className="user-avatar">🧑‍🚒</div>
              <span className="user-name">관리자</span>
            </div>
          </div>
        </header>

        {children}
      </div>
    </div>
  );
}
