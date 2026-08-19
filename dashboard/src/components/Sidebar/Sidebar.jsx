import React, { useState } from "react";
import SettingsModal from "../Settings/SettingsModal.jsx";
import { BrandIcon } from "../icons.jsx";
import "./sidebar.css";

const ICONS = {
  chat: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  ),
  projects: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </svg>
  ),
  integrations: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2v4M15 2v4M6 10h12a1 1 0 011 1v3a5 5 0 01-5 5h-4a5 5 0 01-5-5v-3a1 1 0 011-1zM8 19v1a2 2 0 002 2h4a2 2 0 002-2v-1" />
    </svg>
  ),
  mar: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 14.5L3 21M14 10a4 4 0 10-4-4M15.5 8.5L21 3M13.5 13.5L21 21" />
      <circle cx="8" cy="16" r="4" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  )
};


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

export default function Sidebar({ activeView, onNavigate, onOpenIntegrations, api, projectCount }) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const status = useLiveStatus(api);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-mark">{BrandIcon}</div>
        <div>
          <div className="sidebar-brand-name">Mar en internet</div>
          <div className="sidebar-brand-sub">Mini me with her smarts and AI</div>
        </div>
      </div>

      <button className="btn-accent sidebar-cta" onClick={() => onNavigate("chat")}>
        {ICONS.chat}
        Hablar con Jarvis
      </button>

      <nav className="sidebar-nav">
        <div className="sidebar-nav-label">Trabajo</div>
        <button
          className={`sidebar-nav-item ${activeView === "projects" ? "active" : ""}`}
          onClick={() => onNavigate("projects")}
        >
          {ICONS.projects}
          Proyectos
          {typeof projectCount === "number" && <span className="sidebar-nav-item-count">{projectCount}</span>}
        </button>
      </nav>

      <nav className="sidebar-nav">
        <div className="sidebar-nav-label">Analítica &amp; integraciones</div>
        <button
          className={`sidebar-nav-item ${activeView === "dashboard" ? "active" : ""}`}
          onClick={() => onNavigate("dashboard")}
        >
          {ICONS.dashboard}
          Dashboard
        </button>
        <button className="sidebar-nav-item" onClick={onOpenIntegrations}>
          {ICONS.integrations}
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
          {ICONS.mar}
          Memoria de Mar
        </button>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-status-row">
          <span className={`sidebar-status-dot sidebar-status-dot-${status.state}`} />
          <span className="sidebar-status-text">{status.label}</span>
        </div>
        <button className="sidebar-settings-row" onClick={() => setSettingsOpen(true)}>
          {ICONS.settings}
          Configuración
        </button>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </aside>
  );
}
