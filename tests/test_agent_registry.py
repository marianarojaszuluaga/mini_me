"""Every registered agent must actually load its .md file and build a real
prompt — this is the gap Mariana caught: 26 agents in the roster, 0 tests
that confirm any of them actually loads (2026-09-17)."""

import pytest

from app.services import agent_registry


ALL_AGENT_IDS = [entry["id"] for entry in agent_registry.list_agents()]


def test_roster_has_26_agents():
    assert len(ALL_AGENT_IDS) == 26, ALL_AGENT_IDS


@pytest.mark.parametrize("agent_id", ALL_AGENT_IDS)
def test_agent_is_known(agent_id):
    assert agent_registry.is_known_agent(agent_id)


@pytest.mark.parametrize("agent_id", ALL_AGENT_IDS)
def test_agent_prompt_loads_from_disk(agent_id):
    prompt = agent_registry.build_prompt(agent_id, "test input", {"project_id": "test"})
    assert prompt is not None
    assert prompt.system, f"{agent_id} loaded an empty system prompt"
    assert "test input" in prompt.user


@pytest.mark.parametrize("agent_id", ALL_AGENT_IDS)
def test_agent_has_model_config(agent_id):
    config = agent_registry.get_model_config(agent_id)
    assert config["model"]
    assert config["max_tokens"] > 0


def test_unknown_agent_is_rejected():
    assert not agent_registry.is_known_agent("no-existe")
    assert agent_registry.build_prompt("no-existe", "x") is None
