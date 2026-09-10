"""
GET /agents, GET /phases, GET /phases/{id_or_key}, POST /agents/{name}/invoke,
POST /orchestrate, POST /evaluate — migrated from server.js. All require the
auth dependency (health is the only unauthenticated route, in health.py).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.config import Settings, get_settings
from app.core.security import authenticate_api_key_or_user
from app.core.storage import get_storage
from app.phases import phase_contracts
from app.schemas.qa import Finding, QaSweepReport, Signoff
from app.services import agent_registry
from app.services.agent_evaluator import AgentEvaluator
from app.services.brain.reconciliation import run_reconciliation
from app.services.metrics import collector
from app.services.metrics.evaluate_invocation import evaluate_and_check

router = APIRouter(dependencies=[Depends(authenticate_api_key_or_user)])

# Which agent produces which OutputCount type (SPEC_JARVIS.md §7, resolved
# 2026-08-14 — record_output() previously had zero callers anywhere in the
# system, so the Dashboard's "# de outputs" was always fabricated/empty).
# Agents not listed here (e.g. gaby, gina, lore) don't map to one of the
# tracked output types and simply don't add to any counter — not every
# agent invocation is a countable "output" in this sense.
_AGENT_OUTPUT_TYPE: dict[str, str] = {
    "gime": "hu",
    "gabi": "plan",
    "santi": "acta",
    "vale": "qa_run",
    "sara": "qa_run",
    "xime": "qa_run",
}

# Which agent handles a given (phase, step) — validated against
# phase_contracts so we never invoke an agent that isn't actually assigned to
# that phase.
#
# santi/dani (actas, release notes) are intentionally NOT here: they aren't
# tied to a single phase step, they run continuously across the whole
# lifecycle. Invoke them directly via /agents/{name}/invoke instead.
STEP_TO_AGENT: dict[str, str] = {
    "1:lock_scope": "gime",
    "1:milestones": "mila",
    "1:dod": "diana",
    "1:estimation": "gabi",
    "1:reconciliation": "cami",
    "1:timeline": "gina",
    "1:transversales": "vale",
    "2:data_model": "fer",
    "2:work_plan": "gabi",
    "2:review": "vale",
    "3:frontend_web": "mafe",
    "3:frontend_app": "isa",
    "3:integration": "rena",
    "4:sonar_gate": "sara",
    "4:unit_test_review": "xime",
    "4:quality_report": "pau",
}


def _get_anthropic_client(settings: Settings = Depends(get_settings)) -> AsyncAnthropic:
    return AsyncAnthropic(**settings.anthropic_client_kwargs)


def _get_evaluator(settings: Settings = Depends(get_settings)) -> AgentEvaluator:
    return AgentEvaluator(api_key=settings.ANTHROPIC_API_KEY, base_url=settings.ANTHROPIC_BASE_URL)


async def invoke_agent_core(
    client: AsyncAnthropic,
    name: str,
    project_id: str | None,
    input_: str,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Shared by /agents/{name}/invoke AND /orchestrate — no internal HTTP
    call to itself, same process, one Claude call."""
    if not agent_registry.is_known_agent(name):
        raise HTTPException(status_code=400, detail=f"Unknown agent: {name}")

    prompt = agent_registry.build_prompt(name, input_, context)
    if prompt is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {name}")

    model_config = agent_registry.get_model_config(name)

    kwargs: dict[str, Any] = {
        "model": model_config["model"],
        "max_tokens": model_config["max_tokens"],
        "messages": [{"role": "user", "content": prompt.user}],
    }
    if prompt.system:
        kwargs["system"] = prompt.system

    # 2026-08-14: each of Mariana's LiteLLM virtual keys only authorizes one
    # model (confirmed by the proxy's own 403 error) — the "haiku" tier
    # (deepseek-chat) needs a different key than the client's default
    # ("sonnet" tier, claude-sonnet-4-6). Tried overriding just the
    # `x-api-key` header per-request first (extra_headers) — verified live
    # that this SDK version does NOT let a per-request header win over the
    # client's own auth, so a separate client instance is required instead.
    settings = get_settings()
    model_api_key = settings.api_key_for_model(model_config["model"])
    call_client = client
    if model_api_key != settings.ANTHROPIC_API_KEY:
        call_client = AsyncAnthropic(
            api_key=model_api_key,
            base_url=settings.ANTHROPIC_BASE_URL or None,
        )

    # The Node original wrapped this call in try/catch and returned
    # {"error": message} with the real status code — this must not become an
    # unhandled 500 (regression found 2026-08-13: a fake/invalid API key was
    # crashing the whole request instead of surfacing a clean error).
    try:
        response = await call_client.messages.create(**kwargs)
    except anthropic.APIStatusError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error.message)) from error
    except anthropic.APIError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = {
        "agent": name,
        "projectId": project_id,
        "timestamp": timestamp,
        "output": response.content[0].text,
        "usage": response.usage.model_dump() if hasattr(response.usage, "model_dump") else dict(response.usage),
        "model": model_config["model"],
    }

    storage = get_storage()
    storage.log_activity(
        {
            "timestamp": timestamp,
            "projectId": project_id,
            "agent": name,
            "action": "invoked",
            "status": "completed",
        }
    )

    output_type = _AGENT_OUTPUT_TYPE.get(name)
    if output_type:
        await collector.record_output(output_type, project_id=project_id, agent_name=name)

    await collector.record_usage_event(
        agent_invocation=True,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        project_id=project_id,
    )

    # HU-008-JarvisMode: autoevaluación multidimensional inmediata — corre en
    # cada invocación real, no como paso manual aparte (AC 2.1.2). No debe
    # tumbar la invocación si la evaluación falla (ej. el juez de acertividad
    # tiene un error transitorio de red).
    try:
        result["evaluation"] = await evaluate_and_check(
            name, result["output"], context, input_=input_, client=client, project_id=project_id
        )
    except Exception as error:  # noqa: BLE001 - evaluation is best-effort, never blocks the invoke response
        result["evaluation"] = {"error": f"Evaluation failed: {error}"}

    return result


