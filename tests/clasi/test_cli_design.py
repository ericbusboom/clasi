"""Tests for `clasi design validate` CLI subcommand."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from clasi.cli import cli
from clasi.design.store import write_design_doc, write_readme, write_system_doc
from clasi.project import Project


def _make_project(tmp_path: Path, sources: list[str]) -> Project:
    config_dir = tmp_path / ".clasi"
    config_dir.mkdir(parents=True, exist_ok=True)
    sources_yaml = "\n".join(f"  - {s}" for s in sources)
    (config_dir / "config.yaml").write_text(
        f"sources:\n{sources_yaml}\n", encoding="utf-8"
    )
    return Project(tmp_path)


def _make_subsystem(tmp_path: Path, *parts: str) -> Path:
    subsystem = tmp_path.joinpath(*parts)
    subsystem.mkdir(parents=True, exist_ok=True)
    return subsystem.resolve()


def _write_valid_doc_set(tmp_path: Path) -> Project:
    project = _make_project(tmp_path, ["src"])
    subsystem = _make_subsystem(tmp_path, "src", "clasi")
    write_system_doc(project, "# System design\n")
    write_design_doc(project, subsystem, "# clasi subsystem\n")
    write_readme(subsystem, project, name="clasi", description="The clasi package.")
    return project


class TestDesignGroupRegistered:
    def test_design_group_in_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "design" in result.output

    def test_design_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "validate", "--help"])
        assert result.exit_code == 0


class TestDesignValidateSuccess:
    def test_valid_doc_set_exits_zero(self, tmp_path):
        _write_valid_doc_set(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "validate", str(tmp_path)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()


class TestDesignValidateFailure:
    def test_missing_design_md_exits_nonzero(self, tmp_path):
        _make_project(tmp_path, ["src"])
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "Missing top-level design document" in result.output

    def test_default_path_is_current_directory(self, tmp_path, monkeypatch):
        _write_valid_doc_set(tmp_path)
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["design", "validate"])
        assert result.exit_code == 0
