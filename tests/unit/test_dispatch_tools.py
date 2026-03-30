"""Tests for claude_agent_skills.dispatch_tools module."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_agent_skills.dispatch_tools import (
    _dispatch,
    _load_agent_system_prompt,
    _load_jinja2_template,
    dispatch_to_architect,
    dispatch_to_architecture_reviewer,
    dispatch_to_ad_hoc_executor,
    dispatch_to_code_monkey,
    dispatch_to_code_reviewer,
    dispatch_to_requirements_narrator,
    dispatch_to_sprint_executor,
    dispatch_to_sprint_planner,
    dispatch_to_sprint_reviewer,
    dispatch_to_technical_lead,
    dispatch_to_todo_worker,
)


ALL_DISPATCH_TOOLS = [
    dispatch_to_architect,
    dispatch_to_architecture_reviewer,
    dispatch_to_ad_hoc_executor,
    dispatch_to_code_monkey,
    dispatch_to_code_reviewer,
    dispatch_to_requirements_narrator,
    dispatch_to_sprint_executor,
    dispatch_to_sprint_planner,
    dispatch_to_sprint_reviewer,
    dispatch_to_technical_lead,
    dispatch_to_todo_worker,
]


class TestDispatchToolsExist:
    """Verify all 11 dispatch functions are importable."""

    def test_all_dispatch_tools_are_callable(self):
        for tool in ALL_DISPATCH_TOOLS:
            assert callable(tool), f"{tool.__name__} should be callable"

    def test_all_dispatch_tools_are_async(self):
        for tool in ALL_DISPATCH_TOOLS:
            assert asyncio.iscoroutinefunction(tool), (
                f"{tool.__name__} should be an async function"
            )

    def test_dispatch_tools_count(self):
        assert len(ALL_DISPATCH_TOOLS) == 11


class TestLoadJinja2Template:
    """Tests for the template loader."""

    def test_loads_known_template(self):
        template = _load_jinja2_template("sprint-planner")
        assert template is not None
        rendered = template.render(
            sprint_id="001",
            sprint_directory="/tmp/test",
            todo_ids=["T-001"],
            goals="Test goals",
        )
        assert "sprint-planner" in rendered

    def test_loads_code_monkey_template(self):
        template = _load_jinja2_template("code-monkey")
        assert template is not None

    def test_raises_on_unknown_agent(self):
        with pytest.raises(ValueError, match="No dispatch template"):
            _load_jinja2_template("nonexistent-agent")

    @pytest.mark.parametrize("agent_name", [
        "requirements-narrator",
        "todo-worker",
        "ad-hoc-executor",
        "sprint-reviewer",
        "architect",
        "architecture-reviewer",
        "code-reviewer",
        "technical-lead",
    ])
    def test_new_templates_exist(self, agent_name):
        """Verify dispatch templates were created for all agents."""
        template = _load_jinja2_template(agent_name)
        assert template is not None


class TestLoadAgentSystemPrompt:
    """Tests for the system prompt loader."""

    def test_loads_known_agent(self):
        prompt = _load_agent_system_prompt("code-monkey")
        assert "code-monkey" in prompt.lower() or "Code Monkey" in prompt

    def test_raises_on_unknown(self):
        with pytest.raises(ValueError, match="No agent.md"):
            _load_agent_system_prompt("nonexistent-agent")


@pytest.fixture(autouse=True)
def _chdir_to_tmp(tmp_path, monkeypatch):
    """Ensure every test runs with cwd set to tmp_path."""
    monkeypatch.chdir(tmp_path)


def _make_mock_sdk(query_func):
    """Create a mock SDK module with a given query function."""
    mock_sdk = MagicMock()
    mock_sdk.ClaudeAgentOptions = MagicMock
    mock_sdk.ResultMessage = type("ResultMessage", (), {})
    mock_sdk.query = query_func
    return mock_sdk


def _default_template_patch():
    """Return a patch that provides a simple mock template."""
    mock_template = MagicMock()
    mock_template.render.return_value = "test prompt"
    return patch(
        "claude_agent_skills.dispatch_tools._load_jinja2_template",
        return_value=mock_template,
    )


_CODE_MONKEY_PARAMS = {
    "ticket_path": "t.md",
    "ticket_plan_path": "tp.md",
    "scope_directory": "/tmp/test",
    "sprint_name": "test",
    "ticket_id": "001",
}


def _success_query():
    """An async generator that yields a successful result."""
    async def mock_query(**kwargs):
        msg = MagicMock()
        msg.result = json.dumps({
            "status": "success",
            "summary": "done",
            "files_changed": ["test.py"],
            "tests_passed": True,
        })
        yield msg
    return mock_query


class TestDispatchHelper:
    """Tests for the shared _dispatch helper using mocked SDK."""

    def test_pre_log_written_before_query(self, tmp_path):
        """Verify the pre-execution log is written before query() is called."""
        log_written = False
        query_called = False

        original_log_dispatch = None
        from claude_agent_skills.dispatch_log import log_dispatch as _orig_log

        def tracking_log_dispatch(**kwargs):
            nonlocal log_written
            log_written = True
            assert not query_called, "Log should be written before query()"
            return _orig_log(**kwargs)

        async def tracking_query(**kwargs):
            nonlocal query_called
            query_called = True
            assert log_written, "Query should not be called before log is written"
            msg = MagicMock()
            msg.result = '{"status": "success", "summary": "done", "files_changed": []}'
            yield msg

        mock_sdk = _make_mock_sdk(tracking_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                with patch(
                    "claude_agent_skills.dispatch_log.log_dispatch",
                    side_effect=tracking_log_dispatch,
                ):
                    result = asyncio.run(_dispatch(
                        parent="team-lead",
                        child="code-monkey",
                        template_params=_CODE_MONKEY_PARAMS,
                        scope=str(tmp_path),
                        sprint_name="test",
                        ticket_id="001",
                    ))

        assert log_written
        assert query_called

    def test_contract_loaded_for_correct_agent(self, tmp_path):
        """Verify the contract is loaded for the target agent."""
        loaded_agent = None
        from claude_agent_skills.contracts import load_contract as _orig_load

        def tracking_load_contract(agent_name):
            nonlocal loaded_agent
            loaded_agent = agent_name
            return _orig_load(agent_name)

        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                with patch(
                    "claude_agent_skills.contracts.load_contract",
                    side_effect=tracking_load_contract,
                ):
                    asyncio.run(_dispatch(
                        parent="team-lead",
                        child="code-monkey",
                        template_params=_CODE_MONKEY_PARAMS,
                        scope=str(tmp_path),
                    ))

        assert loaded_agent == "code-monkey"

    def test_sdk_import_error_returns_error_json(self, tmp_path):
        """When claude-agent-sdk is not installed, return error JSON."""
        import builtins
        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if name == "claude_agent_sdk":
                raise ImportError("No module named 'claude_agent_sdk'")
            return original_import(name, *args, **kwargs)

        with patch.dict(sys.modules, {"claude_agent_sdk": None}):
            with patch("builtins.__import__", side_effect=failing_import):
                with _default_template_patch():
                    result = asyncio.run(_dispatch(
                        parent="team-lead",
                        child="code-monkey",
                        template_params=_CODE_MONKEY_PARAMS,
                        scope=str(tmp_path),
                    ))

        data = json.loads(result)
        assert data["status"] == "error"
        assert "claude-agent-sdk" in data["message"]
        assert "log_path" in data

    def test_query_exception_returns_error_json(self, tmp_path):
        """When query() raises an exception, return structured error."""
        async def failing_query(**kwargs):
            raise RuntimeError("Agent crashed")
            yield  # pragma: no cover -- make it a generator

        mock_sdk = _make_mock_sdk(failing_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                result = asyncio.run(_dispatch(
                    parent="team-lead",
                    child="code-monkey",
                    template_params=_CODE_MONKEY_PARAMS,
                    scope=str(tmp_path),
                ))

        data = json.loads(result)
        assert data["status"] == "error"
        assert "Agent crashed" in data["message"]
        assert "log_path" in data

    def test_successful_dispatch_returns_structured_json(self, tmp_path):
        """Full successful dispatch returns status, result, log_path, validations."""
        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                result = asyncio.run(_dispatch(
                    parent="team-lead",
                    child="code-monkey",
                    template_params=_CODE_MONKEY_PARAMS,
                    scope=str(tmp_path),
                ))

        data = json.loads(result)
        assert "status" in data
        assert "log_path" in data

    def test_post_log_written_after_query(self, tmp_path):
        """Verify post-execution log is written after query() completes."""
        post_log_called = False
        from claude_agent_skills.dispatch_log import update_dispatch_result as _orig_update

        def tracking_update(log_path, result, files_modified=None, response=None):
            nonlocal post_log_called
            post_log_called = True
            _orig_update(
                log_path=log_path,
                result=result,
                files_modified=files_modified or [],
                response=response,
            )

        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                with patch(
                    "claude_agent_skills.dispatch_log.update_dispatch_result",
                    side_effect=tracking_update,
                ):
                    asyncio.run(_dispatch(
                        parent="team-lead",
                        child="code-monkey",
                        template_params=_CODE_MONKEY_PARAMS,
                        scope=str(tmp_path),
                    ))

        assert post_log_called


class TestOldDispatchFunctionsRemoved:
    """Verify old dispatch functions no longer exist in artifact_tools."""

    def test_no_dispatch_to_sprint_planner(self):
        from claude_agent_skills import artifact_tools
        assert not hasattr(artifact_tools, "dispatch_to_sprint_planner")

    def test_no_dispatch_to_sprint_executor(self):
        from claude_agent_skills import artifact_tools
        assert not hasattr(artifact_tools, "dispatch_to_sprint_executor")

    def test_no_dispatch_to_code_monkey(self):
        from claude_agent_skills import artifact_tools
        assert not hasattr(artifact_tools, "dispatch_to_code_monkey")

    def test_no_log_subagent_dispatch(self):
        from claude_agent_skills import artifact_tools
        assert not hasattr(artifact_tools, "log_subagent_dispatch")

    def test_no_update_dispatch_log(self):
        from claude_agent_skills import artifact_tools
        assert not hasattr(artifact_tools, "update_dispatch_log")

    def test_no_load_jinja2_template(self):
        from claude_agent_skills import artifact_tools
        assert not hasattr(artifact_tools, "_load_jinja2_template")
