"""
QA-E2E runner (Tarea 3, PLAN-qa-automation.md) — a small Playwright-backed
agent that walks a simple test plan against a live URL and reports results
using the SAME `Finding` schema as the rest of QA (app/schemas/qa.py), so
this never becomes a second, parallel report format.

Runs from Python (not a separate Node process) on purpose: the runner needs
to emit `Finding` objects straight into the existing `QaSweepReport` /
qa-sweep pipeline, and doing that across a language boundary would mean
translating a Node report back into this schema — extra moving parts for no
benefit, since Playwright's Python API covers the (navigate/click/assert
text) step vocabulary this needs.

IMPORTANT — deploy requirement: this module imports `playwright.sync_api`
lazily (inside `run_plan`, not at module top) specifically so that importing
this file, constructing `TestStep`/`Finding` objects, and running unit tests
against a MOCKED `_execute_plan` never requires the actual Chromium browser
binary to be present. Before running a REAL E2E pass (not mocked), the
environment must have run:

    pip install -e ".[test]"
    playwright install chromium

No browser binaries are installed by this pass — only the dependency and
this scaffolding are added (see PLAN-qa-automation.md, Tarea 3).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.qa import Finding

EVIDENCE_ROOT = Path("qa/evidence")


class TestStep(BaseModel):
    """One step of a simple E2E plan. `action` is intentionally a small,
    closed vocabulary — navigate/click/assert_text — matching the task spec;
    extend here (not with a free-form DSL) when a new action is needed."""

    action: Literal["navigate", "click", "assert_text"]
    # navigate: value = URL. click: value = CSS selector. assert_text: value = expected substring.
    value: str
    selector: str | None = None  # required for assert_text scoped to one element


class TestPlan(BaseModel):
    target_url: str
    steps: list[TestStep] = Field(default_factory=list)
    project_id: str | None = None


def _new_run_id() -> str:
    return f"e2e-{uuid.uuid4().hex[:10]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _evidence_dir(run_id: str) -> Path:
    directory = EVIDENCE_ROOT / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _execute_plan(plan: TestPlan, run_id: str) -> tuple[list[Finding], Path | None]:
    """Real execution path — imports Playwright lazily so a missing browser
    binary only breaks this function, never module import or unit tests that
    mock it out. Returns (findings, screenshot_path)."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 (intentional lazy import)

    findings: list[Finding] = []
    evidence_dir = _evidence_dir(run_id)
    screenshot_path = evidence_dir / "final.png"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for step in plan.steps:
                try:
                    if step.action == "navigate":
                        page.goto(step.value)
                    elif step.action == "click":
                        page.click(step.value)
                    elif step.action == "assert_text":
                        content = page.content()
                        if step.value not in content:
                            findings.append(
                                Finding(
                                    title=f"Texto esperado no encontrado: {step.value!r}",
                                    severity="S2",
                                    category="qa-e2e",
                                    description=f"Paso {step.action} sobre {plan.target_url} falló.",
                                )
                            )
                except Exception as exc:  # noqa: BLE001 — one failed step -> one Finding, run continues
                    findings.append(
                        Finding(
                            title=f"Paso E2E falló: {step.action} {step.value}",
                            severity="S1",
                            category="qa-e2e",
                            description=str(exc),
                        )
                    )
            page.screenshot(path=str(screenshot_path))
        finally:
            browser.close()

    return findings, screenshot_path


def run_plan(plan: TestPlan) -> list[Finding]:
    """Entry point: runs `plan` against `plan.target_url`, saves evidence
    under qa/evidence/<run_id>/, and returns Finding[] (app/schemas/qa.py) —
    the same schema the QA sweep uses, so these findings can be appended
    straight into a QaSweepReport.findings list.
    """
    run_id = _new_run_id()
    evidence_dir = _evidence_dir(run_id)
    (evidence_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    try:
        findings, screenshot_path = _execute_plan(plan, run_id)
    except Exception as exc:  # noqa: BLE001 — e.g. Chromium not installed
        findings = [
            Finding(
                title="No se pudo ejecutar el plan E2E",
                severity="S1",
                category="qa-e2e",
                description=(
                    f"{exc}. Verifica que Playwright/Chromium estén instalados "
                    "(`pip install -e \".[test]\" && playwright install chromium`)."
                ),
            )
        ]
        screenshot_path = None

    report = {
        "run_id": run_id,
        "target_url": plan.target_url,
        "project_id": plan.project_id,
        "createdAt": _now_iso(),
        "findings": [f.model_dump(mode="json") for f in findings],
        "screenshot": str(screenshot_path) if screenshot_path else None,
    }
    (evidence_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return findings
