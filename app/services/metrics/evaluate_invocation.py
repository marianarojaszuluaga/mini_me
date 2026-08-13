"""
HU-008-JarvisMode — Autoevaluación multidimensional y continua.

Runs the 4 dimensions (eficiencia, acertividad, formato, calidad) on a real
agent invocation output and persists the result via metrics/collector.py.
Also implements the "2 consecutive low-quality invocations" degradation
check that feeds HU-009's changelog proposal flow.

Called from app/routers/agents.py right after a real Claude call produces
`output` — never as a separate manual step (SPEC_JARVIS.md §8, AC 2.1.2).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.services import agent_registry
from app.services.agent_evaluator import AgentEvaluator
from app.services.metrics import collector
from app.schemas.metrics import AgentEvaluation

# Fast/cheap model for the acertividad judge call — same tier rationale as
# AgentEvaluator's own EVALUATOR_MODEL (mechanical judging, highest-volume
# call if run on every invocation).
ACERTIVIDAD_MODEL = "claude-3-5-haiku-20241022"

# TODO: calibrar en implementacion — starting thresholds; tune once real
# invocation history is observed. Below this score counts as "low" for the
# HU-008 degradation check (2 consecutive lows -> changelog proposal).
DEGRADATION_THRESHOLD = 60.0

# TODO: calibrar en implementacion — eficiencia heuristic constants below.
_EFICIENCIA_IDEAL_CHARS_PER_STEP = 400  # a "step" being a requested item/AC/bullet
_EFICIENCIA_MIN_SCORE = 20.0


@dataclass(frozen=True)
class InvocationEvaluation:
    agent: str
    eficiencia: float
    acertividad: float
    formato: float
    calidad: float
    details: dict[str, Any]


def _count_requested_steps(input_: str, context: dict[str, Any] | None) -> int:
    """Rough count of "things asked for" in the input/context, used as the
    denominator for the eficiencia heuristic. Counts explicit list markers
    (numbered/bulleted lines) in the input, falling back to sentence count,
    with a floor of 1 so we never divide by zero."""
    text = input_ or ""
    bullet_matches = re.findall(r"(?:^|\n)\s*(?:[-*]|\d+[.)])\s+\S", text)
    if bullet_matches:
        return len(bullet_matches)

    if context:
        for key in ("acceptanceCriteria", "steps", "items", "requirements"):
            value = context.get(key)
            if isinstance(value, list) and value:
                return len(value)

    sentences = [s for s in re.split(r"[.!?\n]+", text) if s.strip()]
    return max(len(sentences), 1)


def _eficiencia_heuristic(output: str, input_: str, context: dict[str, Any] | None) -> tuple[float, str]:
    """Real (non-placeholder) heuristic: compares output length against what
    the input/context actually asked for. An output that's proportionate to
    the number of requested steps scores near 100; one that's wildly more
    verbose than the ask (padding, repetition, over-explaining) is penalized
    down toward _EFICIENCIA_MIN_SCORE. Under-length outputs relative to the
    ask are penalized too (likely incomplete, not "efficient").
    """
    requested_steps = _count_requested_steps(input_, context)
    output_len = len(output or "")
    expected_len = requested_steps * _EFICIENCIA_IDEAL_CHARS_PER_STEP

    if expected_len <= 0:
        return 100.0, "No se pudo estimar pasos solicitados; se asume eficiente."

    ratio = output_len / expected_len

    if 0.5 <= ratio <= 1.75:
        # Within a reasonable band around the expected size -> full score,
        # tapering slightly the further from 1.0 it is inside the band.
        score = 100.0 - abs(1.0 - ratio) * 20.0
    elif ratio > 1.75:
        # Verbosity penalty: scales down as the overage grows, floor at
        # _EFICIENCIA_MIN_SCORE so a single bad case doesn't zero out.
        overage = ratio - 1.75
        score = max(_EFICIENCIA_MIN_SCORE, 100.0 - overage * 30.0)
    else:
        # Under-length: likely missing requested content.
        shortage = 0.5 - ratio
        score = max(_EFICIENCIA_MIN_SCORE, 100.0 - shortage * 60.0)

    reasoning = (
        f"{requested_steps} paso(s) detectado(s) en el input, "
        f"{output_len} chars de output vs. {expected_len:.0f} esperados "
        f"(ratio={ratio:.2f})."
    )
    return round(score, 1), reasoning


_ACERTIVIDAD_PROMPT = """Evalúa si el siguiente OUTPUT responde efectivamente a lo que pedía el INPUT/CONTEXTO. \
No evalúes calidad de redacción ni formato, solo si es correcto y relevante respecto a lo preguntado.

INPUT:
{input_}

CONTEXTO:
{context}

OUTPUT:
{output}

