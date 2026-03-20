"""Tests for claude_agent_skills.dispatch_log module."""

import pytest
from pathlib import Path

from claude_agent_skills.dispatch_log import (
    _auto_context_documents,
    _log_dir,
    _next_sequence,
    log_dispatch,
    update_dispatch_result,
)
from claude_agent_skills.frontmatter import read_document


@pytest.fixture(autouse=True)
def _chdir_to_tmp(tmp_path, monkeypatch):
    """Ensure every test runs with cwd set to tmp_path."""
    monkeypatch.chdir(tmp_path)


class TestLogDir:
    def test_returns_log_path_relative_to_cwd(self, tmp_path):
        expected = tmp_path / "docs" / "clasi" / "log"
        assert _log_dir() == expected


class TestNextSequence:
    def test_returns_1_when_directory_missing(self, tmp_path):
        assert _next_sequence(tmp_path / "nonexistent", "ticket-001") == 1

    def test_returns_1_when_directory_empty(self, tmp_path):
        d = tmp_path / "logs"
        d.mkdir()
        assert _next_sequence(d, "sprint-planner") == 1

    def test_returns_next_after_existing(self, tmp_path):
        d = tmp_path / "logs"
        d.mkdir()
        (d / "sprint-planner-001.md").write_text("x")
        (d / "sprint-planner-002.md").write_text("x")
        assert _next_sequence(d, "sprint-planner") == 3

    def test_ignores_non_matching_files(self, tmp_path):
        d = tmp_path / "logs"
        d.mkdir()
        (d / "ticket-001-005.md").write_text("x")
        (d / "sprint-planner-001.md").write_text("x")
        assert _next_sequence(d, "sprint-planner") == 2

    def test_handles_gaps(self, tmp_path):
        d = tmp_path / "logs"
        d.mkdir()
        (d / "sprint-planner-001.md").write_text("x")
        (d / "sprint-planner-005.md").write_text("x")
        assert _next_sequence(d, "sprint-planner") == 6


