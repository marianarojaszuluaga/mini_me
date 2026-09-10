import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import Modal from "../Modal/Modal.jsx";
import "./settings.css";

const THEME_KEY = "ORQ_THEME"; // "light" | "dark" | absent (auto)
const ACCENT_KEY = "ORQ_ACCENT"; // "h,s,l" e.g. "133,50%,32%"

// Valores exactos del mockup acordado (Rediseño Geist v2) — verde oscuro por
// default, SIN rojo (Mariana: "elimina el rojo, deja el amarillo o naranja").
const ACCENT_OPTIONS = [
  { nameKey: "settings.accents.green", hsl: "133,50%,28%" },
  { nameKey: "settings.accents.blue", hsl: "212,100%,48%" },
  { nameKey: "settings.accents.purple", hsl: "272,51%,44%" },
  { nameKey: "settings.accents.orange", hsl: "35,100%,45%" }
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
  const { t } = useTranslation();
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

  const icon = (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
    </svg>
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("settings.title")}
      icon={icon}
      actions={
        <>
          <button type="button" className="btn-cancel" onClick={onClose}>
            {t("settings.cancel")}
          </button>
          <button type="button" className="btn-accent" onClick={handleSave}>
            {t("settings.save")}
          </button>
        </>
      }
    >
      <div className="settings-field">
        <label className="settings-field-label">{t("settings.themeLabel")}</label>
        <div className="settings-theme-toggle">
          {[
            { value: "auto", labelKey: "settings.themeOptions.auto" },
            { value: "light", labelKey: "settings.themeOptions.light" },
            { value: "dark", labelKey: "settings.themeOptions.dark" }
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={theme === opt.value ? "active" : ""}
              onClick={() => previewTheme(opt.value)}
            >
              {t(opt.labelKey)}
            </button>
          ))}
        </div>
      </div>

      <div className="settings-field">
        <label className="settings-field-label">{t("settings.accentLabel")}</label>
        <div className="settings-accent-swatches">
          {ACCENT_OPTIONS.map((opt) => (
            <button
              key={opt.hsl}
              type="button"
              className={`settings-accent-swatch ${accent === opt.hsl ? "active" : ""}`}
              style={{ background: `hsl(${opt.hsl})` }}
              title={t(opt.nameKey)}
              onClick={() => previewAccent(opt.hsl)}
            />
          ))}
        </div>
        <div className="settings-field-hint">
          {t("settings.hint")}
        </div>
      </div>
    </Modal>
  );
}
