"""
GET endpoints for the Analytics/Metrics layer (ARCHITECTURE_JARVIS.md §4/§7,
SPEC_JARVIS.md HU-008/009/010-JarvisMode). Write path is
services/metrics/collector.py, called from the routers/services that produce
each event (agent_evaluator, jarvis_chat, reconciliation); this router is the
read-only surface for the analytics panel.

# TODO: calibrar en implementacion — the parallel "metrics" phase left
# services/metrics/collector.py + schemas/metrics.py on disk but no router;
# this is the integration agent's fill-in, a thin pass-through over
# collector.py's existing read_* helpers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import authenticate_token
from app.services.metrics import collector

router = APIRouter(dependencies=[Depends(authenticate_token)])


@router.get("/metrics/agent-evaluations")
async def agent_evaluations() -> list[dict[str, Any]]:
    return collector.read_agent_evaluations()


@router.get("/metrics/reconciliation-runs")
async def reconciliation_runs() -> list[dict[str, Any]]:
    return collector.read_reconciliation_runs()


@router.get("/metrics/usage-events")
async def usage_events() -> list[dict[str, Any]]:
    return collector.read_usage_events()


@router.get("/metrics/output-counts")
async def output_counts() -> list[dict[str, Any]]:
    return collector.read_output_counts()


@router.get("/metrics/summary")
async def summary() -> dict[str, Any]:
    """One-shot payload for HU-010's analytics panel — all four series
    together, so the frontend doesn't need four round-trips."""
    return {
        "agentEvaluations": collector.read_agent_evaluations(),
        "reconciliationRuns": collector.read_reconciliation_runs(),
        "usageEvents": collector.read_usage_events(),
        "outputCounts": collector.read_output_counts(),
    }
