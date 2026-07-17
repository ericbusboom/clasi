"""Unit tests for the validate_design MCP tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clasi.design.store import write_design_doc, write_readme, write_system_doc
from clasi.mcp_server import set_project
from clasi.tools.design_tools import validate_design


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    set_project(tmp_path)
    return tmp_path


def _configure_sources(tmp_path: Path, sources: list[str]) -> None:
    config_dir = tmp_path / ".clasi"
    config_dir.mkdir(parents=True, exist_ok=True)
    sources_yaml = "\n".join(f"  - {s}" for s in sources)
    (config_dir / "config.yaml").write_text(
        f"sources:\n{sources_yaml}\n", encoding="utf-8"
    )


def _make_subsystem(tmp_path: Path, *parts: str) -> Path:
    subsystem = tmp_path.joinpath(*parts)
    subsystem.mkdir(parents=True, exist_ok=True)
    return subsystem.resolve()


class TestValidateDesignPass:
    def test_valid_doc_set_returns_ok_true_empty_messages(self, work_dir):
        _configure_sources(work_dir, ["src"])
        project_reload = set_project(work_dir)  # refresh cached sources config
        subsystem = _make_subsystem(work_dir, "src", "clasi")

        write_system_doc(project_reload, "# System design\n")
        write_design_doc(project_reload, subsystem, "# clasi subsystem\n")
        write_readme(subsystem, project_reload, name="clasi", description="desc")

        result = json.loads(validate_design())
        assert result == {"ok": True, "messages": [], "info": []}


class TestValidateDesignFail:
    def test_missing_design_md_returns_ok_false_with_message(self, work_dir):
        _configure_sources(work_dir, ["src"])
        set_project(work_dir)

        result = json.loads(validate_design())
        assert result["ok"] is False
        assert isinstance(result["messages"], list)
        assert any("Missing top-level design document" in m for m in result["messages"])

    def test_none_overlay_dir_validates_canonical_only(self, work_dir):
        _configure_sources(work_dir, ["src"])
        project_reload = set_project(work_dir)
        subsystem = _make_subsystem(work_dir, "src", "clasi")
        write_system_doc(project_reload, "# System design\n")
        write_design_doc(project_reload, subsystem, "# clasi subsystem\n")
        write_readme(subsystem, project_reload, name="clasi", description="desc")

        result = json.loads(validate_design(overlay_dir=None))
        assert result["ok"] is True


class TestValidateDesignInfo:
    def test_non_subsystem_doc_surfaces_as_info_not_error(self, work_dir):
        _configure_sources(work_dir, ["src"])
        project_reload = set_project(work_dir)
        subsystem = _make_subsystem(work_dir, "src", "clasi")

        write_system_doc(project_reload, "# System design\n")
        write_design_doc(project_reload, subsystem, "# clasi subsystem\n")
        write_readme(subsystem, project_reload, name="clasi", description="desc")

        (project_reload.design_dir / "overview.md").write_text(
            "# Overview\n\nNo frontmatter.\n", encoding="utf-8"
        )

        result = json.loads(validate_design())
        assert result["ok"] is True
        assert result["messages"] == []
        assert any("overview.md" in m for m in result["info"])
