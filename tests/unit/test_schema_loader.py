"""Unit tests for clasi.schemas.loader.

Covers: happy path, duplicate IDs, missing requires, unknown gate kinds,
cycle detection, YAML parse errors, Pydantic validation errors, and
no-clasi-imports invariant.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from clasi.schemas.loader import load
from clasi.schemas.models import SchemaError, WorkflowSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_schema(tmp_path: Path, content: str) -> Path:
    """Write *content* to a ``schema.yaml`` inside *tmp_path* and return the path."""
    p = tmp_path / "schema.yaml"
    p.write_text(textwrap.dedent(content))
    return p


MINIMAL_VALID = """\
    version: 1
    name: Test Schema
    description: A minimal test schema
    artifacts: []
"""

SINGLE_ARTIFACT = """\
    version: 1
    name: Single
    description: One artifact, no deps
    artifacts:
      - id: overview
        generates: docs/overview.md
"""

TWO_ARTIFACTS_LINEAR = """\
    version: 1
    name: Linear
    description: A -> B
    artifacts:
      - id: b
        generates: docs/b.md
        requires: [a]
      - id: a
        generates: docs/a.md
"""

GATE_VALID = """\
    version: 1
    name: Gated
    description: Artifact with a valid gate
    artifacts:
      - id: spec
        generates: docs/spec.md
        gate:
          kind: stakeholder-review
          record: docs/spec-review.md
