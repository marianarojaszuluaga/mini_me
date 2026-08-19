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
import { BrandIcon, AlertIcon } from "./components/icons.jsx";
import AppShell from "./components/AppShell.jsx";
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
        setLoginError(error.message);
        setAuthenticated(false);
        localStorage.removeItem(STORAGE_KEY);
      }
      setLoading(false);
    })();
  }, [authenticated]);

  const handleLogin = (e) => {
    e.preventDefault();
    localStorage.setItem(STORAGE_KEY, appKey);
    setLoginError("");
    setAuthenticated(true);
  };

  if (!authenticated) {
    return (
      <div className="login-container">
        <div className="login-card">
          <h1>
            <span className="login-brand-icon">{BrandIcon}</span> Mar en internet
          </h1>
          <p>Ingresa la App API Key (no tu clave de Anthropic)</p>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              placeholder="App API Key"
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              required
            />
            <button type="submit">Iniciar Sesión</button>
          </form>
          {loginError && <div className="flag">{AlertIcon} {loginError}</div>}
        </div>
      </div>
    );
  }

  if (loading) {
    return <div className="loading">Cargando...</div>;
  }

  return <AppShell api={api} agents={agents} phases={phases} />;
}