@router.get("/agents")
async def list_agents() -> list[dict[str, str]]:
    return agent_registry.list_agents()


@router.get("/phases")
async def list_phases() -> list[dict[str, Any]]:
    return phase_contracts.list_phases()


@router.get("/phases/{id_or_key}")
async def get_phase(id_or_key: str) -> dict[str, Any]:
    phase = phase_contracts.get_phase(id_or_key)
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    return phase


@router.post("/agents/{name}/invoke")
async def invoke_agent(
    name: str,
    body: dict[str, Any] = Body(...),
    client: AsyncAnthropic = Depends(_get_anthropic_client),
) -> dict[str, Any]:
    project_id = body.get("projectId")
    input_ = body.get("input", "")
    context = body.get("context")
    return await invoke_agent_core(client, name, project_id, input_, context)


@router.post("/orchestrate")
async def orchestrate(
    body: dict[str, Any] = Body(...),
    client: AsyncAnthropic = Depends(_get_anthropic_client),
) -> dict[str, Any]:
    project_id = body.get("projectId")
    phase = body.get("phase")
    step = body.get("step")

    phase_contract = phase_contracts.get_phase(phase)
    if not phase_contract:
        raise HTTPException(status_code=400, detail=f"Unknown phase: {phase}")

    step_key = f"{phase_contract['id']}:{step}"
    agent_to_invoke = STEP_TO_AGENT.get(step_key)
    if not agent_to_invoke:
        available_steps = [
            key.split(":")[1] for key in STEP_TO_AGENT if key.startswith(f"{phase_contract['id']}:")
        ]
        raise HTTPException(
            status_code=400,
            detail={
                "error": f'No agent mapped for phase "{phase_contract["key"]}" step "{step}"',
                "availableSteps": available_steps,
            },
        )

    if agent_to_invoke not in phase_contract["agents"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": f'Agent "{agent_to_invoke}" is not assigned to phase "{phase_contract["key"]}" per PHASE_CONTRACTS.md',
                "phaseAgents": phase_contract["agents"],
            },
        )

    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    agent_result = await invoke_agent_core(
        client, agent_to_invoke, project_id, step, {"phase": phase_contract["key"], "step": step}
    )

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    project["currentPhase"] = phase_contract["id"]
    project["currentStep"] = step
    project["progress"] = min(project.get("progress", 0) + 15, 95)
    project.setdefault("memory", {}).setdefault("timeline", {}).setdefault("activities", []).append(
        {
            "timestamp": timestamp,
            "agent": agent_to_invoke,
            "action": f"{step} completed",
            "status": "completed",
        }
    )

    storage.write_projects(projects)

    return {
        "projectId": project_id,
        "phase": phase_contract["key"],
        "step": step,
        "agentInvoked": agent_to_invoke,
        "agentResult": agent_result["output"],
        "projectUpdated": project,
    }


