"""Smoke tests for the solo-process workflow schema.

Verifies that clasi/schemas/solo-process/schema.yaml loads correctly and
produces the expected topological order, gate configuration, and instruction
stubs. Confirms the leaner DAG: no architecture-review or stakeholder-review
artifacts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from clasi.schemas import loader
from clasi.schemas.graph import ArtifactGraph

_SCHEMA_PATH = Path("clasi/schemas/solo-process/schema.yaml")

_EXPECTED_PHASES = [
    "roadmap",
    "planning-docs",
    "ticketing",
    "executing",
    "closing",
    "done",
]

_ABSENT_PHASES = ["architecture-review", "stakeholder-review"]


class TestSoloSchemaLoads:
    def test_schema_name(self):
        """Schema loads and reports name == 'solo-process'."""
        schema = loader.load(_SCHEMA_PATH)
        assert schema.name == "solo-process"

    def test_phases_order(self):
        """ArtifactGraph.phases() returns the expected leaner phase list."""
        schema = loader.load(_SCHEMA_PATH)
        graph = ArtifactGraph(schema)
        assert graph.phases() == _EXPECTED_PHASES

    def test_no_review_artifacts(self):
        """architecture-review and stakeholder-review are absent from the DAG."""
        schema = loader.load(_SCHEMA_PATH)
        ids = {a.id for a in schema.artifacts}
        for absent in _ABSENT_PHASES:
            assert absent not in ids, f"Artifact {absent!r} must not exist in solo-process"

    def test_no_review_gate_kinds(self):
        """No gate with kind 'review' or 'stakeholder-review' exists."""
        schema = loader.load(_SCHEMA_PATH)
        forbidden_kinds = {"review", "stakeholder-review"}
        for artifact in schema.artifacts:
            if artifact.gate is not None:
                assert artifact.gate.kind not in forbidden_kinds, (
                    f"Artifact {artifact.id!r} has forbidden gate kind {artifact.gate.kind!r}"
                )

    def test_executing_gate_and_lock(self):
        """executing artifact has gate kind=per-ticket and lock=execution."""
        schema = loader.load(_SCHEMA_PATH)
        idx = {a.id: a for a in schema.artifacts}
        ex = idx["executing"]
        assert ex.gate is not None
        assert ex.gate.kind == "per-ticket"
        assert ex.lock == "execution"

    def test_instruction_stubs_exist(self):
        """All instruction files referenced in the schema exist on disk."""
        schema = loader.load(_SCHEMA_PATH)
        seen: set[str] = set()
        for artifact in schema.artifacts:
            if artifact.instruction is not None and artifact.instruction not in seen:
                seen.add(artifact.instruction)
                stub = Path(artifact.instruction)
                assert stub.exists(), f"Missing instruction stub: {stub}"

    @pytest.mark.parametrize("name", ["overview.md", "sprint-plan.md", "tickets.md", "execution.md", "close.md"])
    def test_named_stub_files_exist(self, name: str):
        """Each named instruction stub file exists under solo-process/instructions/."""
        stub = Path(f"clasi/schemas/solo-process/instructions/{name}")
        assert stub.exists(), f"Missing stub: {stub}"
