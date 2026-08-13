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

    # Anthropic API key (required, server-side only).
    ANTHROPIC_API_KEY: str = ""

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

    @property
    def environment(self) -> str:
        """Resolved environment name: ENVIRONMENT if set, else NODE_ENV."""
        return self.ENVIRONMENT or self.NODE_ENV

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
