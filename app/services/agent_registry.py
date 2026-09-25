"""
Agent Registry — migrated from src/agents/registry.js. See that file's header
comment for the full rationale (kept here in condensed form); this is a
faithful port, not a redesign.

Agent ids renamed 2026-08-14 (Mariana's request — short first-name ids,
English by default, instead of role-descriptive slugs).

Source .md filenames renamed 2026-09-17 to the `id_función.md` scheme (e.g.
`sofi_architect.md`) so the id and the file agree at a glance — see
`qa/test-design/agentes-mini-me-input-output-handoff.xlsx` for the full
roster (input/output/handoff per agent) this rename was done alongside.

    gimena -> gime          santi -> santi (unchanged)
    gabi -> gabi (unchanged) daniel -> dani
    gabriela -> gaby        architect -> sofi
    fullstack-developer -> mafe   flutter-developer -> isa
    data-engineer -> fer    auditor -> vale
    fixed-errors -> lore    gina-scheduler -> gina
    qa-integrator -> moni   integration -> rena
    sonar-quality-gate -> sara     mcp-integration-tester -> tami
    test-video-recorder -> vane    unit-test-standards-reviewer -> xime
    quality-report-generator -> pau        milestone-writer -> mila
    dod-definer -> diana    capacity-reconciler -> cami

Two agent families, one lookup table:

1. Spec-kit agents — prompts are loaded VERBATIM from
   SPEC_KIT_AGENTS_DIR/*.md at request time. Never paraphrased. This
   includes gaby/santi/dani (migrated 2026-09-17 from inline Python
   prompts to .md files, for consistency with the other 19 agents —
   version + changelog now live with the prompt, not buried in code).

2. External agents (mila, diana, cami) — same verbatim-load mechanism,
   from EXTERNAL_AGENTS_DIR.

There is no more "PM inline" family — PM_AGENT_PROMPTS is gone. All 22
agents load their prompt from a .md file.

MODEL SELECTION: every agent has a declared model tier + max_tokens in
AGENT_MODEL_CONFIG, instead of one hardcoded model for every call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from app.core.config import get_settings

# canon agent_id -> source .md filename (per ia-hybrid-teams/spec-kit/AGENT_REGISTRY.md,
# corrected where the registry doc itself is wrong — see registry.js header).
# Filenames on disk keep their original (role-descriptive) names — only the
# id callers use was renamed.
SPEC_KIT_FILES: dict[str, str] = {
    "sofi": "sofi_architect.md",
    "mafe": "mafe_fullstackdeveloper.md",
    "isa": "isa_flutterdeveloper.md",
    "fer": "fer_dataengineer.md",
    "vale": "vale_auditor.md",
    "lore": "lore_fixederrors.md",
    "gime": "gime_userstorywriter.md",
    "gabi": "gabi_workplanner.md",
    "gina": "gina_scheduler.md",
    "moni": "moni_qaintegrator.md",
    "rena": "rena_integration.md",
    "sara": "sara_sonarqualitygate.md",
    "tami": "tami_mcpintegrationtester.md",
    "vane": "vane_testvideorecorder.md",
    "xime": "xime_unittestreviewer.md",
    "pau": "pau_qualityreportgenerator.md",
}

EXTERNAL_AGENT_FILES: dict[str, str] = {
    "mila": "mila_milestonewriter.md",
    "diana": "diana_doddefiner.md",
    "cami": "cami_capacityreconciler.md",
}

# PM agents (gaby, santi, dani) — Mini me's own agents, NOT part of the
# ia-hybrid-teams spec-kit sync (see README's "Sincronía con
# ia-hybrid-teams/agents/" — that folder is a verbatim copy of an external
# repo). Kept in their own dir/dict so a future spec-kit sync never touches
# or gets confused with these. Migrated 2026-09-17 from inline Python
# prompts (see git history) to .md files for version/changelog parity with
# every other agent.
PM_AGENT_FILES: dict[str, str] = {
    "gaby": "gaby_projectbrain.md",
    "santi": "santi_actas.md",
    "dani": "dani_releasenotes.md",
    # Added 2026-09-17: close the gap where no agent designed test cases in
    # parallel with development, or consolidated manual test results. See
    # qa/test-design/agentes-mini-me-input-output-handoff.xlsx.
    "cata": "cata_testdesigner.md",
    "leo": "leo_testconsolidator.md",
    "mia": "mia_meetingmessenger.md",
    "nico": "nico_docsync.md",
}


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

MODEL_IDS: dict[str, str] = {
    # "haiku" tier -> DeepSeek (cheap), via a separate LiteLLM virtual key
    # (Mariana's Sonnet key is restricted to claude-sonnet-4-6 only, and the
    # deepseek-chat key is restricted to that model only — see
    # app.core.config.Settings.model_api_key_for). Reconnected 2026-08-14
    # after being collapsed to a single model for lack of a working
    # DeepSeek key.
    "haiku": "deepseek-chat",
    "sonnet": "claude-sonnet-4-6",
}


@dataclass(frozen=True)
class ModelTierConfig:
    tier: str
    max_tokens: int


DEFAULT_MODEL_CONFIG = ModelTierConfig(tier="sonnet", max_tokens=2000)

AGENT_MODEL_CONFIG: dict[str, ModelTierConfig] = {
    "gime": ModelTierConfig("sonnet", 4000),
    "gabi": ModelTierConfig("sonnet", 4000),
    "gaby": ModelTierConfig("sonnet", 3000),
    "santi": ModelTierConfig("sonnet", 2500),
    "dani": ModelTierConfig("sonnet", 3000),
    "sofi": ModelTierConfig("sonnet", 3000),
    "mafe": ModelTierConfig("sonnet", 3000),
    "isa": ModelTierConfig("sonnet", 3000),
    "fer": ModelTierConfig("sonnet", 3000),
    "vale": ModelTierConfig("sonnet", 3000),
    "lore": ModelTierConfig("sonnet", 2500),
    "gina": ModelTierConfig("sonnet", 2500),
    "moni": ModelTierConfig("sonnet", 2500),
    "rena": ModelTierConfig("sonnet", 2500),
    "sara": ModelTierConfig("sonnet", 2000),
    "tami": ModelTierConfig("sonnet", 2000),
    "vane": ModelTierConfig("haiku", 1000),
    "xime": ModelTierConfig("sonnet", 2000),
    # 2026-08-24: 1500 truncaba el reporte real a mitad del bloque ```json de
    # findings (Capa 2 del qa-sweep) — el parser silenciosamente veía 0
    # findings porque el fence nunca cerraba. Subido para que el reporte +
    # el JSON de findings quepan completos.
    "pau": ModelTierConfig("haiku", 3500),
    "mila": ModelTierConfig("sonnet", 2500),
    "diana": ModelTierConfig("sonnet", 2500),
    "cami": ModelTierConfig("sonnet", 2500),
    "cata": ModelTierConfig("sonnet", 3000),
    "leo": ModelTierConfig("sonnet", 2000),
    "mia": ModelTierConfig("haiku", 1500),
    "nico": ModelTierConfig("haiku", 2000),
}


class AgentNotConfiguredError(RuntimeError):
    """Raised when a registered agent's source .md file is missing on disk."""


