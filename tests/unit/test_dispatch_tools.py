"""Tests for clasi.tools.dispatch_tools module."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.dispatch_tools import (
    _check_delegation_edge,
    _dispatch,
    _load_agent_system_prompt,
    _load_jinja2_template,
    dispatch_to_architect,
    dispatch_to_architecture_reviewer,
    dispatch_to_ad_hoc_executor,
    dispatch_to_code_monkey,
    dispatch_to_code_reviewer,
    dispatch_to_project_architect,
    dispatch_to_project_manager,
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
    dispatch_to_project_architect,
    dispatch_to_project_manager,
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
        assert len(ALL_DISPATCH_TOOLS) == 12


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
    from clasi.mcp_server import set_project
    set_project(tmp_path)


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
        "clasi.tools.dispatch_tools._load_jinja2_template",
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
            msg = MagicMock()
            msg.result = '{"status": "success", "summary": "done", "files_changed": []}'
            yield msg

        mock_sdk = _make_mock_sdk(tracking_query)

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                with patch(
                    "clasi.dispatch_log.log_dispatch",
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
        from clasi.contracts import load_contract as _orig_load

        def tracking_load_contract(agent_name):
            nonlocal loaded_agent
            loaded_agent = agent_name
            return _orig_load(agent_name)

        mock_sdk = _make_mock_sdk(_success_query())

        with patch.dict(sys.modules, {"claude_agent_sdk": mock_sdk}):
            with _default_template_patch():
                with patch(
                    "clasi.contracts.load_contract",
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
        from clasi.dispatch_log import update_dispatch_result as _orig_update

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
                    "clasi.dispatch_log.update_dispatch_result",
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
        from clasi.tools import artifact_tools
        assert not hasattr(artifact_tools, "dispatch_to_sprint_planner")

    def test_no_dispatch_to_sprint_executor(self):
        from clasi.tools import artifact_tools
        assert not hasattr(artifact_tools, "dispatch_to_sprint_executor")

    def test_no_dispatch_to_code_monkey(self):
        from clasi.tools import artifact_tools
        assert not hasattr(artifact_tools, "dispatch_to_code_monkey")

    def test_no_log_subagent_dispatch(self):
        from clasi.tools import artifact_tools
        assert not hasattr(artifact_tools, "log_subagent_dispatch")

    def test_no_update_dispatch_log(self):
        from clasi.tools import artifact_tools
        assert not hasattr(artifact_tools, "update_dispatch_log")

    def test_no_load_jinja2_template(self):
        from clasi.tools import artifact_tools
        assert not hasattr(artifact_tools, "_load_jinja2_template")


class TestSprintPlannerModeParameter:
    """Tests for the two-phase sprint planning mode parameter."""

    def test_dispatch_to_sprint_planner_accepts_mode_parameter(self):
        """dispatch_to_sprint_planner has a mode parameter with default 'detail'."""
        import inspect
        sig = inspect.signature(dispatch_to_sprint_planner)
        assert "mode" in sig.parameters
        assert sig.parameters["mode"].default == "detail"

    def test_sprint_planner_mode_values(self):
        """The mode parameter accepts 'roadmap' and 'detail'."""
        import inspect
        sig = inspect.signature(dispatch_to_sprint_planner)
        # Just verify the parameter exists and has a string default
        param = sig.parameters["mode"]
        assert isinstance(param.default, str)
        assert param.default in ("roadmap", "detail")

    def test_mode_passed_through_template_rendering(self):
        """Verify mode is available in the Jinja2 template context."""
        template = _load_jinja2_template("sprint-planner")
        for mode_val in ("roadmap", "detail"):
            rendered = template.render(
                sprint_id="001",
                sprint_directory="/tmp/test",
                todo_ids=["T-001"],
                goals="Test goals",
                mode=mode_val,
            )
            assert mode_val in rendered, (
                f"Mode '{mode_val}' should appear in rendered template"
            )

    def test_roadmap_template_excludes_detail_artifacts(self):
        """Roadmap mode template should not mention ticket creation."""
        template = _load_jinja2_template("sprint-planner")
        rendered = template.render(
            sprint_id="001",
            sprint_directory="/tmp/test",
            todo_ids=["T-001"],
            goals="Test goals",
            mode="roadmap",
        )
        assert "Roadmap Mode" in rendered
        assert "tickets/" not in rendered
        assert "usecases.md" not in rendered.split("What NOT to produce")[0] or \
            "No `usecases.md`" in rendered

    def test_detail_template_includes_full_artifacts(self):
        """Detail mode template should include full artifact requirements."""
        template = _load_jinja2_template("sprint-planner")
        rendered = template.render(
            sprint_id="001",
            sprint_directory="/tmp/test",
            todo_ids=["T-001"],
            goals="Test goals",
            mode="detail",
        )
        assert "Detail Mode" in rendered
        assert "usecases.md" in rendered
        assert "architecture-update.md" in rendered

    def test_template_says_no_branch_creation(self):
        """Both modes should say no branch creation during planning."""
        template = _load_jinja2_template("sprint-planner")
        for mode_val in ("roadmap", "detail"):
            rendered = template.render(
                sprint_id="001",
                sprint_directory="/tmp/test",
                todo_ids=["T-001"],
                goals="Test goals",
                mode=mode_val,
            )
            assert "Do NOT create a git branch" in rendered


class TestSprintPlannerContractModes:
    """Tests for mode-specific outputs and returns in the sprint-planner contract."""

    def test_contract_has_mode_specific_outputs(self):
        from clasi.contracts import load_contract
        contract = load_contract("sprint-planner")
        outputs = contract["outputs"]
        assert "roadmap" in outputs, "Contract should have roadmap outputs"
        assert "detail" in outputs, "Contract should have detail outputs"

    def test_roadmap_outputs_only_sprint_md(self):
        from clasi.contracts import load_contract
        contract = load_contract("sprint-planner")
        roadmap_required = contract["outputs"]["roadmap"]["required"]
        paths = [o["path"] for o in roadmap_required]
        assert "sprint.md" in paths
        assert len(paths) == 1, "Roadmap should only require sprint.md"

    def test_detail_outputs_include_full_artifacts(self):
        from clasi.contracts import load_contract
        contract = load_contract("sprint-planner")
        detail_required = contract["outputs"]["detail"]["required"]
        paths = [o["path"] for o in detail_required]
        assert "sprint.md" in paths
        assert "usecases.md" in paths
        assert "architecture-update.md" in paths
        assert "tickets/*.md" in paths

    def test_contract_has_mode_specific_returns(self):
        from clasi.contracts import load_contract
        contract = load_contract("sprint-planner")
        returns = contract["returns"]
        assert "roadmap" in returns, "Contract should have roadmap return schema"
        assert "detail" in returns, "Contract should have detail return schema"

    def test_roadmap_return_schema(self):
        from clasi.contracts import load_contract
        contract = load_contract("sprint-planner")
        roadmap_returns = contract["returns"]["roadmap"]
        assert "sprint_file" in roadmap_returns["required"]
        assert "status" in roadmap_returns["required"]

    def test_detail_return_schema(self):
        from clasi.contracts import load_contract
        contract = load_contract("sprint-planner")
        detail_returns = contract["returns"]["detail"]
        assert "files_created" in detail_returns["required"]
        assert "ticket_ids" in detail_returns["required"]

    def test_validate_return_uses_roadmap_schema(self, tmp_path):
        """validate_return with mode='roadmap' uses roadmap return schema."""
        from clasi.contracts import load_contract, validate_return
        contract = load_contract("sprint-planner")

        # Create sprint.md in tmp_path
        (tmp_path / "sprint.md").write_text("---\nstatus: roadmap\n---\n# Test")

        result_text = json.dumps({
            "status": "success",
            "summary": "Planned sprint",
            "sprint_file": "sprint.md",
        })
        validation = validate_return(contract, "roadmap", result_text, str(tmp_path))
        assert validation["status"] == "valid"

    def test_validate_return_uses_detail_schema(self, tmp_path):
        """validate_return with mode='detail' uses detail return schema."""
        from clasi.contracts import load_contract, validate_return
        contract = load_contract("sprint-planner")

        # Create required files
        (tmp_path / "sprint.md").write_text("---\nstatus: planning_docs\n---\n# Test")
        (tmp_path / "usecases.md").write_text("# Use cases")
        (tmp_path / "architecture-update.md").write_text(
            "---\nstatus: draft\n---\n# Arch"
        )
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "001.md").write_text(
            "---\nstatus: pending\nid: '001'\n---\n# Ticket"
        )

        result_text = json.dumps({
            "status": "success",
            "summary": "Full plan",
            "files_created": ["sprint.md", "usecases.md"],
            "ticket_ids": ["001"],
            "architecture_review": "passed",
        })
        validation = validate_return(contract, "detail", result_text, str(tmp_path))
        assert validation["status"] == "valid"

    def test_validate_return_roadmap_rejects_missing_field(self, tmp_path):
        """validate_return with mode='roadmap' rejects result missing sprint_file."""
        from clasi.contracts import load_contract, validate_return
        contract = load_contract("sprint-planner")

        (tmp_path / "sprint.md").write_text("---\nstatus: roadmap\n---\n# Test")

        result_text = json.dumps({
            "status": "success",
            "summary": "Planned sprint",
            # missing sprint_file
        })
        validation = validate_return(contract, "roadmap", result_text, str(tmp_path))
        assert validation["status"] == "invalid"
        assert any("sprint_file" in e for e in validation["errors"])

    def test_validate_return_detail_reports_missing_files(self, tmp_path):
        """validate_return with mode='detail' reports missing output files."""
        from clasi.contracts import load_contract, validate_return
        contract = load_contract("sprint-planner")

        # Only create sprint.md, not the others
        (tmp_path / "sprint.md").write_text("---\nstatus: planning_docs\n---\n# Test")

        result_text = json.dumps({
            "status": "success",
            "summary": "Full plan",
            "files_created": ["sprint.md"],
            "ticket_ids": ["001"],
        })
        validation = validate_return(contract, "detail", result_text, str(tmp_path))
        assert validation["status"] == "invalid"
        assert len(validation["missing_files"]) > 0


class TestCheckDelegationEdge:
    """Tests for the _check_delegation_edge helper."""

    def test_no_warning_when_caller_is_allowed(self, caplog):
        """No warning is emitted when CLASI_AGENT_NAME is in allowed_callers."""
        with patch.dict(os.environ, {"CLASI_AGENT_NAME": "sprint-executor"}):
            with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
                _check_delegation_edge(
                    "dispatch_to_code_monkey",
                    frozenset({"sprint-executor", "ad-hoc-executor"}),
                )
        assert "DELEGATION VIOLATION" not in caplog.text

    def test_warning_emitted_when_caller_not_allowed(self, caplog):
        """A WARNING is emitted when CLASI_AGENT_NAME is not in allowed_callers."""
        with patch.dict(os.environ, {"CLASI_AGENT_NAME": "team-lead"}):
            with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
                _check_delegation_edge(
                    "dispatch_to_code_monkey",
                    frozenset({"sprint-executor", "ad-hoc-executor"}),
                )
        assert "DELEGATION VIOLATION" in caplog.text
        assert "team-lead" in caplog.text
        assert "dispatch_to_code_monkey" in caplog.text

    def test_default_caller_is_team_lead_when_env_unset(self, caplog, monkeypatch):
        """When CLASI_AGENT_NAME is absent, caller defaults to 'team-lead'."""
        monkeypatch.delenv("CLASI_AGENT_NAME", raising=False)
        with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
            _check_delegation_edge(
                "dispatch_to_architect",
                frozenset({"sprint-planner"}),
            )
        assert "team-lead" in caplog.text
        assert "DELEGATION VIOLATION" in caplog.text

    def test_no_warning_when_env_unset_and_team_lead_allowed(
        self, caplog, monkeypatch
    ):
        """No warning when CLASI_AGENT_NAME absent and 'team-lead' is allowed."""
        monkeypatch.delenv("CLASI_AGENT_NAME", raising=False)
        with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
            _check_delegation_edge(
                "dispatch_to_sprint_executor",
                frozenset({"team-lead"}),
            )
        assert "DELEGATION VIOLATION" not in caplog.text

    @pytest.mark.parametrize(
        "tool_name,allowed_callers,env_caller,expect_violation",
        [
            # Tier-2 tools: team-lead should trigger violations
            (
                "dispatch_to_architect",
                frozenset({"sprint-planner"}),
                "team-lead",
                True,
            ),
            (
                "dispatch_to_architecture_reviewer",
                frozenset({"sprint-planner"}),
                "team-lead",
                True,
            ),
            (
                "dispatch_to_technical_lead",
                frozenset({"sprint-planner"}),
                "team-lead",
                True,
            ),
            (
                "dispatch_to_code_monkey",
                frozenset({"sprint-executor", "ad-hoc-executor"}),
                "team-lead",
                True,
            ),
            (
                "dispatch_to_code_reviewer",
                frozenset({"ad-hoc-executor"}),
                "team-lead",
                True,
            ),
            # Correct callers: no violation
            (
                "dispatch_to_architect",
                frozenset({"sprint-planner"}),
                "sprint-planner",
                False,
            ),
            (
                "dispatch_to_code_monkey",
                frozenset({"sprint-executor", "ad-hoc-executor"}),
                "sprint-executor",
                False,
            ),
            (
                "dispatch_to_code_reviewer",
                frozenset({"ad-hoc-executor"}),
                "ad-hoc-executor",
                False,
            ),
        ],
    )
    def test_delegation_edges_for_tier2_tools(
        self,
        caplog,
        tool_name,
        allowed_callers,
        env_caller,
        expect_violation,
    ):
        """Parametrised check: correct callers pass, team-lead triggers violation."""
        with patch.dict(os.environ, {"CLASI_AGENT_NAME": env_caller}):
            with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
                _check_delegation_edge(tool_name, allowed_callers)
        if expect_violation:
            assert "DELEGATION VIOLATION" in caplog.text
        else:
            assert "DELEGATION VIOLATION" not in caplog.text

    @pytest.mark.parametrize(
        "tool_name,allowed_callers,env_caller,expect_violation",
        [
            # Tier-1 tools: unauthorized callers should trigger violations
            (
                "dispatch_to_sprint_executor",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            (
                "dispatch_to_sprint_planner",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            (
                "dispatch_to_sprint_reviewer",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            (
                "dispatch_to_project_manager",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            (
                "dispatch_to_project_architect",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            (
                "dispatch_to_todo_worker",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            (
                "dispatch_to_ad_hoc_executor",
                frozenset({"team-lead"}),
                "sprint-executor",
                True,
            ),
            # Correct callers for tier-1 tools: no violation
            (
                "dispatch_to_sprint_executor",
                frozenset({"team-lead"}),
                "team-lead",
                False,
            ),
            (
                "dispatch_to_sprint_planner",
                frozenset({"team-lead"}),
                "team-lead",
                False,
            ),
            (
                "dispatch_to_sprint_reviewer",
                frozenset({"team-lead"}),
                "team-lead",
                False,
            ),
            (
                "dispatch_to_ad_hoc_executor",
                frozenset({"team-lead"}),
                "team-lead",
                False,
            ),
        ],
    )
    def test_delegation_edges_for_tier1_tools(
        self,
        caplog,
        tool_name,
        allowed_callers,
        env_caller,
        expect_violation,
    ):
        """Tier-1 tools: team-lead is correct caller; others trigger violation."""
        with patch.dict(os.environ, {"CLASI_AGENT_NAME": env_caller}):
            with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
                _check_delegation_edge(tool_name, allowed_callers)
        if expect_violation:
            assert "DELEGATION VIOLATION" in caplog.text
        else:
            assert "DELEGATION VIOLATION" not in caplog.text


class TestDispatchToolsCallDelegationCheck:
    """Verify each dispatch tool actually calls _check_delegation_edge."""

    def _make_mock_agent(self):
        """Create a mock agent with render_prompt and async dispatch."""
        from unittest.mock import AsyncMock
        mock_agent = MagicMock()
        mock_agent.render_prompt.return_value = "test prompt"
        mock_agent.dispatch = AsyncMock(return_value={
            "status": "success",
            "summary": "done",
            "log_path": "/tmp/log.json",
        })
        return mock_agent

    def _make_mock_project(self, mock_agent):
        """Create a mock project that returns the given mock agent."""
        mock_project = MagicMock()
        mock_project.root = Path("/tmp/test-project")
        mock_project.get_agent.return_value = mock_agent
        return mock_project

    @pytest.mark.parametrize(
        "tool_fn,tool_name,kwargs,authorized_caller,unauthorized_caller",
        [
            (
                dispatch_to_sprint_executor,
                "dispatch_to_sprint_executor",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                    "branch_name": "sprint-001",
                    "tickets": ["001-001"],
                },
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_sprint_planner,
                "dispatch_to_sprint_planner",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                    "todo_ids": ["T-001"],
                    "goals": "Test goals",
                },
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_sprint_reviewer,
                "dispatch_to_sprint_reviewer",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_project_manager,
                "dispatch_to_project_manager",
                {"mode": "initiation"},
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_project_architect,
                "dispatch_to_project_architect",
                {"todo_files": ["t.md"]},
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_todo_worker,
                "dispatch_to_todo_worker",
                {"todo_ids": ["T-001"], "action": "list"},
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_ad_hoc_executor,
                "dispatch_to_ad_hoc_executor",
                {
                    "task_description": "Fix bug",
                    "scope_directory": "/tmp/scope",
                },
                "team-lead",
                "sprint-executor",
            ),
            (
                dispatch_to_architect,
                "dispatch_to_architect",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "sprint-planner",
                "team-lead",
            ),
            (
                dispatch_to_architecture_reviewer,
                "dispatch_to_architecture_reviewer",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "sprint-planner",
                "team-lead",
            ),
            (
                dispatch_to_technical_lead,
                "dispatch_to_technical_lead",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "sprint-planner",
                "team-lead",
            ),
            (
                dispatch_to_code_monkey,
                "dispatch_to_code_monkey",
                {
                    "ticket_path": "t.md",
                    "ticket_plan_path": "tp.md",
                    "scope_directory": "/tmp/scope",
                    "sprint_name": "test",
                    "ticket_id": "001",
                },
                "sprint-executor",
                "team-lead",
            ),
            (
                dispatch_to_code_reviewer,
                "dispatch_to_code_reviewer",
                {
                    "file_paths": ["test.py"],
                    "review_scope": "Review tests",
                },
                "ad-hoc-executor",
                "team-lead",
            ),
        ],
    )
    def test_warning_logged_for_unauthorized_caller(
        self,
        caplog,
        tool_fn,
        tool_name,
        kwargs,
        authorized_caller,
        unauthorized_caller,
    ):
        """Each dispatch tool logs DELEGATION VIOLATION for unauthorized callers."""
        mock_agent = self._make_mock_agent()
        mock_project = self._make_mock_project(mock_agent)

        with patch("clasi.tools.dispatch_tools.get_project", return_value=mock_project):
            with patch.dict(os.environ, {"CLASI_AGENT_NAME": unauthorized_caller}):
                with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
                    asyncio.run(tool_fn(**kwargs))

        assert "DELEGATION VIOLATION" in caplog.text, (
            f"{tool_name}: expected DELEGATION VIOLATION when called by "
            f"'{unauthorized_caller}'"
        )
        assert unauthorized_caller in caplog.text
        assert tool_name in caplog.text

    @pytest.mark.parametrize(
        "tool_fn,tool_name,kwargs,authorized_caller",
        [
            (
                dispatch_to_sprint_executor,
                "dispatch_to_sprint_executor",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                    "branch_name": "sprint-001",
                    "tickets": ["001-001"],
                },
                "team-lead",
            ),
            (
                dispatch_to_sprint_planner,
                "dispatch_to_sprint_planner",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                    "todo_ids": ["T-001"],
                    "goals": "Test goals",
                },
                "team-lead",
            ),
            (
                dispatch_to_sprint_reviewer,
                "dispatch_to_sprint_reviewer",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "team-lead",
            ),
            (
                dispatch_to_project_manager,
                "dispatch_to_project_manager",
                {"mode": "initiation"},
                "team-lead",
            ),
            (
                dispatch_to_project_architect,
                "dispatch_to_project_architect",
                {"todo_files": ["t.md"]},
                "team-lead",
            ),
            (
                dispatch_to_todo_worker,
                "dispatch_to_todo_worker",
                {"todo_ids": ["T-001"], "action": "list"},
                "team-lead",
            ),
            (
                dispatch_to_ad_hoc_executor,
                "dispatch_to_ad_hoc_executor",
                {
                    "task_description": "Fix bug",
                    "scope_directory": "/tmp/scope",
                },
                "team-lead",
            ),
            (
                dispatch_to_architect,
                "dispatch_to_architect",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "sprint-planner",
            ),
            (
                dispatch_to_architecture_reviewer,
                "dispatch_to_architecture_reviewer",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "sprint-planner",
            ),
            (
                dispatch_to_technical_lead,
                "dispatch_to_technical_lead",
                {
                    "sprint_id": "001",
                    "sprint_directory": "/tmp/sprint",
                },
                "sprint-planner",
            ),
            (
                dispatch_to_code_monkey,
                "dispatch_to_code_monkey",
                {
                    "ticket_path": "t.md",
                    "ticket_plan_path": "tp.md",
                    "scope_directory": "/tmp/scope",
                    "sprint_name": "test",
                    "ticket_id": "001",
                },
                "sprint-executor",
            ),
            (
                dispatch_to_code_reviewer,
                "dispatch_to_code_reviewer",
                {
                    "file_paths": ["test.py"],
                    "review_scope": "Review tests",
                },
                "ad-hoc-executor",
            ),
        ],
    )
    def test_no_warning_for_authorized_caller(
        self,
        caplog,
        tool_fn,
        tool_name,
        kwargs,
        authorized_caller,
    ):
        """Each dispatch tool does NOT log a warning for authorized callers."""
        mock_agent = self._make_mock_agent()
        mock_project = self._make_mock_project(mock_agent)

        with patch("clasi.tools.dispatch_tools.get_project", return_value=mock_project):
            with patch.dict(os.environ, {"CLASI_AGENT_NAME": authorized_caller}):
                with caplog.at_level(logging.WARNING, logger="clasi.dispatch"):
                    asyncio.run(tool_fn(**kwargs))

        assert "DELEGATION VIOLATION" not in caplog.text, (
            f"{tool_name}: unexpected DELEGATION VIOLATION when called by "
            f"'{authorized_caller}'"
        )
