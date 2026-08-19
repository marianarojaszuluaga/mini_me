import React from "react";
import "./modal.css";

/**
 * Modal — shared shell matching the mockup's `.modal-backdrop`/`.modal`
 * exactly (Fase F, plan "UI 100% fiel al mockup"). Used by Integraciones,
 * Nuevo proyecto, and Configuración — the three real form-shaped modals in
 * the app. (Proyectos/Dashboard/Memoria de Mar/Detalle de proyecto are full
 * pages, not modals, and keep their own DrillDown-based overlay for now.)
 *
 * Props:
 *  - open, onClose
 *  - title: string
 *  - icon?: ReactNode — small icon shown before the title
 *  - children: modal body content
 *  - actions?: ReactNode — rendered in the footer action row (buttons)
 */
export default function Modal({ open, onClose, title, icon, children, actions }) {
  if (!open) return null;

  const handleKeyDown = (e) => {
    if (e.key === "Escape") onClose?.();
  };

  return (
    <div className="modal-backdrop" onClick={onClose} onKeyDown={handleKeyDown} role="presentation">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title">
            {icon}
            {title}
          </div>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Cerrar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="modal-body">
          {children}
          {actions && <div className="modal-actions">{actions}</div>}
        </div>
      </div>
    </div>
  );
}