class TestLogDispatch:
    def test_creates_file_with_frontmatter_and_prompt(self, tmp_path):
        path = log_dispatch(
            parent="sprint-executor",
            child="code-monkey",
            scope="claude_agent_skills/",
            prompt="Implement the widget.",
            sprint_name="001-my-sprint",
            ticket_id="001",
            template_used="dispatch-template.md",
        )
        assert path.exists()
        fm, body = read_document(path)
        assert fm["parent"] == "sprint-executor"
        assert fm["child"] == "code-monkey"
        assert fm["scope"] == "claude_agent_skills/"
        assert fm["sprint"] == "001-my-sprint"
        assert fm["ticket"] == "001"
        assert "timestamp" in fm
        assert "Implement the widget." in body

    def test_sprint_with_ticket_routing(self, tmp_path):
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Do work.",
            sprint_name="001-my-sprint",
            ticket_id="003",
        )
        expected_dir = tmp_path / "docs" / "clasi" / "log" / "sprints" / "001-my-sprint"
        assert path.parent == expected_dir
        assert path.name == "ticket-003-001.md"

    def test_sprint_without_ticket_routing(self, tmp_path):
        """Sprint-level dispatch uses child agent name as prefix."""
        path = log_dispatch(
            parent="mc",
            child="sp",
            scope="docs/",
            prompt="Plan the sprint.",
            sprint_name="002-next-sprint",
        )
        expected_dir = tmp_path / "docs" / "clasi" / "log" / "sprints" / "002-next-sprint"
        assert path.parent == expected_dir
        assert path.name == "sp-001.md"

    def test_sprint_without_ticket_uses_child_name(self, tmp_path):
        """Different child agents produce distinctly named log files."""
        p1 = log_dispatch(
            parent="sprint-planner",
            child="architect",
            scope="docs/",
            prompt="Design architecture.",
            sprint_name="003-sprint",
        )
        p2 = log_dispatch(
            parent="sprint-planner",
            child="architecture-reviewer",
            scope="docs/",
            prompt="Review architecture.",
            sprint_name="003-sprint",
        )
        p3 = log_dispatch(
            parent="sprint-planner",
            child="technical-lead",
            scope="docs/",
            prompt="Create tickets.",
            sprint_name="003-sprint",
        )
        assert p1.name == "architect-001.md"
        assert p2.name == "architecture-reviewer-001.md"
        assert p3.name == "technical-lead-001.md"

    def test_adhoc_routing(self, tmp_path):
        path = log_dispatch(
            parent="mc",
            child="ah",
            scope="docs/",
            prompt="Ad-hoc change.",
        )
        expected_dir = tmp_path / "docs" / "clasi" / "log" / "adhoc"
        assert path.parent == expected_dir
        assert path.name == "001.md"

    def test_sequence_numbering_increments(self, tmp_path):
        p1 = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="First dispatch.",
            sprint_name="001-my-sprint",
            ticket_id="001",
        )
        p2 = log_dispatch(
            parent="se",
            child="cr",
            scope="src/",
            prompt="Second dispatch.",
            sprint_name="001-my-sprint",
            ticket_id="001",
        )
        assert p1.name == "ticket-001-001.md"
        assert p2.name == "ticket-001-002.md"

    def test_adhoc_sequence_numbering(self, tmp_path):
        p1 = log_dispatch(parent="mc", child="ah", scope=".", prompt="First.")
        p2 = log_dispatch(parent="mc", child="ah", scope=".", prompt="Second.")
        assert p1.name == "001.md"
        assert p2.name == "002.md"

    def test_body_contains_full_prompt(self, tmp_path):
        long_prompt = "Line 1\nLine 2\nLine 3\n" * 100
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt=long_prompt,
            sprint_name="001-sprint",
            ticket_id="002",
        )
        _, body = read_document(path)
        assert long_prompt in body

    def test_creates_directories_on_demand(self, tmp_path):
        sprint_dir = tmp_path / "docs" / "clasi" / "log" / "sprints" / "new-sprint"
        assert not sprint_dir.exists()
        log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Test.",
            sprint_name="new-sprint",
            ticket_id="001",
        )
        assert sprint_dir.is_dir()

    def test_adhoc_creates_directory_on_demand(self, tmp_path):
        adhoc_dir = tmp_path / "docs" / "clasi" / "log" / "adhoc"
        assert not adhoc_dir.exists()
        log_dispatch(parent="mc", child="ah", scope=".", prompt="Test.")
        assert adhoc_dir.is_dir()

    def test_frontmatter_omits_sprint_and_ticket_for_adhoc(self, tmp_path):
        path = log_dispatch(parent="mc", child="ah", scope=".", prompt="Test.")
        fm, _ = read_document(path)
        assert "sprint" not in fm
        assert "ticket" not in fm

    def test_frontmatter_omits_ticket_for_sprint_planner(self, tmp_path):
        path = log_dispatch(
            parent="mc",
            child="sp",
            scope="docs/",
            prompt="Plan.",
            sprint_name="001-sprint",
        )
        fm, _ = read_document(path)
        assert fm["sprint"] == "001-sprint"
        assert "ticket" not in fm


