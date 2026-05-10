"""Smoke tests for the se-process workflow schema.

Verifies that clasi/schemas/se-process/schema.yaml loads correctly and
produces the expected topological order matching PHASES in state_db_class.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clasi.schemas import loader
from clasi.schemas.models import WorkflowSchema

# Path relative to repo root; loader.load() accepts Path or str.
_SCHEMA_PATH = Path("clasi/schemas/se-process/schema.yaml")

_EXPECTED_ORDER = [
    "roadmap",
    "planning-docs",
    "architecture-review",
    "stakeholder-review",
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

    def test_stakeholder_review_gate(self):
        """stakeholder-review artifact has gate kind=stakeholder-review, record=stakeholder_approval."""
        schema = loader.load(_SCHEMA_PATH)
        idx = {a.id: a for a in schema.artifacts}
        sr = idx["stakeholder-review"]
        assert sr.gate is not None
        assert sr.gate.kind == "stakeholder-review"
        assert sr.gate.record == "stakeholder_approval"

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
        for artifact in schema.artifacts:
            if artifact.instruction is not None:
                stub = Path(artifact.instruction)
                assert stub.exists(), f"Missing instruction stub: {stub}"
