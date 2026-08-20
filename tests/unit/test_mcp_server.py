"""Tests for clasi.mcp_server module."""

import asyncio
import json
import logging
import re

import pytest
from mcp.server.fastmcp import FastMCP

from clasi.mcp_server import (
    server,
    content_path,
    _strip_none_sentinel,
    _build_logged_call_tool,
    _write_call_trace,
)

# Trigger lazy tool registration (normally done by run_server)
import clasi.tools.process_tools  # noqa: F401
import clasi.tools.artifact_tools  # noqa: F401
import clasi.tools.design_tools  # noqa: F401


class TestContentPath:
    def test_resolves_agents_directory(self):
        assert content_path("plugin", "agents").is_dir()

    def test_resolves_skills_directory(self):
        assert content_path("plugin", "skills").is_dir()

    def test_resolves_instructions_directory(self):
        assert content_path("plugin", "instructions").is_dir()

    def test_resolves_nested_path(self):
        assert content_path("plugin", "instructions", "languages").is_dir()

    def test_resolves_specific_file(self):
        # Agent files are now in the flat hierarchy: plugin/agents/team-lead/agent.md
        assert content_path("plugin", "agents", "team-lead", "agent.md").is_file()

    def test_resolves_rules_directory(self):
        assert content_path("plugin", "rules").is_dir()

    def test_tool_call_empty_args_rule_exists(self):
        rule = content_path("plugin", "rules", "tool-call-empty-args.md")
        assert rule.is_file()
        content = rule.read_text(encoding="utf-8")
        assert 'paths: ["**"]' in content
        assert "NONE" in content


class TestServer:
    def test_server_instance_exists(self):
        assert server is not None

    def test_server_is_fastmcp(self):
        assert isinstance(server, FastMCP)

    def test_server_name(self):
        assert server.name == "clasi"


class TestToolRegistration:
    """Verify all expected MCP tools are registered on the server."""

    EXPECTED_PROCESS_TOOLS = {
        "get_use_case_coverage",
        "get_version",
        "get_status",
        "list_agents",
        "list_skills",
        "list_instructions",
        "get_agent_definition",
        "get_skill_definition",
        "get_instruction",
        "list_language_instructions",
        "get_language_instruction",
        "get_activity_guide",
    }

    EXPECTED_ARTIFACT_TOOLS = {
        "create_sprint",
        "detail_sprint",
        "seed_sprint_design_overlay",
        "insert_sprint",
        "create_ticket",
        "list_sprints",
        "list_tickets",
        "get_sprint_status",
        "update_ticket_status",
        "move_ticket_to_done",
        "reopen_ticket",
        "throw_ticket_exception",
        "close_sprint",
        "clear_sprint_recovery",
        "get_sprint_phase",
        "advance_sprint_phase",
        "record_gate_result",
        "acquire_execution_lock",
        "release_execution_lock",
        "list_issues",
        "move_issue_to_done",
        "split_issue",
        "link_sprint_issues",
        "add_issue_ref",
        "create_github_issue",
        "close_github_issue",
        "list_github_issues",
        "read_artifact_frontmatter",
        "write_artifact_frontmatter",
        "tag_version",
        "review_sprint_pre_execution",
        "review_sprint_pre_close",
        "review_sprint_post_close",
        "reconcile_worktrees",
    }

    EXPECTED_DISPATCH_TOOLS: set[str] = set()

    EXPECTED_DESIGN_TOOLS = {
        "validate_design",
    }

    EXPECTED_ALL = EXPECTED_PROCESS_TOOLS | EXPECTED_ARTIFACT_TOOLS | EXPECTED_DESIGN_TOOLS

    def _registered_tool_names(self) -> set[str]:
        """Get the set of tool names registered on the server."""
        # FastMCP stores tools in _tool_manager._tools dict
        tools = server._tool_manager._tools
        return set(tools.keys())

    def test_all_expected_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_ALL - registered
        assert not missing, f"Missing tools: {missing}"

    def test_no_unexpected_tools(self):
        registered = self._registered_tool_names()
        unexpected = registered - self.EXPECTED_ALL
        assert not unexpected, f"Unexpected tools: {unexpected}"

    def test_tool_count(self):
        registered = self._registered_tool_names()
        assert len(registered) == 47

    def test_process_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_PROCESS_TOOLS - registered
        assert not missing, f"Missing process tools: {missing}"

    def test_artifact_tools_registered(self):
        registered = self._registered_tool_names()
        missing = self.EXPECTED_ARTIFACT_TOOLS - registered
        assert not missing, f"Missing artifact tools: {missing}"


class TestNoneSentinelStripping:
    """Unit tests for _strip_none_sentinel — the NONE-sentinel stripping helper."""

    def test_strips_none_sentinel_value(self):
        result = _strip_none_sentinel({"notes": "NONE"})
        assert result == {"notes": None}

    def test_passes_through_real_value(self):
        result = _strip_none_sentinel({"notes": "real value"})
        assert result == {"notes": "real value"}

    def test_strips_only_none_sentinel_in_mixed_dict(self):
        result = _strip_none_sentinel({"sprint_id": "016", "gate": "NONE", "notes": "NONE"})
        assert result == {"sprint_id": "016", "gate": None, "notes": None}

    def test_empty_dict_unchanged(self):
        result = _strip_none_sentinel({})
        assert result == {}

    def test_does_not_mutate_input(self):
        original = {"notes": "NONE"}
        _strip_none_sentinel(original)
        assert original == {"notes": "NONE"}


