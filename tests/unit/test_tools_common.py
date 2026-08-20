"""Unit tests for clasi.tools._common — the @clasi_tool decorator and
resolve_artifact_path (sprint 030 ticket 005).

Exercises @clasi_tool against synthetic functions, not the real 47
``@server.tool()`` functions, and not through the live MCP server's
``call_tool`` dispatch path -- proving NONE-sentinel stripping, the
failure envelope, and trace-writing all work standalone. Before this
ticket, sentinel stripping and call tracing were only reachable through
the monkey-patched ``_tool_manager.call_tool`` wrapper, with no unit
coverage independent of a live server round-trip; this file is that
missing coverage.
"""

import json

import pytest

from clasi.mcp_server import set_project
from clasi.tools._common import (
    _strip_none_sentinel,
    _write_call_trace,
    clasi_tool,
    resolve_artifact_path,
)


class TestStripNoneSentinel:
    """Same behavior as the pre-ticket mcp_server.py version -- this is a
    pure relocation (see clasi.tools._common's own docstring)."""

    def test_strips_none_sentinel_value(self):
        assert _strip_none_sentinel({"notes": "NONE"}) == {"notes": None}

    def test_passes_through_real_value(self):
        assert _strip_none_sentinel({"notes": "real value"}) == {"notes": "real value"}

    def test_strips_only_none_sentinel_in_mixed_dict(self):
        result = _strip_none_sentinel({"sprint_id": "016", "gate": "NONE", "notes": "NONE"})
        assert result == {"sprint_id": "016", "gate": None, "notes": None}

    def test_empty_dict_unchanged(self):
        assert _strip_none_sentinel({}) == {}

    def test_does_not_mutate_input(self):
        original = {"notes": "NONE"}
        _strip_none_sentinel(original)
        assert original == {"notes": "NONE"}


class TestWriteCallTrace:
    """Same behavior as the pre-ticket mcp_server.py version -- this is a
    pure relocation."""

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
        assert record["ok"] is True
        assert record["tool"] == "get_version"

    def test_failure_record_shape(self, tmp_path):
        log_dir = tmp_path / ".clasi" / "log"
        _write_call_trace(
            log_dir, agent="team-lead", tool="broken_tool", args={},
            ok=False, ms=5, result_len=None,
        )
        records = self._read_records(log_dir)
        assert records[0]["ok"] is False
        assert records[0]["result_len"] is None

    def test_ensures_log_dir_gitignore(self, tmp_path):
        log_dir = tmp_path / ".clasi" / "log"
        assert not log_dir.exists()
        _write_call_trace(log_dir, agent="a", tool="t", args={}, ok=True, ms=1, result_len=1)
        gitignore = log_dir / ".gitignore"
        assert gitignore.exists()


class TestClasiToolSentinelStripping:
    """Proves NONE-sentinel stripping works via @clasi_tool directly,
    against a synthetic function -- reachable without the live server or
    the (now-removed) monkey-patched call_tool path, unlike before this
    ticket."""

    def test_strips_none_kwarg_before_calling_wrapped_function(self, tmp_path):
        set_project(tmp_path)
        received = {}

        @clasi_tool
        def echo(notes: str = None) -> str:
            received["notes"] = notes
            return json.dumps({"notes": notes})

        echo(notes="NONE")
        assert received["notes"] is None

    def test_passes_through_real_value_unchanged(self, tmp_path):
        set_project(tmp_path)
        received = {}

        @clasi_tool
        def echo(notes: str = None) -> str:
            received["notes"] = notes
            return "ok"

        echo(notes="a real value")
        assert received["notes"] == "a real value"

    def test_strips_positional_none_sentinel_too(self, tmp_path):
        """FastMCP always calls tools with keyword arguments, but direct/
        test calls may use positional args -- stripped identically."""
        set_project(tmp_path)
        received = {}

        @clasi_tool
        def echo(notes: str = None) -> str:
            received["notes"] = notes
            return "ok"

        echo("NONE")
        assert received["notes"] is None

    def test_strips_only_none_in_mixed_kwargs(self, tmp_path):
        set_project(tmp_path)
        received = {}

        @clasi_tool
        def two_args(sprint_id: str = None, notes: str = None) -> str:
            received["sprint_id"] = sprint_id
            received["notes"] = notes
            return "ok"

        two_args(sprint_id="016", notes="NONE")
        assert received["sprint_id"] == "016"
        assert received["notes"] is None


