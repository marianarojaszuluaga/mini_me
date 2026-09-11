import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AlertIcon, CheckIcon } from "../icons.jsx";

// ---------------------------------------------------------------------------
// Autobasecamp §5.3 — CRUD de BasecampNomenclatureRule por Card Table.
// A nivel de cuenta de Basecamp (§7.1, decisión de producto 2026-09-11) —
// varios proyectos de Minime que apuntan a Card Tables de la misma cuenta
// comparten este catálogo, cada rule sigue siendo per-card_table_key.
// ---------------------------------------------------------------------------

function emptyRule(accountId, cardTableKey, label) {
  return {
    account_id: accountId,
    card_table_key: cardTableKey,
    label,
    reserved_ranges: [],
    types: ["HU", "BUG", "HOTFIX"],
    translate_to_english: false,
  };
}

export function BasecampNomenclatureRules({ api, accountId, cardTables }) {
  const { t } = useTranslation();
  const [rules, setRules] = useState(null);
  const [error, setError] = useState("");

  const load = () => {
    api
      .listBasecampNomenclatureRules(accountId)
      .then((list) => {
        const byKey = Object.fromEntries(list.map((r) => [r.card_table_key, r]));
        setRules(
          cardTables.map(
            (ct) => byKey[ct.key] || emptyRule(accountId, ct.key, ct.label)
          )
        );
      })
      .catch((err) => setError(err.message));
  };

  useEffect(load, [api, accountId, cardTables]);

  if (error) return <div className="flag">{AlertIcon} {error}</div>;
  if (!rules) return <div className="loading">{t("basecamp.rules.loading")}</div>;

  return (
    <div className="pd-subsection">
      <div className="pd-subsection-header">
        <h3>{t("basecamp.rules.title")}</h3>
      </div>
      {rules.map((rule, i) => (
        <BasecampNomenclatureRuleRow
          key={rule.card_table_key}
          api={api}
          rule={rule}
          onSaved={(saved) =>
            setRules((prev) => prev.map((r, j) => (j === i ? saved : r)))
          }
        />
      ))}
    </div>
  );
}

function BasecampNomenclatureRuleRow({ api, rule, onSaved }) {
  const { t } = useTranslation();
  const [rangesText, setRangesText] = useState(
    (rule.reserved_ranges || []).map(([a, b]) => `${a}-${b}`).join(", ")
  );
  const [translate, setTranslate] = useState(!!rule.translate_to_english);
  const [saving, setSaving] = useState(false);
  const [warnings, setWarnings] = useState([]);
  const [error, setError] = useState("");

  const parseRanges = () =>
    rangesText
      .split(",")
      .map((chunk) => chunk.trim())
      .filter(Boolean)
      .map((chunk) => {
        const [a, b] = chunk.split("-").map((s) => Number(s.trim()));
        return [a, b];
      });

  const handleSave = async () => {
    setSaving(true);
    setError("");
    try {
      const saved = await api.upsertBasecampNomenclatureRule(rule.card_table_key, {
        account_id: rule.account_id,
        label: rule.label,
        reserved_ranges: parseRanges(),
        types: rule.types,
        translate_to_english: translate,
      });
      setWarnings(saved.overlap_warnings || []);
      onSaved?.(saved);
    } catch (err) {
      setError(err.message);
    }
    setSaving(false);
  };

  return (
    <div className="basecamp-card-table" style={{ marginBottom: 12 }}>
      <div className="basecamp-card-table-name">{rule.label}</div>
      <div>
        <label className="field-label">{t("basecamp.rules.rangesLabel")}</label>
        <input
          className="field-select"
          type="text"
          value={rangesText}
          onChange={(e) => setRangesText(e.target.value)}
          placeholder="1-199, 302-1000"
        />
      </div>
      <label className="basecamp-card-table-option">
        <input type="checkbox" checked={translate} onChange={(e) => setTranslate(e.target.checked)} />
        {t("basecamp.rules.translateLabel")}
      </label>

      {warnings.map((w, i) => (
        <div key={i} className="flag">{AlertIcon} {w}</div>
      ))}
      {error && <div className="flag">{AlertIcon} {error}</div>}

      <div className="modal-actions">
        <button type="button" className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? t("basecamp.rules.saving") : (<>{CheckIcon} {t("basecamp.rules.save")}</>)}
        </button>
      </div>
    </div>
  );
}
