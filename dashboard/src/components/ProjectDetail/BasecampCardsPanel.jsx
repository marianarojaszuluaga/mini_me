import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import Modal from "../Modal/Modal.jsx";
import { AlertIcon, CheckIcon } from "../icons.jsx";

// ---------------------------------------------------------------------------
// Autobasecamp (SPEC_AUTOBASECAMP.md) — Fases 1, 2 y 4 del frontend:
// crear/editar cards (§5.1), auditoría de nomenclatura (§5.2), bulk create
// (§5.4). Mismo patrón visual que BasecampPublishSettings.jsx: pd-subsection,
// field-label/field-select, btn-*, sin paleta ni componentes nuevos.
// ---------------------------------------------------------------------------

const CARD_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 4h16v16H4z" />
    <path d="M8 9h8M8 13h5" />
  </svg>
);

export function BasecampCardsPanel({ api, project }) {
  const { t } = useTranslation();
  const [cardTables, setCardTables] = useState(null);
  const [selectedTableId, setSelectedTableId] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editingCard, setEditingCard] = useState(null);
  const [showAudit, setShowAudit] = useState(false);
  const [showBulk, setShowBulk] = useState(false);

  const tableIds = (project.basecamp && project.basecamp.selectedCardTableIds) || [];

  useEffect(() => {
    if (!tableIds.length) {
      setCardTables([]);
      return;
    }
    api
      .listProjectCardTables(project.id)
      .then((all) => {
        const linked = all.filter((t) => tableIds.includes(t.id));
        setCardTables(linked);
        if (linked[0]) setSelectedTableId(linked[0].id);
      })
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, project.id]);

  const loadSnapshot = () => {
    if (!selectedTableId) return;
    api
      .getProjectBasecampMirror(project.id)
      .then((mirror) => {
        const table = (mirror.cardTables || []).find((ct) => ct.id === selectedTableId) || mirror.cardTables?.[0];
        setSnapshot(table || null);
      })
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    loadSnapshot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTableId]);

  if (!tableIds.length) {
    return (
      <div className="pd-subsection">
        <div className="pd-subsection-header">
          <h3>{t("basecamp.cardsPanel.title")}</h3>
        </div>
        <div className="pv-empty-cta-list">
          <span>{t("basecamp.cardsPanel.noCardTables")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>{t("basecamp.cardsPanel.title")}</h3>
        <div>
          <button className="btn-secondary" onClick={() => setShowAudit(true)}>
            {t("basecamp.cardsPanel.auditButton")}
          </button>{" "}
          <button className="btn-secondary" onClick={() => setShowBulk(true)}>
            {t("basecamp.cardsPanel.bulkButton")}
          </button>{" "}
          <button className="btn-primary" onClick={() => setShowCreate(true)}>
            {t("basecamp.cardsPanel.newCardButton")}
          </button>
        </div>
      </div>

      <div>
        <label className="field-label">{t("basecamp.cardsPanel.tableSelectLabel")}</label>
        <select
          className="field-select"
          value={selectedTableId || ""}
          onChange={(e) => setSelectedTableId(e.target.value)}
        >
          {(cardTables || []).map((ct) => (
            <option key={ct.id} value={ct.id}>
              {ct.title || ct.name}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="flag">{AlertIcon} {error}</div>}

      {snapshot && (
        <div className="basecamp-card-table" style={{ marginTop: 12 }}>
          {(snapshot.columns || []).map((col, i) => (
            <div key={i} className="basecamp-card-table-column">
              <div className="basecamp-column-name">
                {col.name} ({col.cards.length})
              </div>
              {col.cards.map((card, j) => (
                <div key={j} className="basecamp-card">
                  <span>{card.title}</span>
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => setEditingCard({ ...card, listId: col.id, listName: col.name })}
                  >
                    {t("basecamp.cardsPanel.editButton")}
                  </button>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <Modal open onClose={() => setShowCreate(false)} title={t("basecamp.cardsPanel.newCardModalTitle")} icon={CARD_ICON}>
          <BasecampCardForm
            api={api}
            project={project}
            tableId={selectedTableId}
            columns={snapshot ? snapshot.columns : []}
            onSaved={() => {
              setShowCreate(false);
              loadSnapshot();
            }}
            onCancel={() => setShowCreate(false)}
          />
        </Modal>
      )}

      {editingCard && (
        <Modal open onClose={() => setEditingCard(null)} title={t("basecamp.cardsPanel.editCardModalTitle")} icon={CARD_ICON}>
          <BasecampCardForm
            api={api}
            project={project}
            tableId={selectedTableId}
            columns={snapshot ? snapshot.columns : []}
            editingCard={editingCard}
            onSaved={() => {
              setEditingCard(null);
              loadSnapshot();
            }}
            onCancel={() => setEditingCard(null)}
          />
        </Modal>
      )}

      {showAudit && (
        <Modal open onClose={() => setShowAudit(false)} title={t("basecamp.audit.title")} icon={CARD_ICON}>
          <BasecampNomenclatureAudit api={api} project={project} cardTables={cardTables || []} />
        </Modal>
      )}

      {showBulk && (
        <Modal open onClose={() => setShowBulk(false)} title={t("basecamp.bulk.title")} icon={CARD_ICON}>
          <BasecampBulkCreate
            api={api}
            project={project}
            columns={snapshot ? snapshot.columns : []}
            onDone={() => {
              setShowBulk(false);
              loadSnapshot();
            }}
          />
        </Modal>
      )}
    </div>
  );
}

// §5.1 — modal de crear/editar card, título compuesto asistido.
function BasecampCardForm({ api, project, tableId, columns, editingCard, onSaved, onCancel }) {
  const { t } = useTranslation();
  const [type, setType] = useState("HU");
  const [module_, setModule] = useState("");
  const [descriptor, setDescriptor] = useState("");
  const [listId, setListId] = useState(editingCard ? editingCard.listId : (columns[0] && columns[0].id) || "");
  const [content, setContent] = useState("");
  const [dueOn, setDueOn] = useState("");
  const [people, setPeople] = useState([]);
  const [assigneeId, setAssigneeId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listBasecampPeople(project.id).then(setPeople).catch(() => setPeople([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const composedTitle = editingCard
    ? editingCard.title
    : `${type}-${module_ ? "-" + module_ : ""}${descriptor ? ": " + descriptor : ""}`;

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      if (editingCard) {
        await api.updateBasecampCard(project.id, editingCard.id, {
          content: content || undefined,
          due_on: dueOn || undefined,
        });
      } else {
        await api.createBasecampCard(project.id, tableId, {
          list_id: listId,
          title: composedTitle,
          content: content || undefined,
          due_on: dueOn || undefined,
          assignee_ids: assigneeId ? [Number(assigneeId)] : undefined,
        });
      }
      onSaved?.();
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <div>
      {!editingCard && (
        <>
          <div>
            <label className="field-label">{t("basecamp.cardForm.typeLabel")}</label>
            <select className="field-select" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="HU">HU</option>
              <option value="BUG">BUG</option>
              <option value="HOTFIX">HOTFIX</option>
            </select>
          </div>
          <div>
            <label className="field-label">{t("basecamp.cardForm.moduleLabel")}</label>
            <input className="field-select" type="text" value={module_} onChange={(e) => setModule(e.target.value)} />
          </div>
          <div>
            <label className="field-label">{t("basecamp.cardForm.descriptorLabel")}</label>
            <input
              className="field-select"
              type="text"
              value={descriptor}
              onChange={(e) => setDescriptor(e.target.value)}
            />
          </div>
          <div>
            <label className="field-label">{t("basecamp.cardForm.columnLabel")}</label>
            <select className="field-select" value={listId} onChange={(e) => setListId(e.target.value)}>
              {columns.map((col) => (
                <option key={col.id} value={col.id}>
                  {col.name}
                </option>
              ))}
            </select>
          </div>
          <div className="pd-meta">{t("basecamp.cardForm.preview")}: <strong>{composedTitle}</strong></div>
        </>
      )}
      <div>
        <label className="field-label">{t("basecamp.cardForm.contentLabel")}</label>
        <textarea className="field-select" value={content} onChange={(e) => setContent(e.target.value)} rows={3} />
      </div>
      <div>
        <label className="field-label">{t("basecamp.cardForm.dueOnLabel")}</label>
        <input className="field-select" type="date" value={dueOn} onChange={(e) => setDueOn(e.target.value)} />
      </div>
      {!editingCard && (
        <div>
          <label className="field-label">{t("basecamp.cardForm.assigneeLabel")}</label>
          <select className="field-select" value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
            <option value="">{t("basecamp.cardForm.assigneeNone")}</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {error && <div className="flag">{AlertIcon} {error}</div>}
      <div className="modal-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>
          {t("basecamp.cardForm.cancel")}
        </button>
        <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? t("basecamp.cardForm.saving") : t("basecamp.cardForm.save")}
        </button>
      </div>
    </div>
  );
}

// §5.2 — auditoría de nomenclatura: selector multi-tabla, 3 bloques,
// checkbox por fila, "Aplicar seleccionados" (nunca todo por default).
export function BasecampNomenclatureAudit({ api, project, cardTables }) {
  const { t } = useTranslation();
  const [selectedTables, setSelectedTables] = useState(cardTables.map((t) => t.id));
  const [result, setResult] = useState(null);
  const [selectedFixes, setSelectedFixes] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const toggleTable = (id) => {
    setSelectedTables((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const runAudit = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api.runBasecampNomenclatureAudit(project.id, selectedTables);
      setResult(res);
      setSelectedFixes({});
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const toggleFix = (cardId, title) => {
    setSelectedFixes((prev) => {
      const next = { ...prev };
      if (next[cardId]) delete next[cardId];
      else next[cardId] = title;
      return next;
    });
  };

  const applyFixes = async () => {
    setBusy(true);
    setError("");
    try {
      const fixes = Object.entries(selectedFixes).map(([card_id, new_title]) => ({ card_id, new_title }));
      await api.applyBasecampNomenclatureFixes(project.id, fixes);
      await runAudit();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const renderBlock = (title, findings) => (
    <div style={{ marginBottom: 16 }}>
      <h4>{title} ({findings.length})</h4>
      {findings.map((f) => (
        <div key={f.card.id} className="basecamp-card">
          {f.suggested_title && (
            <input
              type="checkbox"
              checked={!!selectedFixes[f.card.id]}
              onChange={() => toggleFix(f.card.id, f.suggested_title)}
            />
          )}
          <span>{f.card.title}</span>
          {f.suggested_title && <span> → {f.suggested_title}</span>}
          {f.suggested_translation && (
            <div className="pd-meta">{t("basecamp.audit.translationSuggestion")}: {f.suggested_translation}</div>
          )}
          <div className="pd-meta">{f.reason}</div>
          {f.card.url && (
            <a href={f.card.url} target="_blank" rel="noreferrer">
              {t("basecamp.audit.viewInBasecamp")}
            </a>
          )}
        </div>
      ))}
    </div>
  );

  return (
    <div>
      <div className="basecamp-card-table-picker">
        {cardTables.map((ct) => (
          <label key={ct.id} className="basecamp-card-table-option">
            <input type="checkbox" checked={selectedTables.includes(ct.id)} onChange={() => toggleTable(ct.id)} />
            {ct.title || ct.name}
          </label>
        ))}
      </div>
      <div className="modal-actions">
        <button type="button" className="btn-primary" onClick={runAudit} disabled={busy || !selectedTables.length}>
          {busy ? t("basecamp.audit.running") : t("basecamp.audit.run")}
        </button>
      </div>

      {error && <div className="flag">{AlertIcon} {error}</div>}

      {result && (
        <>
          {renderBlock(t("basecamp.audit.duplicates"), result.duplicates)}
          {renderBlock(t("basecamp.audit.missing"), result.missing)}
          {renderBlock(t("basecamp.audit.crossTable"), result.cross_table_violations)}

          <div className="modal-actions">
            <button
              type="button"
              className="btn-primary"
              onClick={applyFixes}
              disabled={busy || Object.keys(selectedFixes).length === 0}
            >
              {CheckIcon} {t("basecamp.audit.applySelected")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// §5.4 — bulk create genérico: pegar filas (columna, título, contenido,
// fecha), preview antes de crear. El segundo parser (milestones-v2.md /
// dod-by-milestone/*.md, §7.4) convierte a este mismo formato de filas
// antes de llegar acá — no duplica la lógica de creación.
export function BasecampBulkCreate({ api, project, columns, onDone }) {
  const { t } = useTranslation();
  const [pastedCsv, setPastedCsv] = useState("");
  const [rows, setRows] = useState([]);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const parseCsv = () => {
    const lines = pastedCsv.split("\n").map((l) => l.trim()).filter(Boolean);
    const parsedRows = lines.map((line) => {
      const [column, title, content, date] = line.split(",").map((s) => (s || "").trim());
      return { column, title, content, date };
    });
    setRows(parsedRows);
  };

  const runPreview = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api.previewBasecampBulkCards(project.id, rows);
      setPreview(res.preview);
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  const runCreate = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api.bulkCreateBasecampCards(project.id, rows);
      setResult(res);
      onDone?.();
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  return (
    <div>
      <p className="pd-meta">{t("basecamp.bulk.helpText")}</p>
      <textarea
        className="field-select"
        rows={6}
        placeholder={t("basecamp.bulk.placeholder")}
        value={pastedCsv}
        onChange={(e) => setPastedCsv(e.target.value)}
      />
      <div className="modal-actions">
        <button type="button" className="btn-secondary" onClick={parseCsv}>
          {t("basecamp.bulk.parse")}
        </button>
        <button type="button" className="btn-secondary" onClick={runPreview} disabled={!rows.length || busy}>
          {t("basecamp.bulk.preview")}
        </button>
      </div>

      {preview && (
        <div className="basecamp-card-table" style={{ marginTop: 12 }}>
          {preview.map((row, i) => (
            <div key={i} className="basecamp-card">
              <strong>{row.list_id}</strong>: {row.title} {row.due_on ? `(${row.due_on})` : ""}
            </div>
          ))}
          <div className="modal-actions">
            <button type="button" className="btn-primary" onClick={runCreate} disabled={busy}>
              {busy ? t("basecamp.bulk.creating") : t("basecamp.bulk.create")}
            </button>
          </div>
        </div>
      )}

      {error && <div className="flag">{AlertIcon} {error}</div>}
      {result && (
        <div className="pd-meta">
          {CheckIcon} {t("basecamp.bulk.created", { count: result.created.length })}
          {result.failed.length > 0 && <div className="flag">{AlertIcon} {t("basecamp.bulk.failed", { count: result.failed.length })}</div>}
        </div>
      )}
    </div>
  );
}