"""


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_returns_workflow_schema(self, tmp_path):
        path = write_schema(tmp_path, MINIMAL_VALID)
        result = load(path)
        assert isinstance(result, WorkflowSchema)

    def test_accepts_str_path(self, tmp_path):
        path = write_schema(tmp_path, MINIMAL_VALID)
        result = load(str(path))
        assert isinstance(result, WorkflowSchema)

    def test_single_artifact(self, tmp_path):
        path = write_schema(tmp_path, SINGLE_ARTIFACT)
        result = load(path)
        assert len(result.artifacts) == 1
        assert result.artifacts[0].id == "overview"

    def test_topological_order_linear(self, tmp_path):
        """``b`` requires ``a``; even though ``b`` is listed first, ``a`` must come first."""
        path = write_schema(tmp_path, TWO_ARTIFACTS_LINEAR)
        result = load(path)
        ids = [a.id for a in result.artifacts]
        assert ids.index("a") < ids.index("b")

    def test_topological_order_diamond(self, tmp_path):
        """Diamond: a -> b, a -> c, b -> d, c -> d."""
        content = """\
            version: 1
            name: Diamond
            description: Diamond dep graph
            artifacts:
              - id: d
                generates: docs/d.md
                requires: [b, c]
              - id: b
                generates: docs/b.md
                requires: [a]
              - id: c
                generates: docs/c.md
                requires: [a]
              - id: a
                generates: docs/a.md
        """
        path = write_schema(tmp_path, content)
        result = load(path)
        ids = [a.id for a in result.artifacts]
        assert ids[0] == "a"
        assert ids[-1] == "d"
        assert set(ids) == {"a", "b", "c", "d"}

    def test_valid_gate_kinds(self, tmp_path):
        for kind in ("stakeholder-review", "review", "per-ticket"):
            content = f"""\
                version: 1
                name: G
                description: d
                artifacts:
                  - id: x
                    generates: docs/x.md
                    gate:
                      kind: {kind}
                      record: docs/x-review.md
            """
            path = write_schema(tmp_path, content)
            result = load(path)
            assert result.artifacts[0].gate.kind == kind

    def test_optional_instruction_and_lock(self, tmp_path):
        content = """\
            version: 1
            name: Full
            description: All optional fields
            artifacts:
              - id: x
                generates: docs/x.md
                instruction: Write a great doc.
                lock: docs/x.lock
        """
        path = write_schema(tmp_path, content)
        result = load(path)
        art = result.artifacts[0]
        assert art.instruction == "Write a great doc."
        assert art.lock == "docs/x.lock"


# ---------------------------------------------------------------------------
# Structural error cases
# ---------------------------------------------------------------------------


class TestDuplicateIds:
    def test_raises_schema_error(self, tmp_path):
        content = """\
            version: 1
            name: Dup
            description: d
            artifacts:
              - id: x
                generates: docs/x.md
              - id: x
                generates: docs/y.md
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="Duplicate artifact id"):
            load(path)

    def test_error_names_duplicated_id(self, tmp_path):
        content = """\
            version: 1
            name: Dup
            description: d
            artifacts:
              - id: alpha
                generates: docs/a.md
              - id: alpha
                generates: docs/b.md
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="alpha"):
            load(path)


class TestMissingRequires:
    def test_raises_schema_error(self, tmp_path):
        content = """\
            version: 1
            name: Missing
            description: d
            artifacts:
              - id: x
                generates: docs/x.md
                requires: [nonexistent]
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="nonexistent"):
            load(path)

    def test_error_names_missing_id(self, tmp_path):
        content = """\
            version: 1
            name: Missing
            description: d
            artifacts:
              - id: x
                generates: docs/x.md
                requires: [ghost]
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="ghost"):
            load(path)


class TestUnknownGateKind:
    def test_raises_schema_error(self, tmp_path):
        content = """\
            version: 1
            name: BadGate
            description: d
            artifacts:
              - id: x
                generates: docs/x.md
                gate:
                  kind: magic-gate
                  record: docs/x-review.md
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="magic-gate"):
            load(path)

    def test_error_names_artifact_id(self, tmp_path):
        content = """\
            version: 1
            name: BadGate
            description: d
            artifacts:
              - id: my-artifact
                generates: docs/x.md
                gate:
                  kind: bad-kind
                  record: docs/x-review.md
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="my-artifact"):
            load(path)


class TestCycleDetection:
    def test_simple_cycle_raises(self, tmp_path):
        content = """\
            version: 1
            name: Cycle
            description: d
            artifacts:
              - id: a
                generates: docs/a.md
                requires: [b]
              - id: b
                generates: docs/b.md
                requires: [a]
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="[Cc]ycle"):
            load(path)

    def test_cycle_error_identifies_nodes(self, tmp_path):
        content = """\
            version: 1
            name: Cycle
            description: d
            artifacts:
              - id: alpha
                generates: docs/a.md
                requires: [beta]
              - id: beta
                generates: docs/b.md
                requires: [alpha]
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError) as exc_info:
            load(path)
        msg = str(exc_info.value)
        assert "alpha" in msg or "beta" in msg

    def test_self_loop_raises(self, tmp_path):
        content = """\
            version: 1
            name: Self
            description: d
            artifacts:
              - id: x
                generates: docs/x.md
                requires: [x]
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError):
            load(path)

    def test_longer_cycle_raises(self, tmp_path):
        """Three-node cycle: a -> b -> c -> a."""
        content = """\
            version: 1
            name: LongCycle
            description: d
            artifacts:
              - id: a
                generates: docs/a.md
                requires: [c]
              - id: b
                generates: docs/b.md
                requires: [a]
              - id: c
                generates: docs/c.md
                requires: [b]
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError, match="[Cc]ycle"):
            load(path)


# ---------------------------------------------------------------------------
# YAML / Pydantic error cases
# ---------------------------------------------------------------------------


class TestYamlErrors:
    def test_invalid_yaml_raises_schema_error(self, tmp_path):
        p = tmp_path / "schema.yaml"
        p.write_text("key: [\nbad yaml")
        with pytest.raises(SchemaError, match="[Yy]AML"):
            load(p)

    def test_missing_file_raises_schema_error(self, tmp_path):
        p = tmp_path / "nonexistent.yaml"
        with pytest.raises(SchemaError):
            load(p)

    def test_non_mapping_yaml_raises_schema_error(self, tmp_path):
        p = tmp_path / "schema.yaml"
        p.write_text("- just\n- a\n- list\n")
        with pytest.raises(SchemaError):
            load(p)


class TestPydanticValidation:
    def test_missing_required_field_raises_schema_error(self, tmp_path):
        content = """\
            version: 1
            name: Bad
            description: missing artifacts key
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError):
            load(path)

    def test_extra_field_raises_schema_error(self, tmp_path):
        content = """\
            version: 1
            name: Bad
            description: extra field
            artifacts: []
            unknown_key: oops
        """
        path = write_schema(tmp_path, content)
        with pytest.raises(SchemaError):
            load(path)


# ---------------------------------------------------------------------------
# Import invariant
# ---------------------------------------------------------------------------


class TestNoClasImports:
    """loader.py must not import from clasi.* except clasi.schemas.models."""

    def test_no_clasi_imports_except_schemas(self):
        import ast
        import importlib.util

        spec = importlib.util.find_spec("clasi.schemas.loader")
        assert spec is not None
        source = Path(spec.origin).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                    if mod.startswith("clasi.") and not mod.startswith("clasi.schemas"):
                        raise AssertionError(
                            f"loader.py imports from {mod!r}, which is outside clasi.schemas"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("clasi.") and not alias.name.startswith(
                            "clasi.schemas"
                        ):
                            raise AssertionError(
                                f"loader.py imports from {alias.name!r}, which is outside clasi.schemas"
                            )
