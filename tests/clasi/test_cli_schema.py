"""Tests for `clasi schema validate` CLI subcommand."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from clasi.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_schema(tmp_path: Path, content: str) -> Path:
    """Write *content* to a ``schema.yaml`` inside *tmp_path* and return the path."""
    p = tmp_path / "schema.yaml"
    p.write_text(textwrap.dedent(content))
    return p


VALID_MINIMAL = """\
    version: 1
    name: Minimal Schema
    description: A minimal valid schema for CLI testing
    artifacts: []
"""

CYCLE_SCHEMA = """\
    version: 1
    name: Cycle Schema
    description: Schema with a dependency cycle
    artifacts:
      - id: a
        generates: docs/a.md
        requires: [b]
      - id: b
        generates: docs/b.md
        requires: [a]
"""


# ---------------------------------------------------------------------------
# Group / subcommand presence
# ---------------------------------------------------------------------------


class TestSchemaGroupRegistered:
    def test_schema_group_in_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "schema" in result.output

    def test_schema_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output or "path" in result.output.lower()


# ---------------------------------------------------------------------------
# Happy path — valid schema
# ---------------------------------------------------------------------------


class TestSchemaValidateSuccess:
    def test_valid_schema_exits_zero(self, tmp_path):
        path = write_schema(tmp_path, VALID_MINIMAL)
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(path)])
        assert result.exit_code == 0

    def test_valid_schema_prints_name_and_version(self, tmp_path):
        path = write_schema(tmp_path, VALID_MINIMAL)
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(path)])
        assert "Minimal Schema" in result.output
        assert "version 1" in result.output

    def test_valid_output_format(self, tmp_path):
        path = write_schema(tmp_path, VALID_MINIMAL)
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(path)])
        assert result.output.strip() == "Schema valid: Minimal Schema (version 1)"

    def test_se_process_schema_is_valid(self):
        """The bundled se-process schema must validate without error."""
        import importlib.resources

        # Resolve via importlib.resources to be robust against editable installs
        import clasi.schemas as _pkg
        pkg_path = Path(_pkg.__file__).parent
        se_schema = pkg_path / "se-process" / "schema.yaml"

        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(se_schema)])
        assert result.exit_code == 0
        assert "Schema valid" in result.output


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestSchemaValidateInvalidSchema:
    def test_cycle_exits_nonzero(self, tmp_path):
        path = write_schema(tmp_path, CYCLE_SCHEMA)
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(path)])
        assert result.exit_code != 0

    def test_cycle_produces_error_output(self, tmp_path):
        """Error text must appear somewhere in the combined output."""
        path = write_schema(tmp_path, CYCLE_SCHEMA)
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(path)])
        assert result.exit_code != 0
        # CliRunner merges stderr into output by default; check either.
        assert result.output  # some output produced

    def test_cycle_error_mentions_cycle(self, tmp_path):
        path = write_schema(tmp_path, CYCLE_SCHEMA)
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(path)])
        assert "ycle" in result.output or "cycle" in result.output.lower()


class TestSchemaValidateMissingFile:
    def test_missing_file_exits_nonzero(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(missing)])
        assert result.exit_code != 0

    def test_missing_file_produces_output(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(missing)])
        assert result.exit_code != 0
        assert result.output  # some error text emitted

    def test_missing_file_error_contains_path(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(missing)])
        # The error should mention either "not found" or the file name
        assert (
            "nonexistent.yaml" in result.output
            or "not found" in result.output.lower()
            or "File not found" in result.output
        )
