"""
Agent Evaluator — migrated from src/agent-evaluator.js.

Independent quality assessment layer: scores an agent's output against a
per-agent weighted rubric (or a generic fallback for agents without one),
via a single Anthropic call on haiku (mechanical enough, and this is the
highest-volume call in the system if it runs on every invocation).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic

EVALUATOR_MODEL = "claude-sonnet-4-6"


@dataclass(frozen=True)
class Dimension:
    weight: float
    description: str


@dataclass(frozen=True)
class AgentCriteria:
    name: str
    dimensions: dict[str, Dimension]
    target_score: int


EVALUATION_CRITERIA: dict[str, AgentCriteria] = {
    "gime": AgentCriteria(
        name="Gime - User Story Writer",
        dimensions={
            "format_compliance": Dimension(0.2, "HU format compliance (As/I want/For structure)"),
            "completeness": Dimension(0.3, "Complete AC, error handling, visual references"),
            "clarity": Dimension(0.2, "Language clarity, technical accuracy"),
            "actionability": Dimension(0.2, "Clear next steps, no ambiguity"),
            "alignment": Dimension(0.1, "Business & technical requirements met"),
        },
        target_score=90,
    ),
    "gabi": AgentCriteria(
        name="Gabi - Work Planner",
        dimensions={
            "phase_completeness": Dimension(0.2, "All 5 phases detailed (DB→Backend→API→Frontend→Integration)"),
            "tdd_strategy": Dimension(0.25, "Unit, Integration, API, E2E test strategies"),
            "solid_application": Dimension(0.2, "All 5 SOLID principles documented"),
            "estimations": Dimension(0.2, "Optimistic, Realistic, Pessimistic with confidence"),
            "risk_management": Dimension(0.15, "Risk assessment with mitigation"),
        },
        target_score=85,
    ),
    "gaby": AgentCriteria(
        name="Gaby - Project Brain",
        dimensions={
            "stakeholder_clarity": Dimension(0.2, "Complete stakeholder table with roles"),
            "scope_definition": Dimension(0.25, "In/Out scope matrix clarity"),
            "timeline_completeness": Dimension(0.15, "Start, end, milestones defined"),
            "business_rules": Dimension(0.2, "Critical rules documented"),
            "documentation_currency": Dimension(0.2, "Meeting log and change log up-to-date"),
        },
        target_score=90,
    ),
    "santi": AgentCriteria(
        name="Santi - Meeting Minutes",
        dimensions={
            "format_compliance": Dimension(0.25, "H1/H2/H3 hierarchy correct (no H2 numbers)"),
            "action_items": Dimension(0.25, "☐ symbol usage, owner, deadline"),
            "language_precision": Dimension(0.2, "Direct language, no 'mentioned that' phrases"),
            "risk_identification": Dimension(0.2, "Alerts and red flags clearly marked"),
            "professional_tone": Dimension(0.1, "Executive, results-oriented tone"),
        },
        target_score=85,
    ),
    "dani": AgentCriteria(
        name="Dani - Release Notes",
        dimensions={
            "technical_accuracy": Dimension(0.25, "Bitbucket version accuracy"),
            "dual_version_coherence": Dimension(0.25, "Bitbucket ↔ Basecamp alignment"),
            "audience_appropriateness": Dimension(0.2, "Technical vs client-friendly tone"),
            "completeness": Dimension(0.2, "All commits, features, fixes included"),
            "presentation": Dimension(0.1, "Professional, clear structure"),
        },
        target_score=90,
    ),
}


def generic_criteria(agent_name: str) -> AgentCriteria:
    """Fallback rubric for agents without a bespoke one (e.g. the 14 spec-kit
    agents) so /evaluate never 400s on a known, invokable agent."""
    return AgentCriteria(
        name=agent_name,
        dimensions={
            "completeness": Dimension(0.3, "Output covers what was asked"),
            "clarity": Dimension(0.25, "Clear, unambiguous"),
            "adherence": Dimension(0.25, "Follows the agent's documented role/restrictions"),
            "actionability": Dimension(0.2, "Next steps are clear"),
        },
        target_score=80,
    )


def _get_status(score: float, target_score: int) -> str:
    if score >= target_score:
        return "EXCELLENT"
    if score >= 75:
        return "GOOD"
    if score >= 50:
        return "WARNING"
    return "CRITICAL"


def _build_evaluation_prompt(criteria: AgentCriteria, output: str, context: dict[str, Any]) -> str:
    dimensions_str = "\n".join(
        f"- {key.replace('_', ' ').upper()}: {dim.description} (Weight: {dim.weight * 100}%)"
        for key, dim in criteria.dimensions.items()
    )

    return f"""You are a quality assurance specialist evaluating AI agent outputs for a project management system.

AGENT: {criteria.name}
TARGET SCORE: {criteria.target_score}/100

EVALUATION DIMENSIONS:
{dimensions_str}

