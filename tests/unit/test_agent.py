"""Tests for clasi.agent module."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clasi.agent import Agent, DomainController, MainController, TaskWorker
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
        agent = project.get_agent("code-monkey")
        assert agent.name == "code-monkey"

    def test_tier_from_directory_position(self, project):
        agent = project.get_agent("code-monkey")
        # code-monkey is in task-workers/ -> tier 2
        assert agent.tier == 2

    def test_model_from_contract(self, project):
        agent = project.get_agent("sprint-planner")
        assert agent.model == "opus"

    def test_model_default_is_sonnet(self, project):
        agent = project.get_agent("code-monkey")
        assert agent.model == "sonnet"

    def test_definition_returns_agent_md_content(self, project):
        agent = project.get_agent("code-monkey")
        definition = agent.definition
        assert isinstance(definition, str)
        assert len(definition) > 0
        # agent.md should mention the agent's role
        assert "code" in definition.lower() or "monkey" in definition.lower()

    def test_contract_returns_dict(self, project):
        agent = project.get_agent("code-monkey")
        contract = agent.contract
        assert isinstance(contract, dict)
        assert "name" in contract
        assert contract["name"] == "code-monkey"

    def test_allowed_tools_from_contract(self, project):
        agent = project.get_agent("code-monkey")
        tools = agent.allowed_tools
        assert isinstance(tools, list)
        assert "Read" in tools
        assert "Write" in tools

    def test_delegates_to_from_contract(self, project):
        agent = project.get_agent("sprint-planner")
        delegates = agent.delegates_to
        assert isinstance(delegates, list)
        assert len(delegates) > 0
        agent_names = [d["agent"] for d in delegates]
        assert "architect" in agent_names

    def test_delegates_to_empty_for_task_worker(self, project):
        agent = project.get_agent("code-monkey")
        delegates = agent.delegates_to
        assert delegates == []

    def test_has_dispatch_template_true(self, project):
        agent = project.get_agent("code-monkey")
        assert agent.has_dispatch_template is True

    def test_has_dispatch_template_false(self, project):
        agent = project.get_agent("team-lead")
        assert agent.has_dispatch_template is False


# ---------------------------------------------------------------------------
# Subclass tests
# ---------------------------------------------------------------------------


class TestSubclasses:
    """Test MainController, DomainController, TaskWorker subclasses."""

    def test_main_controller_tier_is_0(self, project):
        agent = project.get_agent("team-lead")
        assert isinstance(agent, MainController)
        assert agent.tier == 0

    def test_domain_controller_tier_is_1(self, project):
        agent = project.get_agent("sprint-planner")
        assert isinstance(agent, DomainController)
        assert agent.tier == 1

    def test_task_worker_tier_is_2(self, project):
        agent = project.get_agent("code-monkey")
        assert isinstance(agent, TaskWorker)
        assert agent.tier == 2

    def test_all_domain_controllers_are_tier_1(self, project):
        for agent in project.list_agents():
            if isinstance(agent, DomainController):
                assert agent.tier == 1, f"{agent.name} should be tier 1"

    def test_all_task_workers_are_tier_2(self, project):
        for agent in project.list_agents():
            if isinstance(agent, TaskWorker):
                assert agent.tier == 2, f"{agent.name} should be tier 2"


# ---------------------------------------------------------------------------
# Project.get_agent and Project.list_agents
# ---------------------------------------------------------------------------


class TestProjectAgentManagement:
    """Test Project.get_agent and Project.list_agents."""

    def test_get_agent_returns_agent(self, project):
        agent = project.get_agent("code-monkey")
        assert isinstance(agent, Agent)

    def test_get_agent_returns_correct_subclass_main_controller(self, project):
        agent = project.get_agent("team-lead")
        assert isinstance(agent, MainController)

    def test_get_agent_returns_correct_subclass_domain_controller(self, project):
        agent = project.get_agent("sprint-planner")
        assert isinstance(agent, DomainController)

    def test_get_agent_returns_correct_subclass_task_worker(self, project):
        agent = project.get_agent("architect")
        assert isinstance(agent, TaskWorker)

    def test_get_agent_raises_on_unknown(self, project):
        with pytest.raises(ValueError, match="No agent found"):
            project.get_agent("nonexistent-agent")

    def test_list_agents_returns_all(self, project):
        agents = project.list_agents()
        assert isinstance(agents, list)
        assert len(agents) > 0
        names = {a.name for a in agents}
        assert "team-lead" in names
        assert "sprint-planner" in names
        assert "code-monkey" in names
        assert "architect" in names

    def test_list_agents_includes_all_tiers(self, project):
        agents = project.list_agents()
        tiers = {a.tier for a in agents}
        assert tiers == {0, 1, 2}

    def test_list_agents_has_correct_types(self, project):
        agents = project.list_agents()
        for agent in agents:
            if agent.tier == 0:
                assert isinstance(agent, MainController)
            elif agent.tier == 1:
                assert isinstance(agent, DomainController)
            elif agent.tier == 2:
                assert isinstance(agent, TaskWorker)


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

    def test_render_code_monkey_template(self, project):
        agent = project.get_agent("code-monkey")
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


# ---------------------------------------------------------------------------
# Agent.dispatch with mocked query()
# ---------------------------------------------------------------------------


_ResultMessage = type("ResultMessage", (), {})


def _make_mock_sdk(query_func):
    """Create a mock SDK module with a given query function."""
    mock_sdk = MagicMock()
    mock_sdk.ClaudeAgentOptions = MagicMock
    mock_sdk.ResultMessage = _ResultMessage
    mock_sdk.query = query_func
    return mock_sdk


def _make_result_message(result_text: str):
    """Create a ResultMessage instance with the given result text."""
    msg = _ResultMessage()
    msg.result = result_text  # type: ignore[attr-defined]
    return msg


def _success_query():
    """An async generator that yields a successful result."""
    async def mock_query(**kwargs):
        yield _make_result_message(json.dumps({
            "status": "success",
            "summary": "done",
            "files_changed": ["test.py"],
            "tests_passed": True,
        }))
    return mock_query


class TestAgentDispatch:
    """Test Agent.dispatch with mocked query()."""

    def test_successful_dispatch_returns_dict(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")
        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert isinstance(result, dict)
        assert "status" in result
        assert "log_path" in result

    def test_dispatch_logs_before_query(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        log_written = False
        query_called = False

        from clasi.dispatch_log import log_dispatch as _orig_log

        def tracking_log_dispatch(**kwargs):
            nonlocal log_written
            log_written = True
            assert not query_called, "Log should be written before query()"
            return _orig_log(**kwargs)

        async def tracking_query(**kwargs):
            nonlocal query_called
            query_called = True
            assert log_written, "Query should not be called before log is written"
            yield _make_result_message(
                '{"status": "success", "summary": "done", "files_changed": []}'
            )

        mock_sdk = _make_mock_sdk(tracking_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with patch(
                "clasi.dispatch_log.log_dispatch",
                side_effect=tracking_log_dispatch,
            ):
                asyncio.run(agent.dispatch(
                    prompt="test prompt",
                    cwd=str(tmp_path),
                    parent="sprint-executor",
                    sprint_name="test",
                    ticket_id="001",
                ))

        assert log_written
        assert query_called

    def test_dispatch_uses_contract_from_agent(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")
        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        # Verify the contract was loaded (agent has cached it)
        assert agent._contract is not None
        assert agent._contract["name"] == "code-monkey"

    def test_dispatch_sdk_import_error(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        import builtins
        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "claude_agent_sdk":
                raise ImportError("No module named 'claude_agent_sdk'")
            return original_import(name, *args, **kwargs)

        with patch.dict(sys.modules, {"claude_agent_sdk": None}):
            with patch("builtins.__import__", side_effect=failing_import):
                result = asyncio.run(agent.dispatch(
                    prompt="test prompt",
                    cwd=str(tmp_path),
                    parent="sprint-executor",
                ))

        assert result["status"] == "error"
        assert "claude-agent-sdk" in result["message"]
        assert "log_path" in result

    def test_dispatch_query_exception(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        async def failing_query(**kwargs):
            raise RuntimeError("Agent crashed")
            yield  # pragma: no cover

        mock_sdk = _make_mock_sdk(failing_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert result["status"] == "error"
        assert result["fatal"] is True
        assert "Agent crashed" in result["message"]
        assert "log_path" in result

    def test_dispatch_validates_result(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")
        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert "validations" in result
        assert result["validations"]["result_json"] is not None

    def test_dispatch_with_mode_parameter(self, tmp_path):
        project = Project(tmp_path)
        agent = project.get_agent("sprint-planner")

        async def mock_query(**kwargs):
            yield _make_result_message(json.dumps({
                "status": "success",
                "summary": "Planned",
                "sprint_file": "sprint.md",
            }))

        # Create sprint.md for validation
        (tmp_path / "sprint.md").write_text("---\nstatus: roadmap\n---\n# Test")

        mock_sdk = _make_mock_sdk(mock_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="team-lead",
                mode="roadmap",
                sprint_name="test-sprint",
            ))

        assert result["status"] == "valid"

    def test_dispatch_uses_project_mcp_config(self, tmp_path):
        """Verify dispatch uses project.mcp_config_path for MCP servers."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        # Create .mcp.json so it exists
        mcp_json = tmp_path / ".mcp.json"
        mcp_json.write_text('{"mcpServers": {}}')

        captured_options = {}

        async def capturing_query(**kwargs):
            captured_options.update(kwargs)
            yield _make_result_message(json.dumps({
                "status": "success",
                "summary": "done",
                "files_changed": [],
                "tests_passed": True,
            }))

        mock_sdk = _make_mock_sdk(capturing_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        # The mcp_servers should be the path to .mcp.json
        options = captured_options.get("options")
        assert options is not None
        assert options.mcp_servers == str(mcp_json)

    def test_dispatch_post_log_written(self, tmp_path):
        """Verify post-execution log is written after query()."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        post_log_called = False
        from clasi.dispatch_log import update_dispatch_result as _orig

        def tracking_update(log_path, result, files_modified=None, response=None):
            nonlocal post_log_called
            post_log_called = True
            _orig(
                log_path=log_path,
                result=result,
                files_modified=files_modified or [],
                response=response,
            )

        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with patch(
                "clasi.dispatch_log.update_dispatch_result",
                side_effect=tracking_update,
            ):
                asyncio.run(agent.dispatch(
                    prompt="test prompt",
                    cwd=str(tmp_path),
                    parent="sprint-executor",
                ))

        assert post_log_called


# ---------------------------------------------------------------------------
# Agent._build_retry_prompt
# ---------------------------------------------------------------------------


class TestBuildRetryPrompt:
    """Test Agent._build_retry_prompt helper method."""

    def test_includes_original_prompt(self, project):
        agent = project.get_agent("code-monkey")
        validation = {
            "status": "error",
            "errors": ["No valid JSON found in agent result text"],
            "missing_files": [],
        }
        prompt = agent._build_retry_prompt("original prompt text", validation, None)
        assert "original prompt text" in prompt

    def test_includes_validation_errors(self, project):
        agent = project.get_agent("code-monkey")
        validation = {
            "status": "error",
            "errors": ["No valid JSON found in agent result text"],
            "missing_files": [],
        }
        prompt = agent._build_retry_prompt("do work", validation, None)
        assert "No valid JSON found" in prompt

    def test_includes_missing_files(self, project):
        agent = project.get_agent("code-monkey")
        validation = {
            "status": "invalid",
            "errors": [],
            "missing_files": ["docs/output.md"],
        }
        prompt = agent._build_retry_prompt("do work", validation, None)
        assert "docs/output.md" in prompt

    def test_includes_retry_section_header(self, project):
        agent = project.get_agent("code-monkey")
        validation = {
            "status": "error",
            "errors": ["some error"],
            "missing_files": [],
        }
        prompt = agent._build_retry_prompt("do work", validation, None)
        assert "RETRY" in prompt

    def test_includes_return_schema(self, project):
        agent = project.get_agent("code-monkey")
        validation = {
            "status": "error",
            "errors": ["No valid JSON found in agent result text"],
            "missing_files": [],
        }
        prompt = agent._build_retry_prompt("do work", validation, None)
        # Contract for code-monkey requires status, summary, files_changed, tests_passed
        assert "status" in prompt
        assert "summary" in prompt


# ---------------------------------------------------------------------------
# Agent.dispatch retry logic
# ---------------------------------------------------------------------------


class TestAgentDispatchRetry:
    """Test the retry logic in Agent.dispatch()."""

    def test_retry_on_no_json_then_success(self, tmp_path):
        """Dispatch retries when first response has no JSON, succeeds on retry."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        call_count = 0

        async def mock_query_prose_then_json(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call returns prose (no JSON)
                yield _make_result_message(
                    "I worked really hard and everything is done now!"
                )
            else:
                # Second call (retry) returns valid JSON
                yield _make_result_message(json.dumps({
                    "status": "success",
                    "summary": "done on retry",
                    "files_changed": ["test.py"],
                    "tests_passed": True,
                }))

        mock_sdk = _make_mock_sdk(mock_query_prose_then_json)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert call_count == 2, "query() should have been called twice"
        assert result["status"] == "valid"
        assert "done on retry" in result["result"]

    def test_retry_not_triggered_on_success(self, tmp_path):
        """When first response is valid, no retry is attempted."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        call_count = 0

        async def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            yield _make_result_message(json.dumps({
                "status": "success",
                "summary": "done first time",
                "files_changed": [],
                "tests_passed": True,
            }))

        mock_sdk = _make_mock_sdk(mock_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert call_count == 1, "query() should only have been called once"

    def test_retry_both_fail_returns_fatal(self, tmp_path):
        """When both original and retry fail validation, returns fatal error."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        async def mock_query_always_prose(**kwargs):
            yield _make_result_message(
                "Sorry I cannot provide a JSON response, here is prose instead."
            )

        mock_sdk = _make_mock_sdk(mock_query_always_prose)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert result["status"] == "error"
        assert result.get("fatal") is True
        assert "log_path" in result
        assert "instruction" in result

    def test_retry_prompt_sent_on_validation_failure(self, tmp_path):
        """The retry prompt includes validation error context."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        prompts_seen = []

        async def mock_query_capture_prompt(**kwargs):
            prompt_text = kwargs.get("prompt", "")
            prompts_seen.append(prompt_text)
            yield _make_result_message(
                "prose response with no JSON"
            )

        mock_sdk = _make_mock_sdk(mock_query_capture_prompt)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            asyncio.run(agent.dispatch(
                prompt="original dispatch prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert len(prompts_seen) == 2
        # Original prompt unchanged on first call
        assert prompts_seen[0] == "original dispatch prompt"
        # Retry prompt includes original + validation error info
        assert "original dispatch prompt" in prompts_seen[1]
        assert "RETRY" in prompts_seen[1]

    def test_retry_query_exception_falls_through(self, tmp_path):
        """If retry query raises exception, dispatch continues with original invalid result."""
        project = Project(tmp_path)
        agent = project.get_agent("code-monkey")

        call_count = 0

        async def mock_query_first_prose_then_raises(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield _make_result_message("prose with no json")
            else:
                raise RuntimeError("Retry query crashed")
                yield  # pragma: no cover

        mock_sdk = _make_mock_sdk(mock_query_first_prose_then_raises)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            result = asyncio.run(agent.dispatch(
                prompt="test prompt",
                cwd=str(tmp_path),
                parent="sprint-executor",
            ))

        assert call_count == 2
        # Should still return a result, not crash
        assert "status" in result
        assert "log_path" in result
