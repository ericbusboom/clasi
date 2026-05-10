"""Unit tests for ArtifactGraph query methods."""

from __future__ import annotations

import pytest

from clasi.schemas import ArtifactGraph, ArtifactSpec, GateSpec, WorkflowSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_schema(artifacts: list[ArtifactSpec]) -> WorkflowSchema:
    """Build a minimal WorkflowSchema with the given artifacts."""
    return WorkflowSchema(
        version=1,
        name="test",
        description="test schema",
        artifacts=artifacts,
    )


def _simple_graph() -> ArtifactGraph:
    """Two-artifact schema: 'overview' (root) -> 'spec' (depends on overview)."""
    overview = ArtifactSpec(
        id="overview",
        generates="docs/overview.md",
        instruction="Write the overview.",
        requires=[],
        gate=GateSpec(kind="stakeholder-review", record="overview-gate"),
    )
    spec = ArtifactSpec(
        id="spec",
        generates="docs/spec.md",
        instruction=None,
        requires=["overview"],
        gate=None,
    )
    schema = _make_schema([overview, spec])
    return ArtifactGraph(schema)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestArtifactGraphPhases:
    def test_phases_returns_ids_in_order(self):
        graph = _simple_graph()
        assert graph.phases() == ["overview", "spec"]

    def test_phases_single_artifact(self):
        single = ArtifactSpec(id="only", generates="only.md")
        graph = ArtifactGraph(_make_schema([single]))
        assert graph.phases() == ["only"]

    def test_phases_returns_list_of_strings(self):
        graph = _simple_graph()
        result = graph.phases()
        assert isinstance(result, list)
        assert all(isinstance(p, str) for p in result)


class TestArtifactGraphArtifact:
    def test_artifact_returns_spec(self):
        graph = _simple_graph()
        spec = graph.artifact("overview")
        assert isinstance(spec, ArtifactSpec)
        assert spec.id == "overview"

    def test_artifact_second_item(self):
        graph = _simple_graph()
        spec = graph.artifact("spec")
        assert spec.id == "spec"

    def test_artifact_raises_keyerror_for_missing(self):
        graph = _simple_graph()
        with pytest.raises(KeyError):
            graph.artifact("nonexistent")


class TestArtifactGraphRequires:
    def test_requires_root_is_empty(self):
        graph = _simple_graph()
        assert graph.requires("overview") == []

    def test_requires_dependent_lists_dep(self):
        graph = _simple_graph()
        assert graph.requires("spec") == ["overview"]

    def test_requires_raises_keyerror_for_missing(self):
        graph = _simple_graph()
        with pytest.raises(KeyError):
            graph.requires("ghost")

    def test_requires_returns_copy(self):
        """Mutating the returned list does not affect the graph."""
        graph = _simple_graph()
        result = graph.requires("spec")
        result.clear()
        assert graph.requires("spec") == ["overview"]


class TestArtifactGraphGateFor:
    def test_gate_for_returns_gate_spec(self):
        graph = _simple_graph()
        gate = graph.gate_for("overview")
        assert isinstance(gate, GateSpec)
        assert gate.kind == "stakeholder-review"
        assert gate.record == "overview-gate"

    def test_gate_for_returns_none_when_no_gate(self):
        graph = _simple_graph()
        assert graph.gate_for("spec") is None

    def test_gate_for_raises_keyerror_for_missing(self):
        graph = _simple_graph()
        with pytest.raises(KeyError):
            graph.gate_for("missing")


class TestArtifactGraphInstructionFor:
    def test_instruction_for_returns_string(self):
        graph = _simple_graph()
        assert graph.instruction_for("overview") == "Write the overview."

    def test_instruction_for_returns_none_when_absent(self):
        graph = _simple_graph()
        assert graph.instruction_for("spec") is None

    def test_instruction_for_raises_keyerror_for_missing(self):
        graph = _simple_graph()
        with pytest.raises(KeyError):
            graph.instruction_for("nope")


class TestArtifactGraphExport:
    def test_importable_from_clasi_schemas(self):
        """ArtifactGraph must be importable from the package top-level."""
        from clasi.schemas import ArtifactGraph as AG  # noqa: F401
        assert AG is ArtifactGraph