# Tarea 3, Capa 2 (2026-08-21) — Fase 4 real: moni valida API, rena evidencia
# de integración UI↔API, sara/xime corren en paralelo (Sonar + unit test
# standards), y solo entonces corre la reconciliación real (Vale). pau
# consolida todo en el reporte go/no-go — nunca inventado, siempre a partir
# de lo que los agentes anteriores + la reconciliación produjeron de verdad.
_QA_SWEEP_AGENTS = ["moni", "rena", "sara", "xime"]

# Modo "release" (2026-08-24, esquema real de Finanz Butik): consistencia
# de marca/diseño/copy/contenido, corrida 1×/release en vez de por proyecto.
_QA_RELEASE_AGENTS = ["sara", "xime", "vane"]

# Criterion-based prompt (2026-08-24) — reemplaza el "corré tu verificación"
# genérico por el formato real que usa el QA de Finanz Butik
# (planning-fb/qa/QA-EXECUTION-TEMPLATE.md): cada scenario es un criterio
# testeable, validado por los 3 checks T/UX/HU, nunca prosa libre.
_CRITERIA_TABLE_INSTRUCTIONS = (
    "Formato obligatorio de salida: una tabla Markdown con columnas "
    "ID | Criterio | T | UX | HU | Resultado. Cada fila es UN criterio "
    "testeable (una afirmación que debe ser verdadera, no una tarea). "
    "T/UX/HU son ☑ o ☐ según si ese chequeo se cumple (Technical / "
    "User-facing / Historia de Usuario). Resultado es ✅/❌/⛔. "
    "Un criterio solo es ✅ si T, UX y HU están los tres marcados."
)


def _qa_sweep_agents_for(scope: str) -> list[str]:
    return _QA_RELEASE_AGENTS if scope == "release" else _QA_SWEEP_AGENTS


def _parse_pau_findings(report_text: str) -> list[Finding]:
    """Pau's real output includes a fenced ```json findings block (asked for
    explicitly in the prompt below) — parsed here so the gate is computed in
    Python, never trusted from the model's own arithmetic. Missing/malformed
    JSON yields zero findings (never fabricated), not an error — the report
    text itself is still returned to the caller either way."""
    # Non-greedy on the *fence* (```), not on the braces — a naive `\{.*?\}`
    # cuts at the first inner `}` and breaks on more than one finding (found
    # live 2026-08-24: Pau's real multi-finding JSON silently parsed empty).
    match = re.search(r"```json\s*(.*?)\s*```", report_text, re.DOTALL)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
        return [Finding(**item) for item in payload.get("findings", [])]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


