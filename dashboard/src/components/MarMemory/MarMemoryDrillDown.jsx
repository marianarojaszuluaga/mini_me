import React, { useState, useEffect, useCallback } from "react";
import DrillDown from "../CommandCenter/DrillDown.jsx";
import ApiClient from "../../api-client.js";
import "./mar-memory.css";

const STORAGE_KEY = "ORQ_APP_KEY";

function defaultApi() {
  const key = localStorage.getItem(STORAGE_KEY);
  return key ? new ApiClient(key) : null;
}

const TYPE_LABELS = {
  understanding: "🧠 Entendimiento",
  open_question: "❓ Pregunta abierta",
  correction: "✏️ Corrección"
};

const TYPE_ORDER = ["understanding", "open_question", "correction"];

// One entry: view mode by default, switches to an inline edit form on click.
const MemoryEntryCard = ({ entry, onSave, onDelete }) => {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(entry.content);
  const [type, setType] = useState(entry.type);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleSave = async () => {
    setBusy(true);
    setError("");
    try {
      await onSave({ id: entry.id, type, content, source: entry.source });
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
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {TYPE_ORDER.map((t) => (
            <option key={t} value={t}>
              {TYPE_LABELS[t]}
            </option>
          ))}
        </select>
        <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={3} />
        {error && <div className="mar-note mar-note-error">⚠️ {error}</div>}
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
      {error && <div className="mar-note mar-note-error">⚠️ {error}</div>}
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
  const [type, setType] = useState("understanding");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!content.trim()) return;
    setBusy(true);
    setError("");
    try {
      await onCreate({ type, content, source: "manual" });
      setContent("");
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <form className="mar-new-entry" onSubmit={handleSubmit}>
      <h3 className="mar-subtitle">Agregar entrada manual</h3>
      <select value={type} onChange={(e) => setType(e.target.value)}>
        {TYPE_ORDER.map((t) => (
          <option key={t} value={t}>
            {TYPE_LABELS[t]}
          </option>
        ))}
      </select>
      <textarea
        placeholder="Contenido de la entrada"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={3}
        required
      />
      {error && <div className="mar-note mar-note-error">⚠️ {error}</div>}
      <button type="submit" className="btn-primary" disabled={busy || !content.trim()}>
        {busy ? "Agregando..." : "+ Agregar"}
      </button>
    </form>
  );
};

export default function MarMemoryDrillDown({ open, onClose, api: apiProp }) {
  const api = apiProp || defaultApi();
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
    if (open) load();
  }, [open, load]);

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

  const grouped = TYPE_ORDER.map((type) => ({
    type,
    items: entries.filter((e) => e.type === type)
  }));

  return (
    <DrillDown open={open} onClose={onClose} label="Memoria de Mar">
      <div className="mar-drilldown">
        <div className="mar-header">
          <h1>🧠 Memoria de Mar</h1>
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cerrar
          </button>
        </div>

        {loading && <div className="mar-note">Cargando memoria...</div>}
        {error && <div className="mar-note mar-note-error">⚠️ {error}</div>}

        {!loading && !error && (
          <>
            {grouped.map(({ type, items }) => (
              <section key={type} className="mar-group">
                <h2 className="mar-group-title">
                  {TYPE_LABELS[type]} ({items.length})
                </h2>
                {items.length === 0 ? (
                  <div className="mar-note">Sin entradas todavía.</div>
                ) : (
                  <div className="mar-group-list">
                    {items.map((entry) => (
                      <MemoryEntryCard key={entry.id} entry={entry} onSave={handleSave} onDelete={handleDelete} />
                    ))}
                  </div>
                )}
              </section>
            ))}

            <section className="mar-group">
              <NewEntryForm onCreate={handleCreate} />
            </section>
          </>
        )}
      </div>
    </DrillDown>
  );
}
