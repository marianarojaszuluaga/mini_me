// i18n setup — multi-usuario e internacionalización (2026-09-09).
// Locales iniciales: es-ES (default) y en-US. Namespace único "translation"
// por ahora (Sidebar, ProjectsView, AppShell, Landing) — ver
// PLAN-i18n-multiusuario.md §7 para la migración incremental del resto.
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import es from "./locales/es.json";
import en from "./locales/en.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      "es-ES": { translation: es },
      es: { translation: es },
      "en-US": { translation: en },
      en: { translation: en },
    },
    fallbackLng: "es-ES",
    supportedLngs: ["es-ES", "en-US", "es", "en"],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
    },
  });

export default i18n;