def get_model_config(agent_id: str) -> dict[str, object]:
    config = AGENT_MODEL_CONFIG.get(agent_id, DEFAULT_MODEL_CONFIG)
    return {
        "model": MODEL_IDS[config.tier],
        "max_tokens": config.max_tokens,
        "tier": config.tier,
    }


def _load_prompt_file(directory: Path, filename: str, agent_id: str, env_hint: str) -> str:
    file_path = directory / filename
    if not file_path.exists():
        raise AgentNotConfiguredError(
            f'Agent "{agent_id}" registered but source file missing: {file_path}. '
            f"Set {env_hint} to the correct folder."
        )
    return file_path.read_text(encoding="utf-8")


def _load_spec_kit_prompt(agent_id: str) -> str | None:
    filename = SPEC_KIT_FILES.get(agent_id)
    if not filename:
        return None
    settings = get_settings()
    return _load_prompt_file(settings.spec_kit_agents_dir, filename, agent_id, "SPEC_KIT_AGENTS_DIR")


def _load_external_prompt(agent_id: str) -> str | None:
    filename = EXTERNAL_AGENT_FILES.get(agent_id)
    if not filename:
        return None
    settings = get_settings()
    return _load_prompt_file(settings.external_agents_dir, filename, agent_id, "EXTERNAL_AGENTS_DIR")


