"""Unit tests for loader.load() rejection branches.

Tests use in-memory dicts passed to load_from_dict() so no fixture files
are needed.  Every SchemaError path in loader.py is exercised here.
"""

from __future__ import annotations

import pytest

from clasi.schemas.loader import load_from_dict
from clasi.schemas.models import SchemaError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_schema(**overrides) -> dict:
    """Return a minimal valid schema dict, with optional field overrides."""
    base: dict = {
        "version": 1,
        "name": "test-workflow",
        "description": "A test workflow.",
        "artifacts": [
            {
                "id": "overview",
                "generates": "docs/overview.md",
            },
            {
                "id": "spec",
                "generates": "docs/spec.md",
                "requires": ["overview"],
            },
        ],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# AC: valid minimal schema loads successfully
# ---------------------------------------------------------------------------

class TestValidLoad:
    def test_valid_minimal_schema_loads(self):
        """A schema with two artifacts and one requires link loads without error."""
        schema = load_from_dict(_minimal_schema())
        ids = [a.id for a in schema.artifacts]
        # overview must come before spec (topological order)
        assert ids.index("overview") < ids.index("spec")

    def test_artifact_with_no_requires_defaults_to_empty_list(self):
        """An artifact that omits the requires field defaults to [] (not an error)."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "root", "generates": "root.md"},
            ],
        }
        schema = load_from_dict(data)
        assert schema.artifacts[0].requires == []


# ---------------------------------------------------------------------------
# AC: duplicate artifact id raises SchemaError
# ---------------------------------------------------------------------------

class TestDuplicateId:
    def test_duplicate_id_raises_schema_error(self):
        """Two artifacts with the same id raise SchemaError naming the duplicate."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "alpha", "generates": "alpha.md"},
                {"id": "alpha", "generates": "alpha2.md"},
            ],
        }
        with pytest.raises(SchemaError, match="alpha"):
            load_from_dict(data)

    def test_duplicate_id_message_contains_the_id(self):
        """The error message specifically names the duplicate id."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "my-dup", "generates": "a.md"},
                {"id": "my-dup", "generates": "b.md"},
            ],
        }
        with pytest.raises(SchemaError) as exc_info:
            load_from_dict(data)
        assert "my-dup" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC: requires referencing a non-existent ID raises SchemaError
# ---------------------------------------------------------------------------

class TestMissingRequiresReference:
    def test_missing_requires_raises_schema_error(self):
        """requires referencing a non-existent id raises SchemaError naming the missing id."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {
                    "id": "child",
                    "generates": "child.md",
                    "requires": ["ghost"],
                },
            ],
        }
        with pytest.raises(SchemaError, match="ghost"):
            load_from_dict(data)

    def test_missing_requires_message_contains_missing_id(self):
        """The error message names the unresolvable dependency."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {
                    "id": "child",
                    "generates": "child.md",
                    "requires": ["does-not-exist"],
                },
            ],
        }
        with pytest.raises(SchemaError) as exc_info:
            load_from_dict(data)
        assert "does-not-exist" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC: cycle detection
# ---------------------------------------------------------------------------

class TestCycleDetection:
    def test_two_node_cycle_raises_schema_error(self):
        """A -> B -> A is detected as a cycle."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "A", "generates": "a.md", "requires": ["B"]},
                {"id": "B", "generates": "b.md", "requires": ["A"]},
            ],
        }
        with pytest.raises(SchemaError, match="[Cc]ycle"):
            load_from_dict(data)

    def test_three_node_cycle_raises_schema_error(self):
        """A -> B -> C -> A is detected as a cycle."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "A", "generates": "a.md", "requires": ["C"]},
                {"id": "B", "generates": "b.md", "requires": ["A"]},
                {"id": "C", "generates": "c.md", "requires": ["B"]},
            ],
        }
        with pytest.raises(SchemaError, match="[Cc]ycle"):
            load_from_dict(data)

    def test_two_node_cycle_names_involved_ids(self):
        """The SchemaError for a cycle names the artifact IDs involved."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "alpha", "generates": "a.md", "requires": ["beta"]},
                {"id": "beta", "generates": "b.md", "requires": ["alpha"]},
            ],
        }
        with pytest.raises(SchemaError) as exc_info:
            load_from_dict(data)
        msg = str(exc_info.value)
        assert "alpha" in msg
        assert "beta" in msg


# ---------------------------------------------------------------------------
# AC: unknown gate kind raises SchemaError
# ---------------------------------------------------------------------------

class TestUnknownGateKind:
    def test_unknown_gate_kind_raises_schema_error(self):
        """An artifact with an unrecognised gate kind raises SchemaError."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {
                    "id": "gated",
                    "generates": "gated.md",
                    "gate": {"kind": "not-a-real-kind", "record": "some-record"},
                },
            ],
        }
        with pytest.raises(SchemaError, match="not-a-real-kind"):
            load_from_dict(data)

    def test_unknown_gate_kind_message_names_the_kind(self):
        """The error message explicitly names the unknown gate kind."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {
                    "id": "gated",
                    "generates": "gated.md",
                    "gate": {"kind": "magic-gate", "record": "rec"},
                },
            ],
        }
        with pytest.raises(SchemaError) as exc_info:
            load_from_dict(data)
        assert "magic-gate" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC: extra unknown field raises SchemaError (Pydantic extra="forbid")
# ---------------------------------------------------------------------------

class TestExtraFieldForbidden:
    def test_extra_field_on_artifact_raises_schema_error(self):
        """An unknown field on an artifact raises SchemaError (Pydantic extra=forbid)."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {
                    "id": "root",
                    "generates": "root.md",
                    "foo": "bar",
                },
            ],
        }
        with pytest.raises(SchemaError):
            load_from_dict(data)

    def test_extra_field_on_top_level_raises_schema_error(self):
        """An unknown field at the top-level schema raises SchemaError."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "root", "generates": "root.md"},
            ],
            "unknown_top_level_key": "oops",
        }
        with pytest.raises(SchemaError):
            load_from_dict(data)


# ---------------------------------------------------------------------------
# AC: missing required field 'id' on artifact raises SchemaError
# ---------------------------------------------------------------------------

class TestMissingRequiredField:
    def test_missing_id_raises_schema_error(self):
        """An artifact without the required 'id' field raises SchemaError."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"generates": "root.md"},
            ],
        }
        with pytest.raises(SchemaError):
            load_from_dict(data)

    def test_missing_generates_raises_schema_error(self):
        """An artifact without the required 'generates' field raises SchemaError."""
        data = {
            "version": 1,
            "name": "test",
            "description": "desc",
            "artifacts": [
                {"id": "root"},
            ],
        }
        with pytest.raises(SchemaError):
            load_from_dict(data)