class TestUpdateDispatchResult:
    def test_adds_result_and_files_modified(self, tmp_path):
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Do the work.",
            sprint_name="001-sprint",
            ticket_id="001",
        )
        update_dispatch_result(
            path,
            result="success",
            files_modified=["src/foo.py", "tests/test_foo.py"],
        )
        fm, body = read_document(path)
        assert fm["result"] == "success"
        assert fm["files_modified"] == ["src/foo.py", "tests/test_foo.py"]
        # Original prompt still present
        assert "Do the work." in body

    def test_preserves_existing_frontmatter(self, tmp_path):
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Work.",
            sprint_name="001-sprint",
            ticket_id="002",
        )
        update_dispatch_result(path, result="failure", files_modified=[])
        fm, _ = read_document(path)
        assert fm["parent"] == "se"
        assert fm["child"] == "cm"
        assert fm["sprint"] == "001-sprint"
        assert fm["ticket"] == "002"
        assert fm["result"] == "failure"
        assert fm["files_modified"] == []

    def test_response_appended_to_body(self, tmp_path):
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Implement feature.",
            sprint_name="001-sprint",
            ticket_id="001",
        )
        update_dispatch_result(
            path,
            result="success",
            files_modified=["src/widget.py"],
            response="All done. Created widget module with tests.",
        )
        fm, body = read_document(path)
        assert fm["result"] == "success"
        # Original prompt preserved
        assert "Implement feature." in body
        # Response section appended with child name from frontmatter
        assert "# Response: cm" in body
        assert "All done. Created widget module with tests." in body

    def test_response_none_leaves_body_unchanged(self, tmp_path):
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Do something.",
            sprint_name="001-sprint",
            ticket_id="002",
        )
        _, body_before = read_document(path)
        update_dispatch_result(
            path,
            result="success",
            files_modified=[],
            response=None,
        )
        _, body_after = read_document(path)
        assert body_before == body_after
        assert "# Response:" not in body_after

    def test_response_omitted_leaves_body_unchanged(self, tmp_path):
        """Backward compat: callers that don't pass response at all."""
        path = log_dispatch(
            parent="se",
            child="cm",
            scope="src/",
            prompt="Work.",
            sprint_name="001-sprint",
            ticket_id="003",
        )
        _, body_before = read_document(path)
        update_dispatch_result(path, result="success", files_modified=[])
        _, body_after = read_document(path)
        assert body_before == body_after
        assert "# Response:" not in body_after


class TestTemplateUsed:
    """Tests for the template_used parameter on log_dispatch."""

    def test_template_used_recorded_in_frontmatter(self, tmp_path):
        path = log_dispatch(
            parent="team-lead",
            child="sprint-planner",
            scope="docs/",
            prompt="Plan the sprint.",
            sprint_name="001-sprint",
            template_used="dispatch-sprint-planner.md",
        )
        fm, _ = read_document(path)
        assert fm["template_used"] == "dispatch-sprint-planner.md"

    def test_template_used_none_omitted_from_frontmatter(self, tmp_path):
        path = log_dispatch(
            parent="sprint-planner",
            child="architect",
            scope="docs/",
            prompt="Design architecture.",
            sprint_name="001-sprint",
        )
        fm, _ = read_document(path)
        assert "template_used" not in fm

    def test_template_used_with_ticket_dispatch(self, tmp_path):
        path = log_dispatch(
            parent="sprint-executor",
            child="code-monkey",
            scope="src/",
            prompt="Implement ticket.",
            sprint_name="001-sprint",
            ticket_id="005",
            template_used="dispatch-code-monkey.md",
        )
        fm, _ = read_document(path)
        assert fm["template_used"] == "dispatch-code-monkey.md"
        assert fm["ticket"] == "005"


class TestAutoContextDocuments:
    """Tests for _auto_context_documents helper."""

    def test_sprint_only(self):
        docs = _auto_context_documents("001-my-sprint")
        assert docs == [
            "docs/clasi/sprints/001-my-sprint/sprint.md",
            "docs/clasi/sprints/001-my-sprint/architecture-update.md",
            "docs/clasi/sprints/001-my-sprint/usecases.md",
        ]

    def test_sprint_with_ticket(self):
        docs = _auto_context_documents("002-sprint", ticket_id="007")
        assert docs == [
            "docs/clasi/sprints/002-sprint/sprint.md",
            "docs/clasi/sprints/002-sprint/architecture-update.md",
            "docs/clasi/sprints/002-sprint/usecases.md",
            "docs/clasi/sprints/002-sprint/tickets/007.md",
        ]


