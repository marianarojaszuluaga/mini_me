import React, { useEffect, useState } from "react";
import ApiClient from "../../api-client.js";
import Modal from "../Modal/Modal.jsx";

const STORAGE_KEY = "ORQ_APP_KEY";

// Providers with a real OAuth App wired up server-side (app/routers/oauth.py).
// Basecamp joined 2026-08-14 (37signals Launchpad OAuth) — the manual form
// below stays as a fallback for any provider whose OAuth App isn't
// configured yet, not specifically for Basecamp anymore.
const OAUTH_PROVIDERS = [
  {
    id: "github",
    label: "GitHub",
    sub: "Repos + Pull Requests",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M12 .5C5.6.5.5 5.6.5 12c0 5.1 3.3 9.4 7.9 11 .6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.6-.3-5.3-1.3-5.3-5.8 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.3 1.2.9-.3 2-.4 3-.4s2.1.1 3 .4c2.3-1.5 3.3-1.2 3.3-1.2.7 1.6.2 2.8.1 3.1.8.8 1.2 1.9 1.2 3.1 0 4.5-2.7 5.5-5.3 5.8.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6 4.6-1.6 7.9-5.9 7.9-11C23.5 5.6 18.4.5 12 .5z" />
      </svg>
    )
  },
  {
    id: "bitbucket",
    label: "Bitbucket",
    sub: "Repos + Pull Requests",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M2.5 2l3.3 20 6.2-1.3L18.3 2H2.5zm13.6 4.2l-1.6 9.9-5.8 1.2-2.5-9.8 9.9-1.3z" />
      </svg>
    )
  },
  {
    id: "google",
    label: "Google (SSO)",
    sub: "SSO — @imagineapps.co",
    icon: (
      <svg viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.5 12.2c0-.8-.1-1.5-.2-2.2H12v4.3h5.9c-.3 1.4-1 2.5-2.2 3.3v2.8h3.6c2.1-1.9 3.2-4.8 3.2-8.2z" />
        <path fill="#34A853" d="M12 23c3 0 5.4-1 7.2-2.6l-3.6-2.8c-1 .7-2.2 1.1-3.6 1.1-2.8 0-5.2-1.9-6-4.4H2.3v2.8C4.1 20.6 7.8 23 12 23z" />
        <path fill="#FBBC05" d="M6 14.3c-.2-.7-.4-1.4-.4-2.3s.1-1.5.4-2.3V6.9H2.3C1.5 8.5 1 10.2 1 12s.5 3.5 1.3 5.1L6 14.3z" />
        <path fill="#EA4335" d="M12 5.4c1.6 0 3.1.6 4.2 1.6l3.2-3.2C17.4 2 15 1 12 1 7.8 1 4.1 3.4 2.3 6.9l3.7 2.9c.8-2.5 3.2-4.4 6-4.4z" />
      </svg>
    )
  },
  {
    id: "basecamp",
    label: "Basecamp",
    sub: "Proyectos + sprints (link a tareas)",
    icon: (
      <svg viewBox="0 0 24 24" fill="currentColor">
        <path d="M4 3h16a1 1 0 011 1v16a1 1 0 01-1 1H4a1 1 0 01-1-1V4a1 1 0 011-1zm3 5v9h2V8H7zm4 3v6h2v-6h-2zm4-2v8h2V9h-2z" />
      </svg>
    )
  }
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
 * IntegrationsDrillDown — "Integraciones" (SPEC_JARVIS.md §2), now the exact
 * mockup modal (Fase F): oauth-row list + manual Auth Profile fallback form.
 *
 * Props:
 *  - open, onClose — same Modal contract as the other modals
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

  const icon = (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 2v4M15 2v4M6 10h12a1 1 0 011 1v3a5 5 0 01-5 5h-4a5 5 0 01-5-5v-3a1 1 0 011-1z" />
    </svg>
  );

  return (
    <Modal open={open} onClose={onClose} title="Integraciones" icon={icon}>
      {oauthResult?.status === "success" && (
        <div className="flag flag-success">
          ✅ Conectado: {oauthResult.provider} — {oauthResult.account}
        </div>
      )}
      {oauthResult?.status === "error" && (
        <div className="flag">⚠️ No se pudo conectar ({oauthResult.reason || "error desconocido"}).</div>
      )}
      {error && <div className="flag">⚠️ {error}</div>}

      <div className="rail-section-label" style={{ marginBottom: 0 }}>
        Conectar con OAuth real
      </div>
      {OAUTH_PROVIDERS.map((p) => (
        <div key={p.id} className="oauth-row">
          <div className="oauth-row-icon">{p.icon}</div>
          <div style={{ flex: 1 }}>
            <div className="oauth-row-label">{p.label}</div>
            <div className="oauth-row-sub">{p.sub}</div>
          </div>
          <button className="btn-secondary" onClick={() => handleConnectOAuth(p.id)}>
            Conectar
          </button>
        </div>
      ))}
      <div className="modal-note">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 9v4M12 17h.01" />
          <circle cx="12" cy="12" r="9" />
        </svg>
        Si el OAuth App de un proveedor no está configurado todavía, el sistema devuelve un error
        explícito — nunca finge una conexión exitosa.
      </div>

      <div className="pd-subsection">
        <div className="pd-subsection-header">
          <h3>Auth Profiles {profiles ? `(${profiles.length})` : ""}</h3>
          {!showForm && (
            <button className="btn-secondary" onClick={() => setShowForm(true)}>
              + Manual
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
              className="field-select"
              value={form.provider}
              onChange={(e) => setForm({ ...form, provider: e.target.value })}
            >
              <option value="github">github</option>
              <option value="gitlab">gitlab</option>
              <option value="basecamp">basecamp</option>
              <option value="google">google</option>
            </select>
            <input
              className="field-input"
              type="text"
              placeholder="account (email o usuario)"
              value={form.account}
              onChange={(e) => setForm({ ...form, account: e.target.value })}
              required
            />
            <input
              className="field-input"
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
    </Modal>
  );
}
