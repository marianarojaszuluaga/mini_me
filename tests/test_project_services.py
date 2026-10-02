"""
Section 6 of the Project Brain template (Gabriela) — the 5 canonical
services declared for a project. Mariana's requirement (2026-09-24): each
service must have real agency, i.e. an entrypoint that actually executes
from the repo with nothing more than running it locally. This test pins
that every default entrypoint is a real route registered somewhere in the
app, not a placeholder string that looks plausible but points nowhere.
"""

from __future__ import annotations

from app.schemas.project import ProjectBrain, ProjectService, _default_services


def test_default_services_cover_the_five_canonical_ids():
    services = _default_services()
    assert {s.id for s in services} == {
        "qa_human",
        "qa_automated",
        "pr_review",
        "drive_sync",
        "basecamp_sync",
    }


def test_default_services_start_disabled_but_invocable():
    for service in _default_services():
        assert service.enabled is False
        assert service.invocable is True
        assert service.entrypoint  # never blank — always the real route/command


def test_project_brain_defaults_include_services():
    brain = ProjectBrain()
    assert len(brain.services) == 5
    assert all(isinstance(s, ProjectService) for s in brain.services)


def test_entrypoints_match_real_registered_routes():
    from app.main import app

    registered = {route.path for route in app.routes}

    for service in _default_services():
        if service.id == "drive_sync":
            # mia/nico are concrete agent ids invoked through the generic
            # /agents/{name}/invoke route — not routes of their own.
            paths = ["/agents/{name}/invoke"]
        else:
            _, path = service.entrypoint.split(" ", 1)
            paths = [path.split(",")[0].strip()]

        for path in paths:
            assert path in registered, (
                f"{service.id}: entrypoint {path!r} is not a real registered "
                f"route — services must stay invocable, never aspirational"
            )