CONTEXT:
{json.dumps(context, indent=2, ensure_ascii=False)}

OUTPUT TO EVALUATE:
{output}

EVALUATION TASK:
1. Score each dimension from 0-100 based on the criteria
2. Calculate weighted overall score
3. Identify red flags (critical issues)
4. Provide improvement recommendations
5. Determine if output meets quality standards

RESPONSE FORMAT (CRITICAL - MUST BE VALID JSON):
{{
  "dimensions": {{
    "dimension_name": {{
      "score": <number 0-100>,
      "reasoning": "<explanation>"
    }}
  }},
  "overall": <weighted average>,
  "status": "<EXCELLENT|GOOD|WARNING|CRITICAL>",
  "redFlags": ["<flag1>", "<flag2>"],
  "recommendations": ["<rec1>", "<rec2>"],
  "summary": "<brief overall assessment>"
}}"""


def _parse_evaluation_response(text: str, criteria: AgentCriteria) -> dict[str, Any]:
    try:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError("No JSON found in response")

        evaluation = json.loads(match.group(0))

        overall = evaluation.get("overall") or 0
        if not overall:
            weighted_score = 0.0
            total_weight = 0.0
            for dim_name, dim in criteria.dimensions.items():
                score = (evaluation.get("dimensions", {}).get(dim_name) or {}).get("score", 0)
                weighted_score += score * dim.weight
                total_weight += dim.weight
            overall = round(weighted_score / total_weight) if total_weight else 0

        return {
            "dimensions": evaluation.get("dimensions", {}),
            "overall": overall,
            "status": evaluation.get("status") or _get_status(overall, criteria.target_score),
            "redFlags": evaluation.get("redFlags", []),
            "recommendations": evaluation.get("recommendations", []),
            "summary": evaluation.get("summary", ""),
        }
    except (ValueError, json.JSONDecodeError) as error:
        print(f"agent_evaluator: parse error: {error}")
        return {
            "dimensions": {},
            "overall": 0,
            "status": "CRITICAL",
            "redFlags": ["Evaluation parsing failed"],
            "recommendations": ["Review agent output format"],
            "summary": "Unable to parse evaluation",
        }


@dataclass
class AgentEvaluator:
    """Async port of the JS AgentEvaluator class. Construct with the
    Anthropic API key; `evaluate()` does one model call per output."""

    api_key: str
    model: str = EVALUATOR_MODEL
    base_url: str | None = None
    _client: AsyncAnthropic = field(init=False, repr=False)

    def __post_init__(self) -> None:
        kwargs: dict[str, Any] = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = AsyncAnthropic(**kwargs)

    async def evaluate(
        self, agent_name: str, output: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        context = context or {}
        criteria = EVALUATION_CRITERIA.get(agent_name) or generic_criteria(agent_name)
        prompt = _build_evaluation_prompt(criteria, output, context)

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            evaluation_text = response.content[0].text
            scores = _parse_evaluation_response(evaluation_text, criteria)

            return {
                "agent": agent_name,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "scores": scores,
                "targetScore": criteria.target_score,
                "status": _get_status(scores["overall"], criteria.target_score),
                "feedback": evaluation_text,
                "dimensions": {k: {"weight": v.weight, "description": v.description} for k, v in criteria.dimensions.items()},
            }
        except Exception as error:  # noqa: BLE001 - surfaced as a wrapped error, matching JS behavior
            raise RuntimeError(f"Evaluation failed for {agent_name}: {error}") from error

    async def evaluate_batch(self, evaluations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = []
        for item in evaluations:
            result = await self.evaluate(item["agent"], item["output"], item.get("context"))
            results.append(result)
        return results

    def generate_report(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        report: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "totalEvaluations": len(evaluations),
            "agents": {},
            "overallMetrics": {
                "averageScore": 0,
                "excellentCount": 0,
                "goodCount": 0,
                "warningCount": 0,
                "criticalCount": 0,
            },
            "trends": [],
            "recommendations": [],
        }

        total_score = 0
        for item in evaluations:
            total_score += item["scores"]["overall"]

            if item["agent"] not in report["agents"]:
                report["agents"][item["agent"]] = {
                    "latestScore": item["scores"]["overall"],
                    "targetScore": item["targetScore"],
                    "status": item["status"],
                    "redFlags": item["scores"]["redFlags"],
                    "recommendations": item["scores"]["recommendations"],
                }

            status = item["status"]
            if status == "EXCELLENT":
                report["overallMetrics"]["excellentCount"] += 1
            elif status == "GOOD":
                report["overallMetrics"]["goodCount"] += 1
            elif status == "WARNING":
                report["overallMetrics"]["warningCount"] += 1
            elif status == "CRITICAL":
                report["overallMetrics"]["criticalCount"] += 1

        report["overallMetrics"]["averageScore"] = round(total_score / len(evaluations)) if evaluations else 0
        return report
