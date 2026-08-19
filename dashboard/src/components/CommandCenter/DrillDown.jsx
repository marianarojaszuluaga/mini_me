import React from "react";
import "./command-center.css";

/**
 * DrillDown — generic overlay/modal mechanism used for "Detalle de Proyecto",
 * "Analitica completa", "Memoria de Mar", "Integraciones", etc.
 *
 * This component owns ONLY the open/close mechanism (backdrop + fixed
 * container + z-index from design-tokens.css). Content is entirely up to
 * the caller via `children`.
 *
 * Props:
 *  - open: boolean — whether the drill-down is visible
 *  - onClose: () => void — called when the backdrop or Escape is pressed
 *  - children: ReactNode — the drill-down's own content
 *  - label?: string — aria-label for the dialog (default "Detalle")
 *
 * Usage:
 *   <DrillDown open={open} onClose={() => setOpen(false)} label="Detalle de Proyecto">
 *     <ProjectDetailContent .../>
 *   </DrillDown>
 */
export default function DrillDown({ open, onClose, children, label = "Detalle" }) {
  if (!open) return null;

  const handleKeyDown = (e) => {
    if (e.key === "Escape") onClose?.();
  };

  return (
    <div
      className="drilldown-backdrop"
      onClick={onClose}
      onKeyDown={handleKeyDown}
      role="presentation"
    >
      <div
        className="drilldown-content"
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