Responde SOLO con este JSON, sin texto adicional:
{{"score": <0-100>, "reasoning": "<una frase>"}}"""


async def _acertividad_judge(
    client: AsyncAnthropic, output: str, input_: str, context: dict[str, Any] | None
) -> tuple[float, str]:
    """Short Claude call judging whether the output addresses the ask, 0-100."""
    prompt = _ACERTIVIDAD_PROMPT.format(
        input_=input_ or "(sin input explícito)",
        context=json.dumps(context or {}, ensure_ascii=False),
        output=output,
    )
    try:
        response = await client.messages.create(
            model=ACERTIVIDAD_MODEL,
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return 0.0, "No se pudo parsear el juicio de acertividad."
        parsed = json.loads(match.group(0))
        score = float(parsed.get("score", 0))
        return max(0.0, min(100.0, score)), parsed.get("reasoning", "")
    except Exception as error:  # noqa: BLE001 - never let the judge call break the invocation
        return 0.0, f"Error evaluando acertividad: {error}"


# Agents whose documented contract is strict JSON (per agent_registry.py's
# prompts: gabriela/santi/daniel all say "Responde SOLO en JSON"). gimena is
# the HU-format contract (Gimena-style: CONTEXTO/CRITERIOS DE ACEPTACION).
_JSON_CONTRACT_AGENTS = {"gabriela", "santi", "daniel"}
_HU_FORMAT_AGENTS = {"gimena"}


def _formato_heuristic(agent_name: str, output: str) -> tuple[float, str]:
    """Validates the agent's expected output contract:
    - JSON-contract agents: attempt to parse; full score if valid JSON,
      partial credit if a JSON object is embedded in extra text, 0 if
      unparseable.
    - HU-format agents (Gimena-style): checks for the basic structural
      markers required by the format (CONTEXTO/CRITERIOS DE ACEPTACION
      headers, "Como/Quiero/Para" story shape).
    - Unknown/other agents: no specific contract to validate -> full score,
      formato isn't a meaningful constraint for them.
    """
    if agent_name in _JSON_CONTRACT_AGENTS:
        try:
            json.loads(output)
            return 100.0, "JSON válido y bien formado."
        except (json.JSONDecodeError, TypeError):
            match = re.search(r"\{[\s\S]*\}", output or "")
            if match:
                try:
                    json.loads(match.group(0))
                    return 60.0, "JSON válido pero embebido en texto adicional (no estricto)."
                except json.JSONDecodeError:
                    pass
            return 0.0, "Se esperaba JSON estricto y el output no es JSON parseable."

    if agent_name in _HU_FORMAT_AGENTS:
        required_markers = ["CONTEXTO", "CRITERIOS DE ACEPTACION", "CRITERIOS DE ACEPTACIÓN"]
        text_upper = (output or "").upper()
        has_context = "CONTEXTO" in text_upper
        has_ac = "CRITERIOS DE ACEPTACION" in text_upper or "CRITERIOS DE ACEPTACIÓN" in text_upper
        has_story_shape = bool(re.search(r"como.{0,40}quiero.{0,80}para", output or "", re.IGNORECASE | re.DOTALL))

        checks_passed = sum([has_context, has_ac, has_story_shape])
        score = (checks_passed / 3.0) * 100.0
        missing = [
            name
            for name, present in (
                ("CONTEXTO", has_context),
                ("CRITERIOS DE ACEPTACION", has_ac),
                ("estructura Como/Quiero/Para", has_story_shape),
            )
            if not present
        ]
        reasoning = "Formato de HU completo." if not missing else f"Faltan: {', '.join(missing)}."
        return round(score, 1), reasoning

    return 100.0, "Agente sin contrato de formato específico validado."


async def evaluate_invocation(
    agent_name: str,
    output: str,
    context: dict[str, Any] | None,
    *,
    input_: str = "",
    client: AsyncAnthropic | None = None,
    evaluator: AgentEvaluator | None = None,
) -> InvocationEvaluation:
    """Runs all 4 HU-008 dimensions on one real agent output and persists
    the result via metrics/collector.record_evaluation. Returns the
    evaluation so the caller (POST /agents/{name}/invoke) can attach it to
    the response immediately (AC 2.1.2 — no waiting on a later job)."""
    settings = get_settings()
    own_client = client is None
    client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    evaluator = evaluator or AgentEvaluator(api_key=settings.ANTHROPIC_API_KEY)

    context = context or {}

    # calidad: delegate entirely to the already-migrated rubric. Falls back
    # to generic_criteria internally for agents without a bespoke rubric
    # (agent_evaluator.py's own behavior) — satisfies the "no rubric ->
    # generic fallback" error case in HU-008 §2.3.
    calidad_result = await evaluator.evaluate(agent_name, output, context)
    calidad_score = float(calidad_result["scores"]["overall"])

    eficiencia_score, eficiencia_reasoning = _eficiencia_heuristic(output, input_, context)
    acertividad_score, acertividad_reasoning = await _acertividad_judge(client, output, input_, context)
    formato_score, formato_reasoning = _formato_heuristic(agent_name, output)

    record: AgentEvaluation = await collector.record_evaluation(
        agent_name=agent_name,
        calidad=calidad_score,
        eficiencia=eficiencia_score,
        acertividad=acertividad_score,
        formato=formato_score,
    )

    if own_client:
        await client.close()

    return InvocationEvaluation(
        agent=agent_name,
        eficiencia=eficiencia_score,
        acertividad=acertividad_score,
        formato=formato_score,
        calidad=calidad_score,
        details={
            "eficiencia": eficiencia_reasoning,
            "acertividad": acertividad_reasoning,
            "formato": formato_reasoning,
            "calidad": calidad_result["scores"].get("summary", ""),
            "record": record.model_dump(mode="json"),
        },
    )


def _parse_row_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def check_degradation(agent_name: str, dimension: str, threshold: float = DEGRADATION_THRESHOLD) -> bool:
    """HU-008 §2.1.3 / §2.2: if the last 2 invocations of `agent_name` in
    `dimension` are both below `threshold`, returns True (degradation
    detected). Strictly "2 consecutive" — a good invocation in between
    resets the streak (HU-008 §2.3 error case), which falls out naturally
    from only ever looking at the most recent 2 records.

    Does NOT create the changelog proposal itself — callers that detect
    degradation are expected to hand off to changelog.create_proposal().
    """
    if dimension not in ("eficiencia", "acertividad", "formato", "calidad"):
        raise ValueError(f"Unknown dimension: {dimension}")

    all_evaluations = collector.read_agent_evaluations()
    agent_evaluations = [row for row in all_evaluations if row.get("agent") == agent_name]

    if len(agent_evaluations) < 2:
        return False

    # Series is append-only in date order (collector.append_series) -> the
    # last 2 entries are the last 2 invocations.
    last_two = agent_evaluations[-2:]
    return all(row.get(dimension, 100) < threshold for row in last_two)


async def evaluate_and_check(
    agent_name: str,
    output: str,
    context: dict[str, Any] | None,
    *,
    input_: str = "",
    client: AsyncAnthropic | None = None,
    evaluator: AgentEvaluator | None = None,
) -> dict[str, Any]:
    """Convenience entry point for the invoke handler: runs
    evaluate_invocation, then check_degradation for each of the 4
    dimensions, and files a changelog proposal for each degraded one.

    Returns a dict shaped for direct inclusion in the /invoke response:
    {"dimensions": {...}, "degraded": ["eficiencia", ...]}
    """
    evaluation = await evaluate_invocation(
        agent_name, output, context, input_=input_, client=client, evaluator=evaluator
    )

    degraded: list[str] = []
    for dimension in ("eficiencia", "acertividad", "formato", "calidad"):
        if check_degradation(agent_name, dimension):
            degraded.append(dimension)

            # HU-009's changelog: app/services/changelog.py now exists.
            # create_proposal()'s real signature is
            # (agent_name, what_changed, reason, before_window) -> dict, and
            # it computes before_scores itself from before_window (it is not
            # given raw scores directly). Build a before_window covering the
            # last 2 evaluations of this agent/dimension so before_scores
            # reflects exactly the low streak that triggered the proposal.
            from app.services import changelog
            from app.schemas.changelog import DateWindow

            agent_rows = [
                row
                for row in collector.read_agent_evaluations()
                if row.get("agent") == agent_name
            ]
            recent_rows = agent_rows[-2:]
            recent_scores = [row.get(dimension) for row in recent_rows]
            window_dates = [_parse_row_date(row["date"]) for row in recent_rows]
            before_window = DateWindow(start=min(window_dates), end=max(window_dates))

            changelog.create_proposal(
                agent_name=agent_name,
                what_changed=(
                    f"Propuesta automática: degradación detectada en '{dimension}' "
                    f"(2 invocaciones seguidas por debajo de {DEGRADATION_THRESHOLD})."
                ),
                reason=(
                    f"2 invocaciones seguidas bajas en {dimension} "
                    f"(scores: {recent_scores}) — HU-008 §2.1.3."
                ),
                before_window=before_window,
            )

    return {
        "dimensions": {
            "eficiencia": evaluation.eficiencia,
            "acertividad": evaluation.acertividad,
            "formato": evaluation.formato,
            "calidad": evaluation.calidad,
        },
        "details": evaluation.details,
        "degraded": degraded,
    }
