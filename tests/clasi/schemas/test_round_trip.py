"""End-to-end round-trip tests for se-process and solo-process schemas.

Loads the actual shipped schema files via importlib.resources so tests work
in both development (editable install) and CI (installed package).  Exercises
the full schema stack: loader, ArtifactGraph, gate queries, and the CLI
validate subcommand.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path

import pytest
from click.testing import CliRunner

import clasi.schemas as _schemas_pkg
from clasi.cli import cli
from clasi.schemas import loader
from clasi.schemas.graph import ArtifactGraph
from clasi.schemas.models import GateSpec


# ---------------------------------------------------------------------------
# Resolve shipped schema paths once via importlib.resources
# ---------------------------------------------------------------------------

_SCHEMAS_ROOT = Path(_schemas_pkg.__file__).parent
_SE_SCHEMA_PATH = _SCHEMAS_ROOT / "se-process" / "schema.yaml"
_SOLO_SCHEMA_PATH = _SCHEMAS_ROOT / "solo-process" / "schema.yaml"

_SE_EXPECTED_PHASES = [
    "roadmap",
    "planning-docs",
    "architecture-review",
    "stakeholder-review",
    "ticketing",
    "executing",
    "closing",
    "done",
]

_SOLO_EXPECTED_PHASES = [
    "roadmap",
    "planning-docs",
    "ticketing",
    "executing",
    "closing",
    "done",
]


# ---------------------------------------------------------------------------
# se-process round-trip
# ---------------------------------------------------------------------------


class TestSeProcessRoundTrip:
    def test_se_process_round_trip(self):
        """se-process schema loads and reports name == 'se-process'."""
        schema = loader.load(_SE_SCHEMA_PATH)
        assert schema.name == "se-process"

    def test_se_process_phases(self):
        """ArtifactGraph(se_schema).phases() returns the full 8-phase list."""
        schema = loader.load(_SE_SCHEMA_PATH)
        assert ArtifactGraph(schema).phases() == _SE_EXPECTED_PHASES

    def test_se_gate_for_architecture_review(self):
        """gate_for('architecture-review') returns review gate with correct record."""
        schema = loader.load(_SE_SCHEMA_PATH)
        graph = ArtifactGraph(schema)
        expected = GateSpec(kind="review", record="architecture_review")
        assert graph.gate_for("architecture-review") == expected

    def test_se_gate_for_stakeholder_review(self):
        """gate_for('stakeholder-review') returns stakeholder-review gate with correct record."""
        schema = loader.load(_SE_SCHEMA_PATH)
        graph = ArtifactGraph(schema)
        expected = GateSpec(kind="stakeholder-review", record="stakeholder_approval")
        assert graph.gate_for("stakeholder-review") == expected

    def test_se_phases_match_state_db_phases(self):
        """ArtifactGraph(se_schema).phases() equals PHASES from state_db_class.py."""
        from clasi.state_db_class import PHASES as STATE_DB_PHASES

        schema = loader.load(_SE_SCHEMA_PATH)
        assert ArtifactGraph(schema).phases() == STATE_DB_PHASES


# ---------------------------------------------------------------------------
# solo-process round-trip
# ---------------------------------------------------------------------------


class TestSoloProcessRoundTrip:
    def test_solo_process_round_trip(self):
        """solo-process schema loads and reports name == 'solo-process'."""
        schema = loader.load(_SOLO_SCHEMA_PATH)
        assert schema.name == "solo-process"

    def test_solo_process_phases(self):
        """ArtifactGraph(solo_schema).phases() returns the leaner 6-phase list."""
        schema = loader.load(_SOLO_SCHEMA_PATH)
        assert ArtifactGraph(schema).phases() == _SOLO_EXPECTED_PHASES

    def test_solo_no_architecture_review_phase(self):
        """'architecture-review' is absent from the solo-process phase list."""
        schema = loader.load(_SOLO_SCHEMA_PATH)
        assert "architecture-review" not in ArtifactGraph(schema).phases()

    def test_solo_no_stakeholder_review_phase(self):
        """'stakeholder-review' is absent from the solo-process phase list."""
        schema = loader.load(_SOLO_SCHEMA_PATH)
        assert "stakeholder-review" not in ArtifactGraph(schema).phases()


# ---------------------------------------------------------------------------
# CLI validate subcommand
# ---------------------------------------------------------------------------


class TestCliValidateSchemas:
    def test_cli_validate_se_schema(self):
        """'clasi schema validate <se-schema-path>' exits 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(_SE_SCHEMA_PATH)])
        assert result.exit_code == 0

    def test_cli_validate_se_schema_output(self):
        """CLI validate for se-process reports schema name in output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(_SE_SCHEMA_PATH)])
        assert "se-process" in result.output

    def test_cli_validate_solo_schema(self):
        """'clasi schema validate <solo-schema-path>' exits 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(_SOLO_SCHEMA_PATH)])
        assert result.exit_code == 0

    def test_cli_validate_solo_schema_output(self):
        """CLI validate for solo-process reports schema name in output."""
        runner = CliRunner()
        result = runner.invoke(cli, ["schema", "validate", str(_SOLO_SCHEMA_PATH)])
        assert "solo-process" in result.output
