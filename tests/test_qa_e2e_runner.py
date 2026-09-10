"""Tests for app/services/qa_e2e_runner.py (Tarea 3). Real Playwright/
Chromium is NOT installed in CI for this pass — _execute_plan is mocked so
these tests verify the schema/wiring (TestPlan -> Finding[] in
app/schemas/qa.py's format), not real browser behavior."""

from __future__ import annotations

from unittest.mock import patch

from app.schemas.qa import Finding
from app.services import qa_e2e_runner
from app.services.qa_e2e_runner import TestPlan, TestStep, run_plan


def test_test_plan_builds_from_simple_steps():
    plan = TestPlan(
        target_url="https://example.com",
        steps=[
            TestStep(action="navigate", value="https://example.com"),
            TestStep(action="click", value="#login"),
            TestStep(action="assert_text", value="Bienvenida"),
        ],
    )
    assert plan.target_url == "https://example.com"
    assert len(plan.steps) == 3


def test_run_plan_returns_findings_in_qa_schema_when_execution_mocked():
    plan = TestPlan(target_url="https://example.com", steps=[TestStep(action="navigate", value="https://example.com")])

    fake_finding = Finding(title="algo", severity="S3", category="qa-e2e")
    with patch.object(qa_e2e_runner, "_execute_plan", return_value=([fake_finding], None)):
        findings = run_plan(plan)

    assert len(findings) == 1
    assert isinstance(findings[0], Finding)
    assert findings[0].severity == "S3"


def test_run_plan_without_chromium_returns_s1_finding_instead_of_raising():
    """No browser installed -> _execute_plan raises -> run_plan must still
    return a Finding (S1) instead of propagating the exception, per the
    "verifica que al menos el import... funcionen" requirement."""
    plan = TestPlan(target_url="https://example.com", steps=[])

    with patch.object(qa_e2e_runner, "_execute_plan", side_effect=RuntimeError("Executable doesn't exist")):
        findings = run_plan(plan)

    assert len(findings) == 1
    assert findings[0].severity == "S1"
    assert "Playwright" in findings[0].description or "Chromium" in findings[0].description


def test_import_and_finding_construction_do_not_require_playwright_installed():
    """Module import + Finding construction must work even if the real
    playwright package/browser isn't available — the lazy import inside
    _execute_plan is what makes this possible."""
    finding = Finding(title="x", severity="S5")
    assert finding.severity == "S5"