def _load_pm_prompt(agent_id: str) -> str | None:
    filename = PM_AGENT_FILES.get(agent_id)
    if not filename:
        return None
    settings = get_settings()
    return _load_prompt_file(settings.pm_agents_dir, filename, agent_id, "PM_AGENTS_DIR")


@dataclass(frozen=True)
class BuiltPrompt:
    system: str | None
    user: str


def build_prompt(agent_id: str, input_: str, context: dict | None = None) -> BuiltPrompt | None:
    """Returns the system prompt + human message for a given agent invocation.
    Returns None if the agent is unknown."""
    if agent_id in SPEC_KIT_FILES:
        system_prompt = _load_spec_kit_prompt(agent_id)
        return BuiltPrompt(
            system=system_prompt,
            user=(
                f"CONTEXTO: {json.dumps(context or {}, ensure_ascii=False)}\n"
                f"INPUT: {input_}\n\n"
                "Responde siguiendo estrictamente tu rol, comportamiento y restricciones definidos arriba."
            ),
        )

    if agent_id in EXTERNAL_AGENT_FILES:
        system_prompt = _load_external_prompt(agent_id)
        return BuiltPrompt(
            system=system_prompt,
            user=(
                f"CONTEXT: {json.dumps(context or {}, ensure_ascii=False)}\n"
                f"INPUT: {input_}\n\n"
                "Follow your role and rules exactly as defined above."
            ),
        )

    if agent_id in PM_AGENT_FILES:
        system_prompt = _load_pm_prompt(agent_id)
        return BuiltPrompt(
            system=system_prompt,
            user=(
                f"CONTEXTO: {json.dumps(context or {}, ensure_ascii=False)}\n"
                f"INPUT: {input_}\n\n"
                "Responde siguiendo estrictamente tu rol, comportamiento y restricciones definidos arriba."
            ),
        )

    return None


def build_acta_ingest_prompt(acta_content: str, metadata: dict | None = None) -> str:
    """Gabriela's acta-ingestion prompt: extract decisions -> Decision Log and
    risks/blockers -> Alerts. Strict JSON, no invented content."""
    return f"""Eres GABRIELA, guardiana del Project Brain.

Acaba de generarse un acta de reunión. Tu tarea es analizarla y extraer, en JSON estricto:

1. "decisions": decisiones o acuerdos tomados en la reunión, para el Decision Log del proyecto.
   Cada una: {{ "decision": "...", "context": "..." }}
2. "alerts": riesgos, bloqueos o temas que requieren atención del equipo.
   Cada una: {{ "alert": "...", "severity": "LOW|MEDIUM|HIGH" }}

Si no hay decisiones o alertas claras en el acta, devuelve arrays vacíos. No inventes
contenido que no esté explícito o claramente implícito en el acta.

METADATA:
{json.dumps(metadata or {}, indent=2, ensure_ascii=False)}

CONTENIDO DEL ACTA:
{acta_content}

Responde SOLO con este JSON, sin texto adicional:
{{
  "decisions": [{{ "decision": "...", "context": "..." }}],
  "alerts": [{{ "alert": "...", "severity": "LOW|MEDIUM|HIGH" }}]
}}"""


def list_agents() -> list[dict[str, str]]:
    return (
        [{"id": agent_id, "family": "spec-kit"} for agent_id in SPEC_KIT_FILES]
        + [{"id": agent_id, "family": "external"} for agent_id in EXTERNAL_AGENT_FILES]
        + [{"id": agent_id, "family": "pm"} for agent_id in PM_AGENT_FILES]
    )


def is_known_agent(agent_id: str) -> bool:
    return agent_id in SPEC_KIT_FILES or agent_id in EXTERNAL_AGENT_FILES or agent_id in PM_AGENT_FILES


def get_agent_prompt(agent_id: str, input_: str = "", context: dict | None = None) -> BuiltPrompt | None:
    """Convenience alias matching the task spec's requested public surface
    (list_agents / get_agent_prompt / is_known_agent) — delegates to
    build_prompt, the name that mirrors registry.js's buildPrompt."""
    return build_prompt(agent_id, input_, context)
