"""Tests for clasi.agent module."""

import pytest

from clasi.agent import Agent
from clasi.project import Project


@pytest.fixture(autouse=True)
def _setup_project(tmp_path, monkeypatch):
    """Set up a Project pointing to tmp_path for each test."""
    monkeypatch.chdir(tmp_path)
    from clasi.mcp_server import set_project
    set_project(tmp_path)


@pytest.fixture
def project(tmp_path):
    """Return a Project rooted at tmp_path."""
    return Project(tmp_path)


# ---------------------------------------------------------------------------
# Agent properties
# ---------------------------------------------------------------------------


class TestAgentProperties:
    """Test Agent.name, tier, model, definition, contract properties."""

    def test_name_is_directory_name(self, project):
        agent = project.get_agent("programmer")
        assert agent.name == "programmer"

    def test_tier_from_contract(self, project):
        agent = project.get_agent("programmer")
        # programmer contract has tier: 2
        assert agent.tier == 2

    def test_model_from_contract(self, project):
        agent = project.get_agent("sprint-planner")
        assert agent.model == "opus"

    def test_model_default_is_sonnet(self, project):
        agent = project.get_agent("programmer")
        assert agent.model == "sonnet"

    def test_definition_returns_agent_md_content(self, project):
        agent = project.get_agent("programmer")
        definition = agent.definition
        assert isinstance(definition, str)
        assert len(definition) > 0
        # agent.md should mention the agent's role
        assert "programmer" in definition.lower() or "code" in definition.lower()

    def test_contract_returns_dict(self, project):
        agent = project.get_agent("programmer")
        contract = agent.contract
        assert isinstance(contract, dict)
        assert "name" in contract

    def test_allowed_tools_from_contract(self, project):
        agent = project.get_agent("programmer")
        tools = agent.allowed_tools
        assert isinstance(tools, list)
        assert "Read" in tools
        assert "Write" in tools

    def test_delegates_to_from_contract(self, project):
        agent = project.get_agent("team-lead")
        delegates = agent.delegates_to
        assert isinstance(delegates, list)
        assert len(delegates) > 0
        agent_names = [d["agent"] for d in delegates]
        assert "sprint-planner" in agent_names
        assert "programmer" in agent_names

    def test_delegates_to_empty_for_task_worker(self, project):
        agent = project.get_agent("programmer")
        delegates = agent.delegates_to
        assert delegates == []

    def test_delegates_to_empty_for_sprint_planner(self, project):
        agent = project.get_agent("sprint-planner")
        delegates = agent.delegates_to
        assert delegates == []

    def test_has_dispatch_template_true(self, project):
        agent = project.get_agent("programmer")
        assert agent.has_dispatch_template is True

    def test_has_dispatch_template_false(self, project):
        agent = project.get_agent("team-lead")
        assert agent.has_dispatch_template is False


# ---------------------------------------------------------------------------
# Subclass tests
# ---------------------------------------------------------------------------


class TestSubclasses:
    """Test agent tier values from contract.yaml."""

    def test_main_controller_tier_is_0(self, project):
        agent = project.get_agent("team-lead")
        assert isinstance(agent, Agent)
        assert agent.tier == 0

    def test_domain_controller_tier_is_1(self, project):
        agent = project.get_agent("sprint-planner")
        assert isinstance(agent, Agent)
        assert agent.tier == 1

    def test_task_worker_tier_is_2(self, project):
        agent = project.get_agent("programmer")
        assert isinstance(agent, Agent)
        assert agent.tier == 2

    def test_all_agents_have_valid_tiers(self, project):
        for agent in project.list_agents():
            assert agent.tier in {0, 1, 2}, f"{agent.name} has unexpected tier {agent.tier}"


# ---------------------------------------------------------------------------
# Project.get_agent and Project.list_agents
# ---------------------------------------------------------------------------


class TestProjectAgentManagement:
    """Test Project.get_agent and Project.list_agents."""

    def test_get_agent_returns_agent(self, project):
        agent = project.get_agent("programmer")
        assert isinstance(agent, Agent)

    def test_get_agent_team_lead_is_agent(self, project):
        agent = project.get_agent("team-lead")
        assert isinstance(agent, Agent)
        assert agent.tier == 0

    def test_get_agent_sprint_planner_is_agent(self, project):
        agent = project.get_agent("sprint-planner")
        assert isinstance(agent, Agent)
        assert agent.tier == 1

    def test_get_agent_architect_raises_value_error(self, project):
        """architect is in old/ and must not be accessible via get_agent."""
        with pytest.raises(ValueError, match="architect"):
            project.get_agent("architect")

    def test_get_agent_raises_on_unknown(self, project):
        with pytest.raises(ValueError, match="No agent found"):
            project.get_agent("nonexistent-agent")

    def test_list_agents_returns_all(self, project):
        agents = project.list_agents()
        assert isinstance(agents, list)
        assert len(agents) == 3
        names = {a.name for a in agents}
        assert "team-lead" in names
        assert "sprint-planner" in names
        assert "programmer" in names
        # Non-core agents are in old/ and not returned by list_agents
        assert "architect" not in names

    def test_list_agents_includes_all_tiers(self, project):
        agents = project.list_agents()
        tiers = {a.tier for a in agents}
        assert tiers == {0, 1, 2}

    def test_list_agents_all_are_agent_instances(self, project):
        agents = project.list_agents()
        for agent in agents:
            assert isinstance(agent, Agent)


# ---------------------------------------------------------------------------
# Agent.render_prompt
# ---------------------------------------------------------------------------


class TestRenderPrompt:
    """Test Agent.render_prompt with real templates."""

    def test_render_sprint_planner_template(self, project):
        agent = project.get_agent("sprint-planner")
        rendered = agent.render_prompt(
            sprint_id="001",
            sprint_directory="/tmp/test",
            todo_ids=["T-001"],
            goals="Test goals",
            mode="detail",
        )
        assert "sprint-planner" in rendered
        assert "001" in rendered

    def test_render_programmer_template(self, project):
        agent = project.get_agent("programmer")
        rendered = agent.render_prompt(
            ticket_path="t.md",
            ticket_plan_path="tp.md",
            scope_directory="/tmp/test",
            sprint_name="test",
            ticket_id="001",
        )
        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_raises_for_agent_without_template(self, project):
        agent = project.get_agent("team-lead")
        with pytest.raises(ValueError, match="No dispatch template"):
            agent.render_prompt()


