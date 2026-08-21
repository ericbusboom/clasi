"""Smoke tests for the se-process workflow schema.

Verifies that clasi/schemas/se-process/schema.yaml loads correctly and
produces the expected topological order matching PHASES in state_db_class.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import clasi.schemas as _schemas_pkg
from clasi.schemas import loader
from clasi.schemas.models import WorkflowSchema

# Derive the schema path from the installed package so the test is
# robust regardless of the current working directory.
_SCHEMAS_DIR = Path(_schemas_pkg.__file__).resolve().parent
_SCHEMA_PATH = _SCHEMAS_DIR / "se-process" / "schema.yaml"

_EXPECTED_ORDER = [
    "roadmap",
    "planning-docs",
    "architecture-review",
    "ticketing",
    "executing",
    "closing",
    "done",
]


class TestSeSchemaLoads:
    def test_schema_name(self):
        """Schema loads and reports name == 'se-process'."""
        schema = loader.load(_SCHEMA_PATH)
        assert schema.name == "se-process"

    def test_topo_order_matches_phases(self):
        """Artifact IDs in topo-sort order match PHASES from state_db_class.py."""
        schema = loader.load(_SCHEMA_PATH)
        ids = [a.id for a in schema.artifacts]
        assert ids == _EXPECTED_ORDER

    def test_architecture_review_gate(self):
        """architecture-review artifact has gate kind=review, record=architecture_review."""
        schema = loader.load(_SCHEMA_PATH)
        idx = {a.id: a for a in schema.artifacts}
        ar = idx["architecture-review"]
        assert ar.gate is not None
        assert ar.gate.kind == "review"
        assert ar.gate.record == "architecture_review"

    def test_stakeholder_review_phase_removed(self):
        """031/002: the stakeholder-review artifact/phase is deleted --
        stakeholder_approval now gates acquire_execution_lock instead of a
        phase in this schema (see state_db_class.py's advance_to())."""
        schema = loader.load(_SCHEMA_PATH)
        ids = {a.id for a in schema.artifacts}
        assert "stakeholder-review" not in ids

    def test_ticketing_requires_only_architecture_review(self):
        """031/002: ticketing's requires: is [architecture-review] now that
        the stakeholder-review artifact between them is gone."""
        schema = loader.load(_SCHEMA_PATH)
        idx = {a.id: a for a in schema.artifacts}
        assert idx["ticketing"].requires == ["architecture-review"]

    def test_executing_gate_and_lock(self):
        """executing artifact has gate kind=per-ticket and lock=execution."""
        schema = loader.load(_SCHEMA_PATH)
        idx = {a.id: a for a in schema.artifacts}
        ex = idx["executing"]
        assert ex.gate is not None
        assert ex.gate.kind == "per-ticket"
        assert ex.lock == "execution"

    def test_all_instruction_stubs_exist(self):
        """All 8 instruction stub files referenced in the schema exist on disk."""
        schema = loader.load(_SCHEMA_PATH)
        _PREFIX = "clasi/schemas/"
        for artifact in schema.artifacts:
            if artifact.instruction is not None:
                rel = artifact.instruction
                if rel.startswith(_PREFIX):
                    rel = rel[len(_PREFIX):]
                stub = _SCHEMAS_DIR / rel
                assert stub.exists(), f"Missing instruction stub: {stub}"
