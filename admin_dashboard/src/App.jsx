import { useEffect, useState } from "react";
import AresLogin from "./AresLogin";
import "./AresPages.css";
import MonitorPage from "./pages/MonitorPage";
import ReportPage from "./pages/ReportPage";
import SyncPage from "./pages/SyncPage";
import WorkerPage from "./pages/WorkerPage";

const pages = ["worker", "monitor", "report", "sync"];

function getRoute() {
  const route = window.location.hash.replace("#", "");
  return route && (route === "login" || pages.includes(route)) ? route : "login";
}

export default function App() {
  const [route, setRoute] = useState(getRoute);

  useEffect(() => {
    const handleHashChange = () => setRoute(getRoute());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  if (route === "sync") return <SyncPage />;
  if (route === "worker") return <WorkerPage />;
  if (route === "monitor") return <MonitorPage />;
  if (route === "report") return <ReportPage />;
  return <AresLogin />;
}
