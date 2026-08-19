import React, { useState, useEffect, useCallback } from "react";
import DrillDown from "../CommandCenter/DrillDown.jsx";
import ApiClient from "../../api-client.js";
import { BrainIcon, AlertIcon } from "../icons.jsx";
import "./mar-memory.css";

const STORAGE_KEY = "ORQ_APP_KEY";

function defaultApi() {
  const key = localStorage.getItem(STORAGE_KEY);
  return key ? new ApiClient(key) : null;
}

// Simplified 2026-08-14 (Mariana: "Déjalo sólo como memoria") — a single
// flat list, no type grouping/labels in the UI. `type` still travels to the
// backend (the schema requires it) but defaults silently to "understanding"
// since the user no longer picks it.
const DEFAULT_TYPE = "understanding";

// Groups entries by real calendar day (Hoy / Ayer / fecha) — Mariana:
// "el drill down de memoria [necesita] una estructura más organizada/agrupada"
// (2026-08-19). Order is newest-first, entries within a day keep their
// original (creation) order.
function groupEntriesByDay(entries) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const groups = new Map();
  for (const entry of entries) {
    const created = entry.createdAt ? new Date(entry.createdAt) : null;
    let label;
    if (!created || Number.isNaN(created.getTime())) {
      label = "Sin fecha";
    } else {
      const day = new Date(created);
      day.setHours(0, 0, 0, 0);
      if (day.getTime() === today.getTime()) label = "Hoy";
      else if (day.getTime() === yesterday.getTime()) label = "Ayer";
      else label = day.toLocaleDateString("es", { day: "numeric", month: "long", year: "numeric" });
    }
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(entry);
  }
  return Array.from(groups.entries());
}

// One entry: view mode by default, switches to an inline edit form on click.
const MemoryEntryCard = ({ entry, onSave, onDelete }) => {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(entry.content);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    setBusy(true);
    setError("");
    try {
      await onSave({ id: entry.id, type: entry.type || DEFAULT_TYPE, content, source: entry.source });
      setEditing(false);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const handleDelete = async () => {
    setBusy(true);
    setError("");
    try {
      await onDelete(entry.id);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <div className="mar-entry mar-entry-editing">
        <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={3} />
        {error && <div className="mar-note mar-note-error">{AlertIcon} {error}</div>}
        <div className="mar-entry-actions">
          <button type="button" className="btn-cancel" onClick={() => setEditing(false)} disabled={busy}>
            Cancelar
          </button>
          <button type="button" className="btn-success" onClick={handleSave} disabled={busy || !content.trim()}>
            {busy ? "Guardando..." : "Guardar"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mar-entry">
      <div className="mar-entry-content">{entry.content}</div>
      <div className="mar-entry-meta">
        <span>{entry.source === "manual" ? "manual" : "desde chat"}</span>
        <span>{entry.createdAt ? new Date(entry.createdAt).toLocaleString() : ""}</span>
      </div>
      {error && <div className="mar-note mar-note-error">{AlertIcon} {error}</div>}
      <div className="mar-entry-actions">
        <button type="button" className="btn-cancel" onClick={() => setEditing(true)} disabled={busy}>
          Editar
        </button>
        <button type="button" className="btn-danger" onClick={handleDelete} disabled={busy}>
          {busy ? "Borrando..." : "Borrar"}
        </button>
      </div>
    </div>
  );
};

const NewEntryForm = ({ onCreate }) => {
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;
    setBusy(true);
    setError("");
    try {
      await onCreate({ type: DEFAULT_TYPE, content, source: "manual" });
      setContent("");
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <form className="mar-new-entry" onSubmit={handleSubmit}>
      <h3 className="mar-subtitle">Agregar entrada manual</h3>
      <textarea
        placeholder="Contenido de la entrada"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={3}
        required
      />
      {error && <div className="mar-note mar-note-error">{AlertIcon} {error}</div>}
      <button type="submit" className="btn-primary" disabled={busy || !content.trim()}>
        {busy ? "Agregando..." : "+ Agregar"}
      </button>
    </form>
  );
};

function MarMemoryBody({ api }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!api) {
      setError("No hay App API Key configurada.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await api.listMarMemory();
      setEntries(data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (entry) => {
    const updated = await api.upsertMarMemoryEntry(entry);
    setEntries((prev) => {
      const exists = prev.some((e) => e.id === updated.id);
      return exists ? prev.map((e) => (e.id === updated.id ? updated : e)) : [...prev, updated];
    });
  };

  const handleDelete = async (id) => {
    await api.deleteMarMemoryEntry(id);
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  const handleCreate = async (entry) => {
    const created = await api.upsertMarMemoryEntry(entry);
    setEntries((prev) => [...prev, created]);
  };

  return (
    <>
      <div className="mar-backup-badge">
        Respaldado automáticamente en Obsidian — carpeta{" "}
        <code>Orquestrador 360 - Memoria de la App</code>, cada 3h
      </div>

      {loading && <div className="mar-note">Cargando memoria...</div>}
      {error && <div className="mar-note mar-note-error">{AlertIcon} {error}</div>}

      {!loading && !error && (
        <>
          {entries.length === 0 ? (
            <div className="mar-note">Sin entradas todavía.</div>
          ) : (
            groupEntriesByDay(
              [...entries].sort((a, b) => new Date(b.createdAt || 0) - new Date(a.createdAt || 0))
            ).map(([label, groupEntries]) => (
              <section key={label} className="mar-group">
                <h3 className="mar-group-title">{label}</h3>
                <div className="mar-group-list">
                  {groupEntries.map((entry) => (
                    <MemoryEntryCard key={entry.id} entry={entry} onSave={handleSave} onDelete={handleDelete} />
                  ))}
                </div>
              </section>
            ))
          )}
          <section className="mar-group">
            <NewEntryForm onCreate={handleCreate} />
          </section>
        </>
      )}
    </>
  );
}

export default function MarMemoryDrillDown({ open, onClose, api: apiProp, fullPage = false }) {
  const api = apiProp || defaultApi();

  if (fullPage) {
    return (
      <div className="mar-drilldown mar-drilldown-fullpage">
        <MarMemoryBody api={api} />
      </div>
    );
  }

  return (
    <DrillDown open={open} onClose={onClose} label="Memoria de Mar">
      <div className="mar-drilldown">
        <div className="mar-header">
          <h1>
            <span className="mar-header-icon">{BrainIcon}</span> Memoria de Mar
          </h1>
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cerrar
          </button>
        </div>
        {open && <MarMemoryBody api={api} />}
      </div>
    </DrillDown>
  );
}
