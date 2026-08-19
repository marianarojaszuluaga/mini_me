import React, { useState } from "react";
import Modal from "./Modal.jsx";

const ALERT_ICON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 9v4M12 17h.01" />
    <circle cx="12" cy="12" r="9" />
  </svg>
);

/**
 * DestructiveActionModal — real type-to-confirm pattern (Geist's
 * "destructive-action-modal": title/description, type the resource name to
 * unlock the confirm button, an explicit "cannot be undone" band). Used for
 * project deletion — the mockup never showed this flow, so this follows the
 * real Geist spec fetched from vercel.com/geist/destructive-action-modal
 * rather than inventing one.
 *
 * Props:
 *  - open, onClose
 *  - title: string ("Eliminar proyecto")
 *  - description: ReactNode (names the consequence + resource)
 *  - verificationPhrase: string — what the user must type (the project name)
 *  - verificationLabel: string — what to call that phrase in the field label
 *  - confirmLabel: string — matches the title 1:1
 *  - onConfirm: () => Promise<void>
 */
export default function DestructiveActionModal({
  open,
  onClose,
  title,
  icon,
  description,
  verificationPhrase,
  verificationLabel,
  confirmLabel,
  bandText,
  onConfirm
}) {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const handleClose = () => {
    setTyped("");
    setError("");
    onClose();
  };

  const handleConfirm = async () => {
    setBusy(true);
    setError("");
    try {
      await onConfirm();
      setTyped("");
    } catch (err) {
      setError(err.message || "No se pudo completar la acción.");
    }
    setBusy(false);
  };

  return (
    <Modal open={open} onClose={handleClose} title={title} icon={icon || ALERT_ICON}>
      <div>{description}</div>
      <div>
        <label className="field-label">
          Escribe "{verificationPhrase}" ({verificationLabel}) para confirmar
        </label>
        <input
          className="field-input"
          type="text"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoFocus
        />
      </div>
      <div className="modal-note">
        {ALERT_ICON}
        {bandText || `${confirmLabel} — esta acción no se puede deshacer.`}
      </div>
      {error && <div className="flag">{ALERT_ICON} {error}</div>}
      <div className="modal-actions">
        <button type="button" className="btn-cancel" onClick={handleClose} disabled={busy}>
          Cancelar
        </button>
        <button
          type="button"
          className="btn-danger"
          onClick={handleConfirm}
          disabled={busy || typed !== verificationPhrase}
        >
          {busy ? "Eliminando..." : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