@router.post("/projects/{project_id}/qa-sweep")
async def run_qa_sweep(
    project_id: str,
    scope: str = Query(default="project", pattern="^(project|release)$"),
    client: AsyncAnthropic = Depends(_get_anthropic_client),
) -> dict[str, Any]:
    """Capa 2 de QA (a demanda — SPEC_JARVIS.md §14/§15/§16): encadena los
    agentes reales de Fase 4 en vez de 6 invocaciones manuales sueltas.
    Nunca falla completo por un agente puntual — cada paso queda registrado
    con su propio resultado o error, y pau arma el reporte con lo que sí
    haya salido real.

    `scope=release` (2026-08-24, esquema de Finanz Butik): corre el set de
    agentes de consistencia cross-cutting (marca/diseño/copy/contenido) en
    vez de la cadena por-proyecto — pensado para correr 1×/release, no por
    HU. `scope=project` (default) es el flujo original."""
    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    agents_to_run = _qa_sweep_agents_for(scope)
    steps: dict[str, Any] = {}
    for agent_name in agents_to_run:
        try:
            result = await invoke_agent_core(
                client,
                agent_name,
                project_id,
                (
                    f"Corré tu verificación real de Fase 4 para el proyecto {project.get('name', project_id)}"
                    f" (scope={scope}). {_CRITERIA_TABLE_INSTRUCTIONS}"
                ),
                {"trigger": "qa_sweep", "phase": "4", "scope": scope},
            )
            steps[agent_name] = {"output": result["output"]}
        except HTTPException as error:
            steps[agent_name] = {"error": error.detail}

    reconciliation = None
    gaps: list[dict[str, Any]] = []
    if scope == "project":
        reconciliation = await run_reconciliation(project_id)
        gaps = (reconciliation or {}).get("gaps", [])
    sin_test = sum(1 for g in gaps if g.get("status") == "sin_test")

    summary_input = (
        f"Resultados reales de la corrida de QA ({scope}) para {project.get('name', project_id)}:\n"
        + "\n".join(
            f"- {agent}: {step.get('error') or step.get('output', '')[:600]}"
            for agent, step in steps.items()
        )
        + (f"\n- Reconciliación: {len(gaps)} gaps totales, {sin_test} sin_test.\n" if scope == "project" else "\n")
        + "Genera el reporte de consolidación go/no-go basado únicamente en esto — no inventes datos que no estén acá. "
        "Al final del reporte, agregá un bloque ```json con exactamente esta forma: "
        '{"findings": [{"title": "...", "severity": "S1|S2|S3|S4|S5", "category": "...", '
        '"description": "...", "criterionId": "..."}]} — un finding por cada criterio ❌/⛔ '
        "real que hayas visto arriba. S1/S2 = bloqueante (rompe el flujo/pierde datos/rompe un AC). "
        "Sin hallazgos reales, el array queda vacío — nunca inventes uno para 'tener algo que reportar'."
    )
    report: str | None = None
    findings: list[Finding] = []
    try:
        pau_result = await invoke_agent_core(
            client, "pau", project_id, summary_input, {"trigger": "qa_sweep", "phase": "4", "scope": scope}
        )
        report = pau_result["output"]
        findings = _parse_pau_findings(report)
    except HTTPException as error:
        steps["pau"] = {"error": error.detail}

    sweep = QaSweepReport(
        projectId=project_id,
        scope=scope,  # type: ignore[arg-type]
        steps=steps,
        reconciliation=reconciliation,
        findings=findings,
        report=report,
    )

    project.setdefault("memory", {}).setdefault("qaSweeps", []).append(sweep.to_public_dict())
    storage.write_projects(projects)

    return sweep.to_public_dict()


@router.post("/projects/{project_id}/qa-sweeps/{sweep_id}/signoff")
async def signoff_qa_sweep(project_id: str, sweep_id: str, body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Sign-off humano real (2026-08-24, esquema de Finanz Butik) — un ciclo
    de QA no queda "cerrado" solo porque el gate mecánico dio APPROVED;
    hace falta que una persona (PM o Tech Lead) lo firme explícitamente."""
    reviewer = body.get("reviewer")
    verdict = body.get("verdict")
    if reviewer not in ("PM", "TechLead") or verdict not in ("APPROVED", "NOT_APPROVED"):
        raise HTTPException(status_code=400, detail="reviewer (PM|TechLead) and verdict (APPROVED|NOT_APPROVED) are required")

    storage = get_storage()
    projects = storage.read_projects()
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    sweeps = project.get("memory", {}).get("qaSweeps", [])
    sweep = next((s for s in sweeps if s.get("id") == sweep_id), None)
    if not sweep:
        raise HTTPException(status_code=404, detail="QA sweep not found")

    sweep.setdefault("signoffs", []).append(Signoff(reviewer=reviewer, verdict=verdict).model_dump(mode="json"))
    storage.write_projects(projects)
    return sweep


@router.post("/evaluate")
async def evaluate(
    body: dict[str, Any] = Body(...),
    evaluator: AgentEvaluator = Depends(_get_evaluator),
) -> dict[str, Any]:
    agent_name = body.get("agentName")
    output = body.get("output")
    context = body.get("context")

    if not agent_registry.is_known_agent(agent_name):
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_name}")

    return await evaluator.evaluate(agent_name, output, context)