class TestContextDocuments:
    """Tests for the context_documents parameter on log_dispatch."""

    def test_auto_populated_from_sprint_name(self, tmp_path):
        """When sprint_name is given and context_documents is None,
        standard planning documents are auto-populated."""
        path = log_dispatch(
            parent="team-lead",
            child="sprint-executor",
            scope="src/",
            prompt="Execute the sprint.",
            sprint_name="010-my-sprint",
            template_used="dispatch-template.md",
        )
        fm, body = read_document(path)
        assert "context_documents" in fm
        assert fm["context_documents"] == [
            "docs/clasi/sprints/010-my-sprint/sprint.md",
            "docs/clasi/sprints/010-my-sprint/architecture-update.md",
            "docs/clasi/sprints/010-my-sprint/usecases.md",
        ]

    def test_auto_populated_with_ticket(self, tmp_path):
        """When sprint_name + ticket_id, ticket file is included."""
        path = log_dispatch(
            parent="sprint-executor",
            child="code-monkey",
            scope="src/",
            prompt="Implement ticket.",
            sprint_name="010-my-sprint",
            ticket_id="003",
            template_used="dispatch-template.md",
        )
        fm, _ = read_document(path)
        assert "docs/clasi/sprints/010-my-sprint/tickets/003.md" in fm["context_documents"]

    def test_explicit_context_documents_override(self, tmp_path):
        """Passing an explicit list replaces auto-population."""
        custom_docs = ["docs/overview.md", "docs/spec.md"]
        path = log_dispatch(
            parent="team-lead",
            child="sprint-planner",
            scope="docs/",
            prompt="Plan it.",
            sprint_name="010-my-sprint",
            template_used="dispatch-template.md",
            context_documents=custom_docs,
        )
        fm, _ = read_document(path)
        assert fm["context_documents"] == custom_docs

    def test_empty_list_overrides_auto_population(self, tmp_path):
        """Passing an empty list explicitly prevents auto-population."""
        path = log_dispatch(
            parent="team-lead",
            child="sprint-planner",
            scope="docs/",
            prompt="Plan it.",
            sprint_name="010-my-sprint",
            template_used="dispatch-template.md",
            context_documents=[],
        )
        fm, _ = read_document(path)
        assert fm["context_documents"] == []

    def test_no_sprint_name_no_context_documents(self, tmp_path):
        """Ad-hoc dispatches without sprint_name have no context_documents."""
        path = log_dispatch(
            parent="mc",
            child="ah",
            scope=".",
            prompt="Ad-hoc.",
        )
        fm, _ = read_document(path)
        assert "context_documents" not in fm

    def test_context_documents_section_in_body(self, tmp_path):
        """Dispatch log body includes a ## Context Documents section."""
        path = log_dispatch(
            parent="team-lead",
            child="sprint-executor",
            scope="src/",
            prompt="Execute.",
            sprint_name="010-my-sprint",
            template_used="dispatch-template.md",
        )
        _, body = read_document(path)
        assert "## Context Documents" in body
        assert "`docs/clasi/sprints/010-my-sprint/sprint.md`" in body
        assert "`docs/clasi/sprints/010-my-sprint/architecture-update.md`" in body
        assert "`docs/clasi/sprints/010-my-sprint/usecases.md`" in body

    def test_explicit_context_documents_in_body(self, tmp_path):
        """Explicit context_documents appear in the body section."""
        custom_docs = ["docs/overview.md", "docs/spec.md"]
        path = log_dispatch(
            parent="team-lead",
            child="sprint-planner",
            scope="docs/",
            prompt="Plan.",
            sprint_name="010-my-sprint",
            template_used="dispatch-template.md",
            context_documents=custom_docs,
        )
        _, body = read_document(path)
        assert "## Context Documents" in body
        assert "`docs/overview.md`" in body
        assert "`docs/spec.md`" in body

    def test_no_context_documents_section_for_adhoc(self, tmp_path):
        """Ad-hoc dispatch without context_documents omits the section."""
        path = log_dispatch(
            parent="mc",
            child="ah",
            scope=".",
            prompt="Ad-hoc.",
        )
        _, body = read_document(path)
        assert "## Context Documents" not in body

    def test_frontmatter_matches_body_documents(self, tmp_path):
        """Frontmatter context_documents match the documents listed in body."""
        path = log_dispatch(
            parent="sprint-executor",
            child="code-monkey",
            scope="src/",
            prompt="Implement.",
            sprint_name="010-sprint",
            ticket_id="002",
            template_used="dispatch-template.md",
        )
        fm, body = read_document(path)
        for doc in fm["context_documents"]:
            assert f"`{doc}`" in body


