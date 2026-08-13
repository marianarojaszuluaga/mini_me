"""
Application settings, read from environment variables via pydantic-settings.

Mirrors the env vars already documented in .env.example (Node era) — no new
variables invented here. See .env.example.python for the annotated copy.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Anthropic API key (required, server-side only). Mariana routes this
    # through her own LiteLLM proxy (https://admin-llm.imagineapps.co/) rather
    # than calling api.anthropic.com directly — ANTHROPIC_BASE_URL below
    # redirects the SDK there. Both must be set together for the proxy path;
    # leaving ANTHROPIC_BASE_URL unset falls back to Anthropic's real API.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str | None = None

    # DeepSeek, routed through the SAME LiteLLM proxy (ANTHROPIC_BASE_URL) but
    # with its OWN virtual key — Mariana's LiteLLM keys are each restricted to
    # one model (confirmed 2026-08-13/14 by the proxy's own error messages),
    # so this can't share ANTHROPIC_API_KEY. Used for the "haiku" (cheap) tier
    # in app/services/agent_registry.py's MODEL_IDS. Verified live 2026-08-14
    # against https://admin-llm.imagineapps.co with model "deepseek-chat".
    DEEPSEEK_API_KEY: str | None = None

    # Comma-separated allowlist of API keys this service accepts from its own
    # clients (dashboard, CLI, CI, Apps Script). Parsed into a list by
    # `allowed_api_keys` below — kept as a raw string here so pydantic-settings
    # doesn't try to parse it as JSON (its default behavior for list-typed
    # fields read from env vars).
    APP_API_KEYS: str = ""

    # MAP server port.
    PORT: int = 3001

    # Master Orchestrator port.
    ORCHESTRATOR_PORT: int = 3000

    # Environment mode. NODE_ENV kept for drop-in compatibility with the
    # existing .env; ENVIRONMENT is the Python-idiomatic alias (SPEC_JARVIS
    # mentions both names) — whichever is set wins, NODE_ENV takes priority
    # since it's what current deployments already set.
    NODE_ENV: str = "development"
    ENVIRONMENT: str | None = None

    # Where projects.json / activity-log.json / workflows.json are written.
    # Only used when Redis is NOT configured.
    STORAGE_DIR: str = str(REPO_ROOT / "storage")

    # Vercel deploy only: Redis (Upstash) credentials for persistent storage
    # across serverless invocations. Vercel's Redis Marketplace integration
    # namespaces these with a store-specific prefix (see core/storage.py's
    # suffix-matching, ported from store.js) — these two are the unprefixed
    # fallback names.
    UPSTASH_REDIS_REST_URL: str | None = None
    UPSTASH_REDIS_REST_TOKEN: str | None = None

    # Master Orchestrator only: public URL of the deployed MAP service.
    MAP_URL: str | None = None

    # Path to the ia-hybrid-teams agents/ folder, if overriding the bundled
    # copy at src/agents/spec-kit-agents/.
    SPEC_KIT_AGENTS_DIR: str | None = None

    # External agents folder (milestone-writer, dod-definer, capacity-reconciler).
    EXTERNAL_AGENTS_DIR: str | None = None

    # Frontend URL (for CORS, if restricting origins later — CORS is wide
    # open today, matching the Express app's bare `cors()`).
    FRONTEND_URL: str = "http://localhost:5173"

    # Real OAuth Auth Profiles (SPEC_JARVIS.md §11, resolved 2026-08-14):
    # each provider needs an OAuth App registered by Mariana (GitHub OAuth
    # App, Bitbucket OAuth consumer, Google OAuth 2.0 client) with its
    # callback pointed at {BACKEND_PUBLIC_URL}/auth-profiles/oauth/{provider}/callback.
    # Left unset by default — app/routers/oauth.py returns a clear 501 per
    # provider until its pair is configured, same "real key when she has it"
    # pattern as DEEPSEEK_API_KEY.
    GITHUB_OAUTH_CLIENT_ID: str | None = None
    GITHUB_OAUTH_CLIENT_SECRET: str | None = None
    BITBUCKET_OAUTH_CLIENT_ID: str | None = None
    BITBUCKET_OAUTH_CLIENT_SECRET: str | None = None
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    # Public URL of THIS backend (not the frontend) — used to build the
    # OAuth callback redirect_uri sent to each provider. Defaults to local
    # dev; must be the real deployed backend URL in production.
    BACKEND_PUBLIC_URL: str = "http://localhost:3001"

    @property
    def environment(self) -> str:
        """Resolved environment name: ENVIRONMENT if set, else NODE_ENV."""
        return self.ENVIRONMENT or self.NODE_ENV

    @property
    def anthropic_client_kwargs(self) -> dict:
        """kwargs for AsyncAnthropic(**this) — every call site should build its
        client through this instead of passing api_key= directly, so the
        LiteLLM proxy redirect (ANTHROPIC_BASE_URL) applies everywhere at once."""
        kwargs: dict = {"api_key": self.ANTHROPIC_API_KEY}
        if self.ANTHROPIC_BASE_URL:
            kwargs["base_url"] = self.ANTHROPIC_BASE_URL
        return kwargs

    def api_key_for_model(self, model: str) -> str:
        """Which virtual key to use for a given model — each of Mariana's
        LiteLLM keys only authorizes one specific model (see
        anthropic_client_kwargs' docstring history / SPEC_JARVIS.md §11).
        Callers that vary model per-agent (app/routers/agents.py's
        invoke_agent_core, via agent_registry.get_model_config) should send
        this as the `x-api-key` header per-request instead of assuming the
        client's default key covers every model."""
        if model == "deepseek-chat" and self.DEEPSEEK_API_KEY:
            return self.DEEPSEEK_API_KEY
        return self.ANTHROPIC_API_KEY

    @property
    def allowed_api_keys(self) -> list[str]:
        return [k.strip() for k in self.APP_API_KEYS.split(",") if k.strip()]

    @property
    def spec_kit_agents_dir(self) -> Path:
        if self.SPEC_KIT_AGENTS_DIR:
            return Path(self.SPEC_KIT_AGENTS_DIR)
        return REPO_ROOT / "src" / "agents" / "spec-kit-agents"

    @property
    def external_agents_dir(self) -> Path:
        if self.EXTERNAL_AGENTS_DIR:
            return Path(self.EXTERNAL_AGENTS_DIR)
        return REPO_ROOT / "src" / "agents" / "external-agents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
