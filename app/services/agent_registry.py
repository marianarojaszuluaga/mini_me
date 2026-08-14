"""
Agent Registry — migrated from src/agents/registry.js. See that file's header
comment for the full rationale (kept here in condensed form); this is a
faithful port, not a redesign.

Agent ids renamed 2026-08-14 (Mariana's request — short first-name ids,
English by default, instead of role-descriptive slugs): the mapping below
is id-only — source .md filenames on disk are unchanged, since those are an
implementation detail, not something callers see.

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

1. PM agents (gaby, santi, dani) — prompts are inline, built from the
   input/context at call time. gime and gabi look like PM agents by name
   but are actually loaded from spec-kit .md files (see SPEC_KIT_FILES) —
   this matches the real registry.js exactly, not the task's naive
   assumption that all 5 "PM" names are inline.

2. Spec-kit agents — prompts are loaded VERBATIM from
   SPEC_KIT_AGENTS_DIR/*.md at request time. Never paraphrased.

3. External agents (mila, diana, cami) — same verbatim-load mechanism,
   from EXTERNAL_AGENTS_DIR.

MODEL SELECTION: every agent has a declared model tier + max_tokens in
AGENT_MODEL_CONFIG, instead of one hardcoded model for every call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.core.config import get_settings

# canon agent_id -> source .md filename (per ia-hybrid-teams/spec-kit/AGENT_REGISTRY.md,
# corrected where the registry doc itself is wrong — see registry.js header).
# Filenames on disk keep their original (role-descriptive) names — only the
# id callers use was renamed.
SPEC_KIT_FILES: dict[str, str] = {
    "sofi": "architect.md",
    "mafe": "fullstack-developer.md",
    "isa": "flutter-developer.md",
    "fer": "data-engineer.md",
    "vale": "auditor.md",
    "lore": "fixed-errors.md",
    "gime": "Gimena-userstorywriter.md",
    "gabi": "Gabi-workplanner.md",
    # NOTE: AGENT_REGISTRY.md references "gimena-scheduler.md" but the actual
    # file in agents/ is "Gina-scheduler.md" — pre-existing inconsistency in
    # ia-hybrid-teams itself, not introduced here. Pointing at the real file.
    "gina": "Gina-scheduler.md",
    "moni": "qa-integrator.md",
    "rena": "integration.md",
    "sara": "sonar-quality-gate.md",
    "tami": "mcp-integration-tester.md",
    "vane": "test-video-recorder.md",
    "xime": "unit-test-standards-reviewer.md",
    "pau": "quality-report-generator.md",
}

EXTERNAL_AGENT_FILES: dict[str, str] = {
    "mila": "milestone-writer.md",
    "diana": "dod-definer.md",
    "cami": "capacity-reconciler.md",
}


def _gabriela_prompt(input_: str, context: dict | None) -> str:
    return f"""Eres GABRIELA, guardiana del Project Brain.

Tu responsabilidad es mantener el Project Brain del proyecto siguiendo EXACTAMENTE
la estructura del template canónico (ia-hybrid-teams/agents/Gabriela-ProjectBrain.md,
V2.0.0), no una estructura libre:

1. Strategic Definition & Governance (Executive Summary, Stakeholders and Approvers)
2. Scope Management (Scope Matrix In/Out por módulo)
3. Timeline & Milestones (Start/End Date, Delivery Roadmap con status)
4. Dynamic Knowledge & Meeting Logs (Master Meeting Doc, Change Log / Decision Log)
5. Functional Requirements (Key Characteristics, Critical Business Rules)

IMPORTANTE:
1. Archivo: project_brain_[project_name].md
2. Ante cualquier discrepancia entre este documento y el Decision Log, gana el Decision Log
3. Los agentes gime/gabi consultan este documento ANTES de cualquier decisión
4. Responde SOLO en JSON

CONTEXTO: {json.dumps(context or {}, ensure_ascii=False)}
INPUT: {input_}

Proporciona resumen del Project Brain siguiendo esa estructura de 5 secciones."""


def _santi_prompt(input_: str, context: dict | None) -> str:
    return f"""Eres SANTI, especialista en documentación de reuniones técnicas.
Tu trabajo es transformar transcripciones en actas profesionales:
- Estructura: Notas (H2/H3) + Action Items ☐ + Alertas + RedFlags
- Formato: H1 (Título), H2 (Secciones), H3 (Numeradas en subsecciones)
- Accionables con ☐ [Tarea] [[Owner] DUE: [Fecha]]
- Output: Acta profesional lista para Google Docs

IMPORTANTE:
1. Lenguaje directo y técnico
2. Prohibido 'X mencionó que'
3. Marca ambigüedades con [POR CONFIRMAR]
4. Responde SOLO en JSON

CONTEXTO: {json.dumps(context or {}, ensure_ascii=False)}
INPUT: {input_}

Genera acta de reunión profesional."""


def _daniel_prompt(input_: str, context: dict | None) -> str:
    return f"""Eres DANIEL, especialista en Release Notes.
Tu trabajo es generar dos versiones:
1. Bitbucket (Técnico): commits, package versions, contributors
2. Basecamp (Client-friendly): sin términos técnicos

IMPORTANTE:
1. Bitbucket: Incluir todos los commits funcionales
2. Basecamp: Máximo 2-4 oraciones por item, lenguaje plano
3. Responde SOLO en JSON

CONTEXTO: {json.dumps(context or {}, ensure_ascii=False)}
INPUT: {input_}

Genera ambas versiones de release notes."""


PM_AGENT_PROMPTS: dict[str, Callable[[str, dict | None], str]] = {
    "gaby": _gabriela_prompt,
    "santi": _santi_prompt,
    "dani": _daniel_prompt,
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
    "pau": ModelTierConfig("haiku", 1500),
    "mila": ModelTierConfig("sonnet", 2500),
    "diana": ModelTierConfig("sonnet", 2500),
    "cami": ModelTierConfig("sonnet", 2500),
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


@dataclass(frozen=True)
class BuiltPrompt:
    system: str | None
    user: str


def build_prompt(agent_id: str, input_: str, context: dict | None = None) -> BuiltPrompt | None:
    """Returns the system prompt + human message for a given agent invocation.
    Returns None if the agent is unknown."""
    if agent_id in PM_AGENT_PROMPTS:
        return BuiltPrompt(system=None, user=PM_AGENT_PROMPTS[agent_id](input_, context))

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
        [{"id": agent_id, "family": "pm"} for agent_id in PM_AGENT_PROMPTS]
        + [{"id": agent_id, "family": "spec-kit"} for agent_id in SPEC_KIT_FILES]
        + [{"id": agent_id, "family": "external"} for agent_id in EXTERNAL_AGENT_FILES]
    )


def is_known_agent(agent_id: str) -> bool:
    return agent_id in PM_AGENT_PROMPTS or agent_id in SPEC_KIT_FILES or agent_id in EXTERNAL_AGENT_FILES


def get_agent_prompt(agent_id: str, input_: str = "", context: dict | None = None) -> BuiltPrompt | None:
    """Convenience alias matching the task spec's requested public surface
    (list_agents / get_agent_prompt / is_known_agent) — delegates to
    build_prompt, the name that mirrors registry.js's buildPrompt."""
    return build_prompt(agent_id, input_, context)
