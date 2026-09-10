import React, { useEffect, useState } from "react";
import { AlertIcon, CheckIcon } from "../icons.jsx";

// ---------------------------------------------------------------------------
// Basecamp Message Board Publisher — Fase 4 (frontend), 2026-09-09.
// Reusa exactamente los mismos patrones visuales de BasecampSection/
// BasecampLinkForm (ProjectDetailDrillDown.jsx): field-label/field-select de
// modal.css, flag/loading/empty-state/btn-* de styles.css, pd-subsection de
// command-center.css. Sin paleta ni componentes nuevos.
// ---------------------------------------------------------------------------

// HU-044 E-3 — mapea el `last_error` técnico de
// app/services/basecamp_publisher.py a un mensaje legible. Función pura,
// sin dependencias, exportada para poder testearla aparte.
export function errorMessageMap(lastError) {
  if (!lastError) return "Ocurrió un error al publicar en Basecamp.";
  if (lastError.includes("Sesión de Basecamp expirada")) {
    return "La sesión de Basecamp expiró — reconecta la cuenta desde Auth Profiles.";
  }
  if (lastError.includes("Rate limit")) {
    return "Basecamp está limitando las publicaciones por ahora — se reintentará automáticamente.";
  }
  if (/Basecamp respondió 5\d\d/.test(lastError)) {
    return "Basecamp tuvo un problema temporal — se reintentará automáticamente.";
  }
  if (lastError.includes("rechazó el payload")) {
    return "Basecamp rechazó la publicación — puede que la categoría o el Message Board ya no existan.";
  }
  return lastError;
}

export function BasecampPublishSettings({ api, project }) {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getBasecampPublishConfig(project.id).then(setConfig).catch((err) => setError(err.message));
  }, [api, project.id]);

  // NOTA (decisión propia): el backend valida `category_id` contra
  // list_categories() real en el PUT (400 si no existe) pero no hay todavía
  // un GET dedicado para listar categorías en el picker — se deja como
  // input numérico simple en vez de inventar un endpoint no pedido por el
  // plan. Si se agrega un GET .../basecamp-categories más adelante, este
  // campo pasa a selector real sin cambiar el resto del componente.

  const handleField = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const saved = await api.setBasecampPublishConfig(project.id, config);
      setConfig(saved);
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  if (error && !config) {
    return <div className="flag">{AlertIcon} {error}</div>;
  }
  if (!config) return <div className="loading">Cargando configuración de publicación...</div>;

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>Publicar en Message Board</h3>
      </div>

      <label className="basecamp-card-table-option">
        <input
          type="checkbox"
          checked={!!config.enabled}
          onChange={(e) => handleField("enabled", e.target.checked)}
        />
        Publicar automáticamente al iniciar/cerrar sprint
      </label>

      {config.enabled && (
        <>
          <label className="basecamp-card-table-option">
            <input
              type="checkbox"
              checked={!!config.publish_on_start}
              onChange={(e) => handleField("publish_on_start", e.target.checked)}
            />
            Publicar al iniciar sprint
          </label>
          <label className="basecamp-card-table-option">
            <input
              type="checkbox"
              checked={!!config.publish_on_close}
              onChange={(e) => handleField("publish_on_close", e.target.checked)}
            />
            Publicar al cerrar sprint
          </label>

          <div>
            <label className="field-label">Category ID (opcional)</label>
            <input
              className="field-select"
              type="number"
              value={config.category_id ?? ""}
              onChange={(e) => handleField("category_id", e.target.value === "" ? null : Number(e.target.value))}
              placeholder="Sin categoría"
            />
          </div>

          <div>
            <label className="field-label">Personas a notificar (IDs separados por coma)</label>
            <input
              className="field-select"
              type="text"
              value={(config.notify_person_ids || []).join(", ")}
              onChange={(e) =>
                handleField(
                  "notify_person_ids",
                  e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean)
                    .map(Number)
                )
              }
              placeholder="123, 456"
            />
          </div>
        </>
      )}

      {error && <div className="flag">{AlertIcon} {error}</div>}
      <div className="modal-actions">
        <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Guardando..." : "Guardar"}
        </button>
      </div>
    </div>
  );
}

// HU-044 — 3 estados reales + oculto si publish.enabled es false. Se renderiza
// por sprint (= Card Table id, §4a del plan), listando cada publicación de
// ese sprint (sprint.started / sprint.closed, cada evento es su propia fila).
export function SprintPublicationStatus({ api, project, sprintId, publishEnabled }) {
  const [publications, setPublications] = useState(null);
  const [error, setError] = useState("");

  const refresh = () => {
    api
      .listSprintPublications(project.id, sprintId)
      .then(setPublications)
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    if (!publishEnabled) return;
    refresh();
    // El reintento perezoso (plan §1.1 Opción A) se dispara del lado del
    // backend en este mismo GET — un poll periódico corto es lo que hace
    // que un `pending` con backoff cumplido se resuelva sin acción manual.
    const interval = setInterval(refresh, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, project.id, sprintId, publishEnabled]);

  if (!publishEnabled) return null; // HU-044 — oculto si la publicación está desactivada
  if (error) return <div className="flag">{AlertIcon} {error}</div>;
  if (!publications) return <div className="loading">Cargando estado de publicación...</div>;
  if (publications.length === 0) return null;

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>Publicaciones en Basecamp</h3>
      </div>
      {publications.map((pub) => (
        <div key={pub.id} className="basecamp-card" style={{ marginBottom: 6 }}>
          <strong>{pub.event_type === "sprint.started" ? "Inicio" : "Cierre"}</strong>{" "}
          {pub.status === "sent" && (
            <span>
              {CheckIcon} Publicado{" "}
              <a href={pub.basecamp_url} target="_blank" rel="noreferrer">Ver post ↗</a>
            </span>
          )}
          {pub.status === "pending" && (
            <span>
              Publicando…{" "}
              <button className="btn-secondary" disabled>Reintentar</button>
            </span>
          )}
          {pub.status === "failed" && (
            <span>
              {AlertIcon} Falló — {errorMessageMap(pub.last_error)}{" "}
              <RetryPublicationButton api={api} publicationId={pub.id} onRetried={refresh} />
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

export function RetryPublicationButton({ api, publicationId, onRetried }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleRetry = async () => {
    setBusy(true);
    setError("");
    try {
      await api.retryBasecampPublication(publicationId);
      onRetried?.();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <>
      <button className="btn-primary" onClick={handleRetry} disabled={busy}>
        {busy ? "Reintentando..." : "Reintentar"}
      </button>
      {error && <span className="flag">{AlertIcon} {error}</span>}
    </>
  );
}
