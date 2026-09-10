import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { BrandIcon, AlertIcon, IntegrationsIcon, AgentsIcon, ChatIcon, QaIcon } from "../components/icons.jsx";
import "./landing.css";

const FEATURE_ICONS = {
  integrations: IntegrationsIcon,
  agents: AgentsIcon,
  chat: ChatIcon,
  qa: QaIcon,
};

const LANG_FLAGS = { es: "🇪🇸", en: "🇺🇸" };

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

  async function submitCredentials(e) {
    e.preventDefault();
    setError("");
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

      <section className="landing-features">
        <h2>{t("landing.featuresTitle")}</h2>
        <div className="landing-features-grid">
          {["integrations", "agents", "chat", "qa"].map((key) => (
            <div className="landing-feature-card" key={key}>
              <div className="landing-feature-icon">{FEATURE_ICONS[key]}</div>
              <h3>{t(`landing.features.${key}.title`)}</h3>
              <p>{t(`landing.features.${key}.body`)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="landing-access">
        <div className="landing-access-card">
          <h2>{mode === "login" ? t("landing.loginTitle") : t("landing.registerTitle")}</h2>
          <form onSubmit={submitCredentials}>
            {mode === "register" && (
              <input
                type="text"
                placeholder={t("landing.name")}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
            <input
              type="email"
              placeholder={t("landing.email")}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <input
              type="password"
              placeholder={t("landing.password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
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