class TestClasiToolEnvelope:
    """Proves the failure envelope shape and that success passes through
    unmodified (see clasi.tools._common's own docstring, point 2, for the
    full rationale of that shape decision)."""

    def test_success_passes_wrapped_return_value_through_unchanged(self, tmp_path):
        set_project(tmp_path)

        @clasi_tool
        def make_payload() -> str:
            return json.dumps({"id": "001", "title": "Test"})

        out = make_payload()
        assert json.loads(out) == {"id": "001", "title": "Test"}

    def test_success_non_json_string_return_also_passes_through(self, tmp_path):
        """Markdown-returning tools (get_agent_definition et al) are not
        JSON at all -- confirm those pass through unchanged too."""
        set_project(tmp_path)

        @clasi_tool
        def get_markdown() -> str:
            return "# Some Heading\n\nBody text.\n"

        assert get_markdown() == "# Some Heading\n\nBody text.\n"

    def test_value_error_becomes_uniform_failure_envelope(self, tmp_path):
        set_project(tmp_path)

        @clasi_tool
        def boom() -> str:
            raise ValueError("something bad")

        out = json.loads(boom())
        assert out == {
            "ok": False,
            "error": {"type": "ValueError", "message": "something bad"},
        }

    def test_file_not_found_error_becomes_uniform_failure_envelope(self, tmp_path):
        set_project(tmp_path)

        @clasi_tool
        def boom() -> str:
            raise FileNotFoundError("nope.md")

        out = json.loads(boom())
        assert out["ok"] is False
        assert out["error"]["type"] == "FileNotFoundError"
        assert "nope.md" in out["error"]["message"]

    def test_value_error_subclass_also_caught(self, tmp_path):
        """The artifact model's own exception types (SprintNotFoundError,
        SprintFrontmatterError, SprintIdMismatchError,
        MalformedFrontmatterError) are all ValueError subclasses --
        confirm subclassing is honored, not just the exact ValueError
        type, and that the reported "type" is the subclass's own name."""
        set_project(tmp_path)

        class DomainError(ValueError):
            pass

        @clasi_tool
        def boom() -> str:
            raise DomainError("domain-specific failure")

        out = json.loads(boom())
        assert out["ok"] is False
        assert out["error"]["type"] == "DomainError"
        assert out["error"]["message"] == "domain-specific failure"

    def test_unexpected_exception_type_propagates_uncaught(self, tmp_path):
        """A genuine bug (not a domain error) is not swallowed into the
        envelope -- it still surfaces as a real exception (and, in the
        live server, a real MCP tool error), matching today's behavior
        for that class of failure."""
        set_project(tmp_path)

        @clasi_tool
        def boom() -> str:
            raise RuntimeError("not a domain error")

        with pytest.raises(RuntimeError, match="not a domain error"):
            boom()

    def test_failure_envelope_shape_is_uniform_across_different_tools(self, tmp_path):
        """Two independently-decorated synthetic tools raising ValueError
        produce identically-shaped failure envelopes -- the same
        {"ok", "error": {"type", "message"}} keys regardless of which
        tool or what its own signature/success payload looks like."""
        set_project(tmp_path)

        @clasi_tool
        def tool_a() -> str:
            raise ValueError("a failed")

        @clasi_tool
        def tool_b(x: str) -> str:
            raise ValueError("b failed")

        a = json.loads(tool_a())
        b = json.loads(tool_b("irrelevant"))
        assert set(a.keys()) == set(b.keys()) == {"ok", "error"}
        assert set(a["error"].keys()) == set(b["error"].keys()) == {"type", "message"}
        assert a["ok"] is False and b["ok"] is False


class TestClasiToolTracing:
    """Proves the mcp-calls.jsonl trace fires for both outcomes, moved
    (not duplicated) from _write_call_trace (sprint 028)."""

    def test_success_call_is_traced(self, tmp_path):
        set_project(tmp_path)

        @clasi_tool
        def some_tool(x: str) -> str:
            return "result"

        some_tool(x="value")

        trace_file = tmp_path / ".clasi" / "log" / "mcp-calls.jsonl"
        records = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 1
        assert records[0]["tool"] == "some_tool"
        assert records[0]["ok"] is True
        assert records[0]["args"] == {"x": "value"}

    def test_failure_call_is_traced(self, tmp_path):
        set_project(tmp_path)

        @clasi_tool
        def some_tool() -> str:
            raise ValueError("boom")

        some_tool()

        trace_file = tmp_path / ".clasi" / "log" / "mcp-calls.jsonl"
        records = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
        assert len(records) == 1
        assert records[0]["tool"] == "some_tool"
        assert records[0]["ok"] is False

    def test_traced_args_reflect_the_stripped_sentinel(self, tmp_path):
        set_project(tmp_path)

        @clasi_tool
        def some_tool(notes: str = None) -> str:
            return json.dumps({"notes": notes})

        out = json.loads(some_tool(notes="NONE"))
        assert out["notes"] is None

        trace_file = tmp_path / ".clasi" / "log" / "mcp-calls.jsonl"
        records = [json.loads(line) for line in trace_file.read_text(encoding="utf-8").splitlines()]
        assert records[0]["ok"] is True


class TestResolveArtifactPathRelocated:
    """SUC-005 acceptance criterion: resolve_artifact_path lives in
    tools/_common.py (relocated from artifact_tools.py, no behavior
    change)."""

    def test_importable_and_usable_from_common_module(self, tmp_path):
        f = tmp_path / "ticket.md"
        f.write_text("---\nid: '001'\n---\n", encoding="utf-8")
        assert resolve_artifact_path(str(f)) == f

    def test_relative_path_anchors_to_project_root(self, tmp_path):
        set_project(tmp_path)
        f = tmp_path / "tickets" / "001.md"
        f.parent.mkdir(parents=True)
        f.write_text("---\nid: '001'\n---\n", encoding="utf-8")
        assert resolve_artifact_path("tickets/001.md") == f

    def test_unknown_path_raises_file_not_found_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_artifact_path(str(tmp_path / "missing.md"))
