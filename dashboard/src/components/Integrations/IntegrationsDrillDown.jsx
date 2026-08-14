import React, { useEffect, useState } from "react";
import ApiClient from "../../api-client.js";
import DrillDown from "../CommandCenter/DrillDown.jsx";

const STORAGE_KEY = "ORQ_APP_KEY";

// Providers with a real OAuth App wired up server-side (app/routers/oauth.py).
// Basecamp joined 2026-08-14 (37signals Launchpad OAuth) — the manual form
// below stays as a fallback for any provider whose OAuth App isn't
// configured yet, not specifically for Basecamp anymore.
const OAUTH_PROVIDERS = [
  { id: "github", label: "GitHub" },
  { id: "bitbucket", label: "Bitbucket" },
  { id: "google", label: "Google (SSO)" },
  { id: "basecamp", label: "Basecamp" }
];

function defaultApi() {
  const key = localStorage.getItem(STORAGE_KEY);
  return key ? new ApiClient(key) : null;
}

function readOAuthRedirectResult() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("integrations") !== "oauth") return null;
  return {
    status: params.get("status"),
    provider: params.get("provider"),
    account: params.get("account"),
    reason: params.get("reason")
  };
}

/**
 * IntegrationsDrillDown — "Integraciones" (SPEC_JARVIS.md §2).
 *
 * Minimal version: lists existing Auth Profiles (GET /auth-profiles) and lets
 * the user create a new one (POST /auth-profiles) with a plain form
 * (provider + account + scope, entered manually). The real OAuth/SSO-with-
 * Google flow is explicitly out of scope here (SPEC_JARVIS.md §11, pending
 * investigation) — this form is a stand-in until that's built, and says so.
 *
 * Props:
 *  - open, onClose — same DrillDown contract as the other drill-downs
 *  - api? — ApiClient instance; falls back to one built from the same
 *    localStorage ORQ_APP_KEY App.jsx already uses, consistent with the
 *    other drill-downs' self-contained pattern.
 */
export default function IntegrationsDrillDown({ open, onClose, api: apiProp }) {
  const api = apiProp || defaultApi();

  const [profiles, setProfiles] = useState(null);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ provider: "github", account: "", scope: "" });
  const [busy, setBusy] = useState(false);
  const [oauthResult, setOauthResult] = useState(readOAuthRedirectResult);

  const load = async () => {
    if (!api) {
      setError("No hay sesión activa.");
      return;
    }
    try {
      const data = await api.listAuthProfiles();
      setProfiles(Array.isArray(data) ? data : data?.profiles || []);
    } catch (err) {
      setError(err.message);
      setProfiles([]);
    }
  };

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    // Consume the ?integrations=oauth&... query params left by the backend's
    // redirect (app/routers/oauth.py's oauth_callback) exactly once, so a
    // page refresh doesn't keep re-showing "conectado" — and refresh the
    // profile list so the new OAuth-created Auth Profile shows up.
    if (!oauthResult) return;
    if (oauthResult.status === "success") load();
    const url = new URL(window.location.href);
    url.searchParams.delete("integrations");
    url.searchParams.delete("status");
    url.searchParams.delete("provider");
    url.searchParams.delete("account");
    url.searchParams.delete("reason");
    window.history.replaceState({}, "", url.toString());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnectOAuth = (providerId) => {
    if (!api) {
      setError("No hay sesión activa.");
      return;
    }
    // Real Authorization Code flow — top-level navigation so the provider's
    // own login/consent screen can render (can't be done via XHR/fetch).
    // The app's Bearer token can't travel on a browser redirect, so it goes
    // as ?app_key= instead (checked server-side in oauth.py's oauth_start).
    window.location.href = `${api.baseUrl}/auth-profiles/oauth/${providerId}/start?app_key=${encodeURIComponent(api.apiKey)}`;
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createAuthProfile(form);
      setForm({ provider: "github", account: "", scope: "" });
      setShowForm(false);
      await load();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <DrillDown open={open} onClose={onClose} label="Integraciones">
      <div className="pd-drilldown">
        <div className="pd-header">
          <h2>🔌 Integraciones</h2>
        </div>

        {oauthResult?.status === "success" && (
          <div className="flag flag-success">
            ✅ Conectado: {oauthResult.provider} — {oauthResult.account}
          </div>
        )}
        {oauthResult?.status === "error" && (
          <div className="flag">⚠️ No se pudo conectar ({oauthResult.reason || "error desconocido"}).</div>
        )}

        {error && <div className="flag">⚠️ {error}</div>}

        <div className="pd-subsection">
          <div className="pd-subsection-header">
            <h3>Conectar con OAuth real</h3>
          </div>
          <div className="pd-oauth-buttons">
            {OAUTH_PROVIDERS.map((p) => (
              <button key={p.id} className="btn-primary" onClick={() => handleConnectOAuth(p.id)}>
                Conectar con {p.label}
              </button>
            ))}
          </div>
          <p className="pd-meta">
            Cada botón redirige a la pantalla de login/consentimiento real del proveedor. Si el
            OAuth App de ese proveedor no está configurado todavía en el backend, el proveedor
            devuelve un error explícito en vez de fingir éxito.
          </p>
        </div>

        <div className="pd-subsection">
          <div className="pd-subsection-header">
            <h3>Auth Profiles {profiles ? `(${profiles.length})` : ""}</h3>
            {!showForm && (
              <button className="btn-primary" onClick={() => setShowForm(true)}>
                + Nuevo Auth Profile manual
              </button>
            )}
          </div>

          {profiles === null ? (
            <div className="loading">Cargando Auth Profiles...</div>
          ) : profiles.length === 0 && !showForm ? (
            <div className="empty-state">Sin Auth Profiles creados todavía.</div>
          ) : (
            <div className="evaluations-list">
              {(profiles || []).map((p) => (
                <div key={p.id} className="evaluation-item">
                  <div className="eval-header">
                    <span className="eval-agent">
                      {p.provider} — {p.account}
                    </span>
                    <span className="pd-meta">{p.auth_method === "oauth" ? "OAuth real" : "manual"}</span>
                  </div>
                  {p.scope && <div className="pd-meta">Scope: {p.scope}</div>}
                </div>
              ))}
            </div>
          )}

          {showForm && (
            <form onSubmit={handleCreate} className="pd-connect-repo-form">
              <select
                value={form.provider}
                onChange={(e) => setForm({ ...form, provider: e.target.value })}
              >
                <option value="github">github</option>
                <option value="gitlab">gitlab</option>
                <option value="basecamp">basecamp</option>
                <option value="google">google</option>
              </select>
              <input
                type="text"
                placeholder="account (email o usuario)"
                value={form.account}
                onChange={(e) => setForm({ ...form, account: e.target.value })}
                required
              />
              <input
                type="text"
                placeholder="scope (manual, ej: repo,read:org)"
                value={form.scope}
                onChange={(e) => setForm({ ...form, scope: e.target.value })}
              />
              <div className="modal-buttons">
                <button type="button" className="btn-cancel" onClick={() => setShowForm(false)} disabled={busy}>
                  Cancelar
                </button>
                <button type="submit" className="btn-success" disabled={busy}>
                  {busy ? "Creando..." : "Crear"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </DrillDown>
  );
}
