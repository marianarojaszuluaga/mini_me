import React, { useState } from "react";
import SettingsModal from "../Settings/SettingsModal.jsx";
import "./sidebar.css";

const NAV_ITEMS = [
  { id: "chat", label: "Jarvis Chat" },
  { id: "projects", label: "Proyectos" },
  { id: "dashboard", label: "Dashboard" }
];

// Live platform status (2026-08-14, mockup §11): a real health probe is a
// separate piece of infra (uptime monitor / health endpoint aggregation)
// that doesn't exist yet — GET /health only tells us THIS backend process
// answers, not "is the whole platform having issues". Wired to that single
// real signal for now (ok/down), with "novedades" reserved for when a real
// incident-status source exists; never fabricated as a 3rd state.
function useLiveStatus(api) {
  const [status, setStatus] = useState({ state: "ok", label: "Operativo" });

  React.useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        // no-store: a transient 500 (e.g. a real backend crash) must never
        // get stuck in the browser's HTTP cache and keep reporting "Caído"
        // forever after the real problem is fixed — found live 2026-08-14
        // when a since-fixed crash's cached response kept failing CORS
        // checks (a cached error response carries no CORS headers) long
        // after the backend itself was healthy again.
        const res = await fetch(`${api.baseUrl}/health`, { cache: "no-store" });
        if (!cancelled) {
          setStatus(
            res.ok
              ? { state: "ok", label: "Operativo" }
              : { state: "down", label: `Caído — /health respondió ${res.status}` }
          );
        }
      } catch (err) {
        if (!cancelled) setStatus({ state: "down", label: "Caído — backend no responde" });
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [api]);

  return status;
}

export default function Sidebar({ activeView, onNavigate, onOpenIntegrations, api }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const status = useLiveStatus(api);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">🎯</div>
        <div>
          <div className="sidebar-brand-name">Mar en internet</div>
          <div className="sidebar-brand-sub">Mini me with her smarts and AI</div>
        </div>
      </div>

      <button className="btn-accent sidebar-cta" onClick={() => onNavigate("chat")}>
        Hablar con Jarvis
      </button>

      <nav className="sidebar-nav">
        <div className="sidebar-nav-label">Trabajo</div>
        {NAV_ITEMS.filter((n) => n.id !== "chat").map((item) => (
          <button
            key={item.id}
            className={`sidebar-nav-item ${activeView === item.id ? "active" : ""}`}
            onClick={() => onNavigate(item.id)}
          >
            {item.label}
          </button>
        ))}
        <button className="sidebar-nav-item" onClick={onOpenIntegrations}>
          Integraciones
        </button>
      </nav>

      {/* Memoria de Mar: aislada, justo arriba del separador de status —
          SPEC_JARVIS.md §2 (ya no agrupada con Analítica/Integraciones). */}
      <div className="sidebar-nav-standalone">
        <button
          className={`sidebar-nav-item ${activeView === "mar" ? "active" : ""}`}
          onClick={() => onNavigate("mar")}
        >
          Memoria de Mar
        </button>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-status-row">
          <span className={`sidebar-status-dot sidebar-status-dot-${status.state}`} />
          <span className="sidebar-status-text">{status.label}</span>
        </div>
        <button className="sidebar-settings-row" onClick={() => setSettingsOpen(true)}>
          Configuración
        </button>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </aside>
  );
}
