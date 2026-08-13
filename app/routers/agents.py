"""
GET /agents, GET /phases, GET /phases/{id_or_key}, POST /agents/{name}/invoke,
POST /orchestrate, POST /evaluate — migrated from server.js. All require the
auth dependency (health is the only unauthenticated route, in health.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anthropic
from anthropic import AsyncAnthropic
from fastapi import APIRouter, Body, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.security import authenticate_token
from app.core.storage import get_storage
from app.phases import phase_contracts
from app.services import agent_registry
from app.services.agent_evaluator import AgentEvaluator
from app.services.metrics.evaluate_invocation import evaluate_and_check

router = APIRouter(dependencies=[Depends(authenticate_token)])

# Which agent handles a given (phase, step) — validated against
# phase_contracts so we never invoke an agent that isn't actually assigned to
# that phase.
#
# santi/daniel (actas, release notes) are intentionally NOT here: they aren't
# tied to a single phase step, they run continuously across the whole
# lifecycle. Invoke them directly via /agents/{name}/invoke instead.
STEP_TO_AGENT: dict[str, str] = {
    "1:lock_scope": "gimena",
    "1:milestones": "milestone-writer",
    "1:dod": "dod-definer",
    "1:estimation": "gabi",
    "1:reconciliation": "capacity-reconciler",
    "1:timeline": "gina-scheduler",
    "1:transversales": "auditor",
    "2:data_model": "data-engineer",
    "2:work_plan": "gabi",
    "2:review": "auditor",
    "3:frontend_web": "fullstack-developer",
    "3:frontend_app": "flutter-developer",
    "3:integration": "integration",
    "4:sonar_gate": "sonar-quality-gate",
    "4:unit_test_review": "unit-test-standards-reviewer",
    "4:quality_report": "quality-report-generator",
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

    # HU-008-JarvisMode: autoevaluación multidimensional inmediata — corre en
    # cada invocación real, no como paso manual aparte (AC 2.1.2). No debe
    # tumbar la invocación si la evaluación falla (ej. el juez de acertividad
    # tiene un error transitorio de red).
    try:
        result["evaluation"] = await evaluate_and_check(
            name, result["output"], context, input_=input_, client=client
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
