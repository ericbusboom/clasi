"""Pydantic data models for CLASI workflow schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SchemaError(Exception):
    """Raised when a workflow schema is invalid or cannot be loaded."""


class GateSpec(BaseModel):
    """Specification for a gate that validates an artifact."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    record: str


class ArtifactSpec(BaseModel):
    """Specification for a single artifact in the workflow DAG."""

    model_config = ConfigDict(extra="forbid")

    id: str
    generates: str
    instruction: str | None = None
    requires: list[str] = []
    gate: GateSpec | None = None
    lock: str | None = None


class WorkflowSchema(BaseModel):
    """Top-level workflow schema containing all artifacts."""

    model_config = ConfigDict(extra="forbid")

    version: int
    name: str
    description: str
    artifacts: list[ArtifactSpec]
