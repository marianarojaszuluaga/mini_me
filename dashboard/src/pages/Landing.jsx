import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { BrandIcon, AlertIcon, IntegrationsIcon, AgentsIcon, ChatIcon, QaIcon, FolderIcon } from "../components/icons.jsx";
import "./landing.css";

const FEATURE_ICONS = {
  integrations: IntegrationsIcon,
  agents: AgentsIcon,
  chat: ChatIcon,
  qa: QaIcon,
};

const LANG_FLAGS = { es: "🇪🇸", en: "🇺🇸" };

/**
 * Reveal-on-scroll (2026-09-11, auditoría de usabilidad): fade-in + slide
 * sutil para las feature cards cuando entran en viewport. Motion mínimo pero
 * real — un solo IntersectionObserver, sin scroll-jacking. `prefers-reduced-
 * motion` se respeta en CSS (ver landing.css), no acá: el observer sigue
 * agregando la clase, pero la media query anula la transición.
 */
function useRevealOnScroll(count) {
  const refs = useRef([]);
  const [revealed, setRevealed] = useState(() => new Array(count).fill(false));
  refs.current = [];

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const idx = Number(entry.target.dataset.revealIndex);
          setRevealed((prev) => {
            if (prev[idx]) return prev;
            const next = [...prev];
            next[idx] = true;
            return next;
          });
          observer.unobserve(entry.target);
        });
      },
      { threshold: 0.2 }
    );
    refs.current.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const registerRef = (index) => (el) => {
    refs.current[index] = el;
  };

  return { registerRef, revealed };
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:3001";
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID || "";
const GSI_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

function loadGsiScript() {
  if (document.getElementById("gsi-client-script")) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.id = "gsi-client-script";
    script.src = GSI_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("No se pudo cargar Google Identity Services"));
    document.head.appendChild(script);
  });
}

/**
 * Landing page — Mini me (multi-usuario, 2026-09-09). Hero + features +
 * access form (email/password real against /auth/register|/auth/login,
 * "Continuar con Google" against /auth/google). On success calls
 * onAuthenticated(jwt) which the caller (App.jsx) uses to enter the app.
 *
 * NOTE (see PLAN-i18n-multiusuario.md, "Estado real al cierre de este
 * pase"): only /projects and /repositories are gated to filter by the
 * logged-in user today — other routers (agents, jarvis chat, mar memory,
 * metrics, changelog) still require the shared APP_API_KEYS token. The
 * "App API Key" fallback below stays available so existing access to the
 * full app isn't broken by this pass.
 */
