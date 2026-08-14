import React, { useState } from "react";
import "./settings.css";

const THEME_KEY = "ORQ_THEME"; // "light" | "dark" | absent (auto)
const ACCENT_KEY = "ORQ_ACCENT"; // "h,s,l" e.g. "133,50%,32%"

// Real Geist HSL triples (design-tokens.css) — verde oscuro por default,
// SIN rojo (Mariana: "elimina el rojo, deja el amarillo o naranja").
const ACCENT_OPTIONS = [
  { name: "Verde (default)", hsl: "133,50%,32%" },
  { name: "Azul", hsl: "212,100%,41%" },
  { name: "Púrpura", hsl: "272,47%,45%" },
  { name: "Naranja", hsl: "35,100%,45%" }
];

export function applyStoredAppearance() {
  const theme = localStorage.getItem(THEME_KEY);
  if (theme === "light") document.documentElement.classList.add("light-theme");
  else if (theme === "dark") document.documentElement.classList.add("dark-theme");

  const accent = localStorage.getItem(ACCENT_KEY);
  if (accent) {
    const [h, s, l] = accent.split(",");
    document.documentElement.style.setProperty("--accent-h", h);
    document.documentElement.style.setProperty("--accent-s", s);
    document.documentElement.style.setProperty("--accent-l", l);
  }
}

export default function SettingsModal({ open, onClose }) {
  const [theme, setTheme] = useState(localStorage.getItem(THEME_KEY) || "auto");
  const [accent, setAccent] = useState(localStorage.getItem(ACCENT_KEY) || ACCENT_OPTIONS[0].hsl);

  if (!open) return null;

  const previewTheme = (value) => {
    setTheme(value);
    document.documentElement.classList.remove("light-theme", "dark-theme");
    if (value === "light") document.documentElement.classList.add("light-theme");
    if (value === "dark") document.documentElement.classList.add("dark-theme");
  };

  const previewAccent = (hsl) => {
    setAccent(hsl);
    const [h, s, l] = hsl.split(",");
    document.documentElement.style.setProperty("--accent-h", h);
    document.documentElement.style.setProperty("--accent-s", s);
    document.documentElement.style.setProperty("--accent-l", l);
  };

  const handleSave = () => {
    if (theme === "auto") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, theme);
    localStorage.setItem(ACCENT_KEY, accent);
    onClose();
  };

  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-modal-header">
          <h2>Configuración</h2>
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cerrar
          </button>
        </div>

        <div className="settings-field">
          <label className="settings-field-label">Tema</label>
          <div className="settings-theme-toggle">
            {[
              { value: "auto", label: "Auto" },
              { value: "light", label: "Claro" },
              { value: "dark", label: "Oscuro" }
            ].map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={theme === opt.value ? "active" : ""}
                onClick={() => previewTheme(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="settings-field">
          <label className="settings-field-label">Color principal</label>
          <div className="settings-accent-swatches">
            {ACCENT_OPTIONS.map((opt) => (
              <button
                key={opt.hsl}
                type="button"
                className={`settings-accent-swatch ${accent === opt.hsl ? "active" : ""}`}
                style={{ background: `hsl(${opt.hsl})` }}
                title={opt.name}
                onClick={() => previewAccent(opt.hsl)}
              />
            ))}
          </div>
          <div className="settings-field-hint">
            Se guarda por usuario — la próxima vez que abras la app, arranca con esta config.
          </div>
        </div>

        <div className="settings-modal-actions">
          <button type="button" className="btn-cancel" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" className="btn-accent" onClick={handleSave}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
}
