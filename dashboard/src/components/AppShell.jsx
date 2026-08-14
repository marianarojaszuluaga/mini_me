import React, { useState } from "react";
import Sidebar from "./Sidebar/Sidebar.jsx";
import ChatPanel from "./CommandCenter/ChatPanel.jsx";
import ProjectsView from "./Projects/ProjectsView.jsx";
import AnalyticsDrillDown from "./Analytics/AnalyticsDrillDown.jsx";
import MarMemoryDrillDown from "./MarMemory/MarMemoryDrillDown.jsx";
import IntegrationsDrillDown from "./Integrations/IntegrationsDrillDown.jsx";
import "./app-shell.css";

/**
 * AppShell — real implementation of the IA Mariana approved via the HTML
 * mockup (SPEC_JARVIS.md HU-011, §2). Replaces CommandCenterLayout as the
 * authenticated app's root: sidebar navigation + one of four full-page
 * views (Jarvis Chat / Proyectos / Dashboard / Memoria de Mar), with
 * Integraciones staying a modal (deliberate — see §2's rationale).
 */
export default function AppShell({ api, agents, phases }) {
  const [view, setView] = useState("chat");
  const [integrationsOpen, setIntegrationsOpen] = useState(false);
  const [projects, setProjects] = useState([]);

  // Dashboard needs the project list for its scope selector; fetched once
  // here (not by AnalyticsDrillDown itself) so Proyectos and Dashboard share
  // one source instead of two independent fetches drifting apart.
  React.useEffect(() => {
    api.getProjects().then(setProjects).catch(() => setProjects([]));
  }, [api]);

  return (
    <div className="app-shell">
      <Sidebar
        activeView={view}
        onNavigate={setView}
        onOpenIntegrations={() => setIntegrationsOpen(true)}
        api={api}
      />

      <main className="app-shell-main">
        {view === "chat" && <ChatPanel api={api} />}
        {view === "projects" && <ProjectsView api={api} agents={agents} phases={phases} />}
        {view === "dashboard" && (
          <div className="app-shell-page">
            <AnalyticsDrillDown api={api} fullPage projects={projects} />
          </div>
        )}
        {view === "mar" && (
          <div className="app-shell-page">
            <MarMemoryDrillDown api={api} fullPage />
          </div>
        )}
      </main>

      <IntegrationsDrillDown
        open={integrationsOpen}
        onClose={() => setIntegrationsOpen(false)}
        api={api}
      />
    </div>
  );
}
