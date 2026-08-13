import React, { useEffect, useState } from "react";
import ApiClient from "../../api-client.js";
import DrillDown from "../CommandCenter/DrillDown.jsx";

const STORAGE_KEY = "ORQ_APP_KEY";

function defaultApi() {
  const key = localStorage.getItem(STORAGE_KEY);
  return key ? new ApiClient(key) : null;
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

        <div className="flag">
          ⚠️ OAuth real (SSO de Google, etc.) está pendiente de investigación
          (SPEC_JARVIS.md §11) — este formulario es un stand-in manual mientras
          tanto, no un flujo de autenticación real.
        </div>

        {error && <div className="flag">⚠️ {error}</div>}

        <div className="pd-subsection">
          <div className="pd-subsection-header">
            <h3>Auth Profiles {profiles ? `(${profiles.length})` : ""}</h3>
            {!showForm && (
              <button className="btn-primary" onClick={() => setShowForm(true)}>
                + Nuevo Auth Profile
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