export default function Landing({ onAuthenticated, onUseAppKey, externalError }) {
  const { t, i18n } = useTranslation();
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [appKey, setAppKey] = useState("");
  const [googleReady, setGoogleReady] = useState(false);
  const googleBtnRef = useRef(null);
  const { registerRef, revealed } = useRevealOnScroll(4);

  const currentLang = i18n.resolvedLanguage?.startsWith("en") ? "en" : "es";

  async function handleGoogleCredential(response) {
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/google`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: response.credential }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "No se pudo autenticar con Google");
      onAuthenticated(data.access_token, data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return; // sin client id configurado, se mantiene el botón deshabilitado
    let cancelled = false;
    loadGsiScript()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: handleGoogleCredential,
        });
        if (googleBtnRef.current) {
          window.google.accounts.id.renderButton(googleBtnRef.current, {
            theme: "outline",
            size: "large",
            width: 320,
            locale: currentLang,
          });
        }
        setGoogleReady(true);
      })
      .catch((err) => setError(err.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLang]);

  // Validación propia (2026-09-10): los <input required/type="email"> disparaban
  // el tooltip nativo del navegador (icono naranja, fuente/colores del OS) al
  // enviar el form — no sigue el diseño de la app. Con noValidate en el <form>
  // el navegador ya no lo muestra, y este chequeo cae en el mismo bloque de
  // error (.flag + AlertIcon) que ya se usaba para errores del backend.
  function validateCredentials() {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return t("landing.errors.invalidEmail");
    }
    if (password.length < 8) {
      return t("landing.errors.passwordTooShort");
    }
    if (mode === "register" && !name.trim()) {
      return t("landing.errors.nameRequired");
    }
    return "";
  }

  async function submitCredentials(e) {
    e.preventDefault();
    setError("");
    const validationError = validateCredentials();
    if (validationError) {
      setError(validationError);
      return;
    }
    setLoading(true);
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const body = mode === "login" ? { email, password } : { email, password, name };
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "No se pudo autenticar");
      onAuthenticated(data.access_token, data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleAppKeySubmit(e) {
    e.preventDefault();
    onUseAppKey(appKey);
  }

  return (
    <div className="landing">
      <div className="landing-lang">
        {["es", "en"].map((lng) => (
          <button
            key={lng}
            className={`landing-lang-option ${currentLang === lng ? "active" : ""}`}
            onClick={() => i18n.changeLanguage(lng)}
            type="button"
            aria-label={lng.toUpperCase()}
          >
            <span aria-hidden="true">{LANG_FLAGS[lng]}</span> {lng.toUpperCase()}
          </button>
        ))}
      </div>

      <section className="landing-hero">
        <div className="landing-hero-mark">{BrandIcon}</div>
        <h1>{t("landing.brand")}</h1>
        <p className="landing-tagline">{t("landing.tagline")}</p>
      </section>

      {/* Mockup del producto real (2026-09-11, auditoría): recreación fiel en
          HTML/CSS del AppShell real dentro de un device frame — no una
          captura de pantalla real, pero tampoco un bloque gris genérico. */}
      <section className="landing-mockup-section">
        <div className="landing-device-frame">
          <div className="landing-device-titlebar">
            <span className="landing-device-dot" />
            <span className="landing-device-dot" />
            <span className="landing-device-dot" />
            <span className="landing-device-url">app.minime.io</span>
          </div>
          <div className="landing-device-body">
            <div className="landing-mock-sidebar">
              <div className="landing-mock-brand">
                <span className="landing-mock-brand-mark">{BrandIcon}</span>
                Mini me
              </div>
              <div className="landing-mock-cta">{ChatIcon} Hablar con Jarvis</div>
              <div className="landing-mock-nav-label">Trabajo</div>
              <div className="landing-mock-nav-item active">{FolderIcon} Proyectos</div>
              <div className="landing-mock-nav-item">{AgentsIcon} Ciclo de vida</div>
              <div className="landing-mock-nav-label">Analítica</div>
              <div className="landing-mock-nav-item">{QaIcon} Dashboard</div>
              <div className="landing-mock-nav-item">{IntegrationsIcon} Integraciones</div>
            </div>
            <div className="landing-mock-main">
              <div className="landing-mock-heading">3 proyectos</div>
              <div className="landing-mock-cards">
                <div className="landing-mock-card">
                  <div className="landing-mock-card-top">
                    <span className="landing-mock-card-name">Rediseño App Móvil</span>
                    <span className="landing-mock-pill landing-mock-pill-ok">En curso</span>
                  </div>
                  <span className="landing-mock-card-sub">Fase 2 · desarrollo</span>
                </div>
                <div className="landing-mock-card">
                  <div className="landing-mock-card-top">
                    <span className="landing-mock-card-name">Backend Facturación</span>
                    <span className="landing-mock-pill landing-mock-pill-warn">Atención</span>
                  </div>
                  <span className="landing-mock-card-sub">Fase 3 · QA</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="landing-features">
        <h2>{t("landing.featuresTitle")}</h2>
        <div className="landing-features-grid">
          {["integrations", "agents", "chat", "qa"].map((key, index) => (
            <div
              className={`landing-feature-card ${revealed[index] ? "is-revealed" : ""}`}
              key={key}
              ref={registerRef(index)}
              data-reveal-index={index}
            >
              <div className="landing-feature-icon">{FEATURE_ICONS[key]}</div>
              <h3>{t(`landing.features.${key}.title`)}</h3>
              <p>{t(`landing.features.${key}.body`)}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Claridad de propósito (2026-09-11): "no se ve muy directo el
          entendimiento de lo que se hace" — 3 pasos, antes del formulario. */}
      <section className="landing-how">
        <h2>{t("landing.how.title")}</h2>
        <div className="landing-how-steps">
          {["connect", "work", "review"].map((key, i) => (
            <div className="landing-how-step" key={key}>
              <span className="landing-how-step-num">{i + 1}</span>
              <h3>{t(`landing.how.steps.${key}.title`)}</h3>
              <p>{t(`landing.how.steps.${key}.body`)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-access">
        <div className="landing-access-card">
          <h2>{mode === "login" ? t("landing.loginTitle") : t("landing.registerTitle")}</h2>
          <form onSubmit={submitCredentials} noValidate>
            {mode === "register" && (
              <input
                type="text"
                placeholder={t("landing.name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
            <input
              type="text"
              placeholder={t("landing.email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              type="password"
              placeholder={t("landing.password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button type="submit" disabled={loading}>
              {mode === "login" ? t("landing.loginButton") : t("landing.registerButton")}
            </button>
          </form>

          {GOOGLE_CLIENT_ID ? (
            <div className="landing-google-btn-container" ref={googleBtnRef} />
          ) : (
            <button className="landing-google-btn" disabled type="button">
              {t("landing.googleNotConfigured")}
            </button>
          )}
          {GOOGLE_CLIENT_ID && !googleReady && (
            <p className="landing-google-loading">{t("landing.googleLoading")}</p>
          )}

          <button
            className="landing-switch-link"
            type="button"
            onClick={() => {
              setError("");
              setMode(mode === "login" ? "register" : "login");
            }}
          >
            {mode === "login" ? t("landing.switchToRegister") : t("landing.switchToLogin")}
          </button>

          {(error || externalError) && (
            <div className="flag">
              {AlertIcon} {error || externalError}
            </div>
          )}

          <details className="landing-appkey">
            <summary>{t("landing.orAppKey")}</summary>
            <form onSubmit={handleAppKeySubmit}>
              <input
                type="password"
                placeholder={t("landing.appKeyPlaceholder")}
                value={appKey}
                onChange={(e) => setAppKey(e.target.value)}
              />
              <button type="submit">{t("landing.loginButton")}</button>
            </form>
          </details>
        </div>
      </section>
    </div>
  );
}