class TestWriteCallTrace:
    """Unit tests for `_write_call_trace` — the self-contained JSONL trace
    writer (ticket 028-003). Deliberately tested independent of the
    call_tool monkey-patch it is invoked from, since it is written to be
    liftable into a future `@clasi_tool` decorator (sprint 030) as-is.
    """

    def _read_records(self, log_dir):
        text = (log_dir / "mcp-calls.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def test_success_record_shape(self, tmp_path):
        log_dir = tmp_path / ".clasi" / "log"
        _write_call_trace(
            log_dir, agent="team-lead", tool="get_version", args={"a": "1"},
            ok=True, ms=42, result_len=17,
        )
        records = self._read_records(log_dir)
        assert len(records) == 1
        record = records[0]
        assert set(record.keys()) == {"ts", "agent", "tool", "args", "ok", "ms", "result_len"}
        assert record["agent"] == "team-lead"
        assert record["tool"] == "get_version"
        assert record["args"] == {"a": "1"}
        assert record["ok"] is True
        assert record["ms"] == 42
        assert record["result_len"] == 17
        # ISO 8601 UTC, matching _log_hook_event's %Y-%m-%dT%H:%M:%SZ format
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", record["ts"])

    def test_failure_record_shape(self, tmp_path):
        log_dir = tmp_path / ".clasi" / "log"
        _write_call_trace(
            log_dir, agent="team-lead", tool="broken_tool", args={},
            ok=False, ms=5, result_len=None,
        )
        records = self._read_records(log_dir)
        assert len(records) == 1
        record = records[0]
        assert record["ok"] is False
        assert record["tool"] == "broken_tool"
        assert record["result_len"] is None
        assert record["ms"] == 5

    def test_appends_one_line_per_call(self, tmp_path):
        log_dir = tmp_path / ".clasi" / "log"
        _write_call_trace(log_dir, agent="a", tool="t1", args={}, ok=True, ms=1, result_len=1)
        _write_call_trace(log_dir, agent="a", tool="t2", args={}, ok=False, ms=2, result_len=None)
        records = self._read_records(log_dir)
        assert len(records) == 2
        assert records[0]["tool"] == "t1"
        assert records[1]["tool"] == "t2"

    def test_ensures_log_dir_gitignore(self, tmp_path):
        """AC: .clasi/log/mcp-calls.jsonl must be covered by the existing
        log-dir gitignore mechanism. mcp_server.py's own log setup
        (Clasi._setup_logging) does not call _ensure_log_gitignore, so
        _write_call_trace must call it itself — verified here rather than
        assumed."""
        log_dir = tmp_path / ".clasi" / "log"
        assert not log_dir.exists()
        _write_call_trace(log_dir, agent="a", tool="t", args={}, ok=True, ms=1, result_len=1)
        gitignore = log_dir / ".gitignore"
        assert gitignore.exists()
        assert gitignore.read_text(encoding="utf-8") == "*\n!.gitignore\n"


class TestBuildLoggedCallTool:
    """Unit tests for `_build_logged_call_tool` — the call_tool wrapper
    factory (ticket 028-003). Built as a factory (rather than a closure
    inline in Clasi.run()) specifically so it can be exercised here against
    a fake `original_call_tool` and a tmp_path log dir, without booting the
    real stdio server.
    """

    def test_success_appends_trace_and_logs_duration(self, tmp_path, caplog):
        log_dir = tmp_path / ".clasi" / "log"

        async def fake_original(name, arguments, **kwargs):
            return "ok-result"

        wrapped = _build_logged_call_tool(fake_original, "test-agent", log_dir)

        with caplog.at_level(logging.INFO, logger="clasi.mcp"):
            result = asyncio.run(wrapped("some_tool", {"x": "1"}))

        assert result == "ok-result"

        records = [json.loads(line) for line in (log_dir / "mcp-calls.jsonl").read_text(
            encoding="utf-8").splitlines()]
        assert len(records) == 1
        record = records[0]
        assert record["ok"] is True
        assert record["tool"] == "some_tool"
        assert record["agent"] == "test-agent"
        assert isinstance(record["ms"], int)
        assert record["ms"] >= 0
        assert record["result_len"] == len("ok-result")

        # Human log line carries the duration too.
        assert re.search(r"OK some_tool \(\d+ms\) ->", caplog.text)

    def test_failure_propagates_and_records_trace(self, tmp_path, caplog):
        log_dir = tmp_path / ".clasi" / "log"

        async def fake_original(name, arguments, **kwargs):
            raise ValueError("boom")

        wrapped = _build_logged_call_tool(fake_original, "test-agent", log_dir)

        with caplog.at_level(logging.INFO, logger="clasi.mcp"):
            with pytest.raises(ValueError, match="boom"):
                asyncio.run(wrapped("broken_tool", {}))

        records = [json.loads(line) for line in (log_dir / "mcp-calls.jsonl").read_text(
            encoding="utf-8").splitlines()]
        assert len(records) == 1
        record = records[0]
        assert record["ok"] is False
        assert record["tool"] == "broken_tool"
        assert record["result_len"] is None
        assert isinstance(record["ms"], int)
        assert record["ms"] >= 0

        # Exception still propagates unchanged (asserted above via pytest.raises);
        # human log line carries the duration on the FAIL path too.
        assert re.search(r"FAIL broken_tool \(\d+ms\) ->", caplog.text)