class TestTemplateEnforcementRemoved:
    """Verify that TEMPLATED_AGENTS enforcement has been removed."""

    def test_dispatch_to_sprint_planner_without_template_succeeds(self, tmp_path):
        """Dispatching to sprint-planner without template_used no longer raises."""
        path = log_dispatch(
            parent="team-lead",
            child="sprint-planner",
            scope="docs/",
            prompt="Plan the sprint.",
            sprint_name="001-sprint",
        )
        assert path.exists()

    def test_dispatch_to_sprint_executor_without_template_succeeds(self, tmp_path):
        """Dispatching to sprint-executor without template_used no longer raises."""
        path = log_dispatch(
            parent="team-lead",
            child="sprint-executor",
            scope="src/",
            prompt="Execute the sprint.",
            sprint_name="001-sprint",
        )
        assert path.exists()

    def test_dispatch_to_code_monkey_without_template_succeeds(self, tmp_path):
        """Dispatching to code-monkey without template_used no longer raises."""
        path = log_dispatch(
            parent="sprint-executor",
            child="code-monkey",
            scope="src/",
            prompt="Implement ticket.",
            sprint_name="001-sprint",
            ticket_id="001",
        )
        assert path.exists()

    def test_templated_agents_constant_removed(self):
        """TEMPLATED_AGENTS set no longer exists in dispatch_log module."""
        import claude_agent_skills.dispatch_log as dl
        assert not hasattr(dl, "TEMPLATED_AGENTS")

    def test_dispatch_to_non_templated_agent_without_template_succeeds(self, tmp_path):
        """Dispatching to todo-worker without template_used still works."""
        path = log_dispatch(
            parent="sprint-planner",
            child="todo-worker",
            scope="docs/",
            prompt="Process the TODO.",
            sprint_name="001-sprint",
        )
        assert path.exists()
        fm, _ = read_document(path)
        assert "template_used" not in fm


