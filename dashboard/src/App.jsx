/**
 * Mar en internet (Orquestrador 360) — Dashboard
 *
 * Talks to the MAP server (src/server.js) via an app-issued API key (one of
 * APP_API_KEYS on the backend). This is NOT the Anthropic key — the backend
 * never accepts or forwards a raw Anthropic key from the browser, so there is
 * nothing sensitive to protect beyond a revocable app token.
 */

import React, { useState, useEffect } from "react";
import "./styles.css";
import ApiClient from "./api-client.js";
import AppShell from "./components/AppShell.jsx";
import Landing from "./pages/Landing.jsx";
import { applyStoredAppearance } from "./components/Settings/SettingsModal.jsx";

const STORAGE_KEY = "ORQ_APP_KEY";

applyStoredAppearance();

export default function App() {
  const [appKey, setAppKey] = useState(localStorage.getItem(STORAGE_KEY) || "");
  const [authenticated, setAuthenticated] = useState(!!appKey);
  const [loading, setLoading] = useState(false);
  const [phases, setPhases] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loginError, setLoginError] = useState("");

  const api = authenticated ? new ApiClient(appKey) : null;

  useEffect(() => {
    if (!authenticated || !api) return;
    (async () => {
      setLoading(true);
      try {
        const [phasesData, agentsData] = await Promise.all([api.getPhases(), api.getAgents()]);
        setPhases(phasesData);
        setAgents(agentsData);
      } catch (error) {
        console.error("Error loading initial data:", error);
        // Multi-usuario (2026-09-09): a user JWT from /auth/login only
        // authorizes /projects and /repositories today (see
        // PLAN-i18n-multiusuario.md) — /agents and /phases still require the
        // shared APP_API_KEYS token, so a JWT-only login surfaces here as a
        // 401/403 on this initial load rather than silently half-working.
        setLoginError(
          `${error.message} — si iniciaste sesión con email/contraseña, todavía necesitás tu App API Key para el resto de la app (usá la opción avanzada).`
        );
        setAuthenticated(false);
        localStorage.removeItem(STORAGE_KEY);
      }
      setLoading(false);
    })();
  }, [authenticated]);

  const enterWithToken = (token) => {
    localStorage.setItem(STORAGE_KEY, token);
    setAppKey(token);
    setLoginError("");
    setAuthenticated(true);
  };

  if (!authenticated) {
    return (
      <Landing
        onAuthenticated={(token) => enterWithToken(token)}
        onUseAppKey={enterWithToken}
        externalError={loginError}
      />
    );
  }

  if (loading) {
    return <div className="loading">Cargando...</div>;
  }

  return <AppShell api={api} agents={agents} phases={phases} />;
}