class TestTypedDispatchTools:
    """Tests for the three typed dispatch MCP tools."""

    def test_dispatch_to_sprint_planner_renders_template(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_sprint_planner
        import json

        result = json.loads(dispatch_to_sprint_planner(
            sprint_id="024",
            sprint_directory="docs/clasi/sprints/024-test",
            todo_ids=["todo-001.md", "todo-002.md"],
            goals="Build the feature",
        ))
        assert "rendered_prompt" in result
        assert "log_path" in result
        assert "024" in result["rendered_prompt"]
        assert "docs/clasi/sprints/024-test" in result["rendered_prompt"]
        assert "todo-001.md" in result["rendered_prompt"]
        assert "todo-002.md" in result["rendered_prompt"]
        assert "Build the feature" in result["rendered_prompt"]

    def test_dispatch_to_sprint_planner_logs_dispatch(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_sprint_planner
        import json

        result = json.loads(dispatch_to_sprint_planner(
            sprint_id="024",
            sprint_directory="docs/clasi/sprints/024-test",
            todo_ids=["todo-001.md"],
            goals="Test goals",
        ))
        log_path = Path(result["log_path"])
        assert log_path.exists()
        fm, body = read_document(log_path)
        assert fm["parent"] == "team-lead"
        assert fm["child"] == "sprint-planner"
        assert fm["template_used"] == "dispatch-template.md.j2"

    def test_dispatch_to_sprint_executor_renders_template(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_sprint_executor
        import json

        result = json.loads(dispatch_to_sprint_executor(
            sprint_id="024",
            sprint_directory="docs/clasi/sprints/024-test",
            branch_name="sprint/024-test",
            tickets=["015", "016"],
        ))
        assert "rendered_prompt" in result
        assert "log_path" in result
        assert "024" in result["rendered_prompt"]
        assert "sprint/024-test" in result["rendered_prompt"]
        assert "015" in result["rendered_prompt"]
        assert "016" in result["rendered_prompt"]

    def test_dispatch_to_sprint_executor_logs_dispatch(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_sprint_executor
        import json

        result = json.loads(dispatch_to_sprint_executor(
            sprint_id="024",
            sprint_directory="docs/clasi/sprints/024-test",
            branch_name="sprint/024-test",
            tickets=["015"],
        ))
        log_path = Path(result["log_path"])
        assert log_path.exists()
        fm, _ = read_document(log_path)
        assert fm["parent"] == "team-lead"
        assert fm["child"] == "sprint-executor"
        assert fm["template_used"] == "dispatch-template.md.j2"

    def test_dispatch_to_code_monkey_renders_template(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_code_monkey
        import json

        result = json.loads(dispatch_to_code_monkey(
            ticket_path="docs/clasi/sprints/024-test/tickets/015.md",
            ticket_plan_path="docs/clasi/sprints/024-test/tickets/015-plan.md",
            scope_directory="claude_agent_skills/",
            sprint_name="024-test",
            ticket_id="015",
        ))
        assert "rendered_prompt" in result
        assert "log_path" in result
        assert "015.md" in result["rendered_prompt"]
        assert "015-plan.md" in result["rendered_prompt"]
        assert "claude_agent_skills/" in result["rendered_prompt"]
        assert "024-test" in result["rendered_prompt"]

    def test_dispatch_to_code_monkey_logs_dispatch(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_code_monkey
        import json

        result = json.loads(dispatch_to_code_monkey(
            ticket_path="docs/clasi/sprints/024-test/tickets/015.md",
            ticket_plan_path="docs/clasi/sprints/024-test/tickets/015-plan.md",
            scope_directory="claude_agent_skills/",
            sprint_name="024-test",
            ticket_id="015",
        ))
        log_path = Path(result["log_path"])
        assert log_path.exists()
        fm, _ = read_document(log_path)
        assert fm["parent"] == "sprint-executor"
        assert fm["child"] == "code-monkey"
        assert fm["ticket"] == "015"
        assert fm["template_used"] == "dispatch-template.md.j2"

    def test_dispatch_to_code_monkey_returns_rendered_prompt_and_log_path(self, tmp_path):
        from claude_agent_skills.artifact_tools import dispatch_to_code_monkey
        import json

        result = json.loads(dispatch_to_code_monkey(
            ticket_path="tickets/001.md",
            ticket_plan_path="tickets/001-plan.md",
            scope_directory="src/",
            sprint_name="001-sprint",
            ticket_id="001",
        ))
        assert isinstance(result["rendered_prompt"], str)
        assert isinstance(result["log_path"], str)
        assert len(result["rendered_prompt"]) > 0

    def test_get_dispatch_template_tool_removed(self):
        """The old get_dispatch_template tool no longer exists."""
        from claude_agent_skills.mcp_server import server
        tools = server._tool_manager._tools
        assert "get_dispatch_template" not in tools

    def test_log_subagent_dispatch_no_template_used_parameter(self):
        """log_subagent_dispatch no longer accepts template_used."""
        from claude_agent_skills.artifact_tools import log_subagent_dispatch
        import inspect
        sig = inspect.signature(log_subagent_dispatch)
        assert "template_used" not in sig.parameters
