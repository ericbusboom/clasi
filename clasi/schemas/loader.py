"""Loader for workflow schema YAML files.

This is the only module that parses schema YAML. No other module may import
YAML parsing for schemas.

Depends only on stdlib, PyYAML, Pydantic, and clasi.schemas.models.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import yaml
from pydantic import ValidationError

from clasi.schemas.models import ArtifactSpec, SchemaError, WorkflowSchema

# Registry of valid gate kinds.
_VALID_GATE_KINDS: frozenset[str] = frozenset(
    {"stakeholder-review", "review", "per-ticket"}
)


def load_from_dict(data: dict) -> WorkflowSchema:
    """Validate and structurally check a workflow schema from an already-parsed dict.

    Runs the same validation and structural checks as :func:`load` but skips
    YAML file I/O.  Useful in tests that construct schema dicts in-memory.

    Raises :class:`SchemaError` on any validation or structural failure.
    """
    if not isinstance(data, dict):
        raise SchemaError(f"Schema data must be a mapping, got {type(data).__name__}")

    # --- Pydantic validation ---
    try:
        schema = WorkflowSchema.model_validate(data)
    except ValidationError as exc:
        raise SchemaError(f"Schema validation error: {exc}") from exc

    artifacts: list[ArtifactSpec] = schema.artifacts

    # --- Duplicate ID check ---
    seen_ids: set[str] = set()
    for artifact in artifacts:
        if artifact.id in seen_ids:
            raise SchemaError(f"Duplicate artifact id {artifact.id!r}")
        seen_ids.add(artifact.id)

    # --- Missing requires references ---
    for artifact in artifacts:
        for req in artifact.requires:
            if req not in seen_ids:
                raise SchemaError(
                    f"Artifact {artifact.id!r} requires unknown artifact {req!r}"
                )

    # --- Unknown gate kinds ---
    for artifact in artifacts:
        if artifact.gate is not None and artifact.gate.kind not in _VALID_GATE_KINDS:
            raise SchemaError(
                f"Artifact {artifact.id!r} has unknown gate kind {artifact.gate.kind!r}; "
                f"valid kinds are {sorted(_VALID_GATE_KINDS)}"
            )

    # --- Topological sort with cycle detection (Kahn's algorithm) ---
    sorted_artifacts = _topo_sort(artifacts, Path("<in-memory>"))

    return schema.model_copy(update={"artifacts": sorted_artifacts})


def load(path: str | Path) -> WorkflowSchema:
    """Load a workflow schema from a YAML file.

    Parses the YAML at *path*, validates it with Pydantic, then runs
    structural checks in this order:

    1. Duplicate artifact IDs.
    2. Missing ``requires`` references.
    3. Unknown ``gate.kind`` values.
    4. Cycles in the dependency graph (Kahn's algorithm).

    Returns a :class:`WorkflowSchema` with ``artifacts`` in topological order.
    Raises :class:`SchemaError` on any validation or structural failure.
    """
    path = Path(path)

    # --- Parse YAML ---
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise SchemaError(f"YAML parse error in {path}: {exc}") from exc
    except OSError as exc:
        raise SchemaError(f"Cannot read schema file {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise SchemaError(f"Schema file {path} must contain a YAML mapping, got {type(raw).__name__}")

    # --- Pydantic validation ---
    try:
        schema = WorkflowSchema.model_validate(raw)
    except ValidationError as exc:
        raise SchemaError(f"Schema validation error in {path}: {exc}") from exc

    artifacts: list[ArtifactSpec] = schema.artifacts

    # --- Duplicate ID check ---
    seen_ids: set[str] = set()
    for artifact in artifacts:
        if artifact.id in seen_ids:
            raise SchemaError(f"Duplicate artifact id {artifact.id!r} in {path}")
        seen_ids.add(artifact.id)

    # --- Missing requires references ---
    for artifact in artifacts:
        for req in artifact.requires:
            if req not in seen_ids:
                raise SchemaError(
                    f"Artifact {artifact.id!r} requires unknown artifact {req!r} in {path}"
                )

    # --- Unknown gate kinds ---
    for artifact in artifacts:
        if artifact.gate is not None and artifact.gate.kind not in _VALID_GATE_KINDS:
            raise SchemaError(
                f"Artifact {artifact.id!r} has unknown gate kind {artifact.gate.kind!r} in {path}; "
                f"valid kinds are {sorted(_VALID_GATE_KINDS)}"
            )

    # --- Topological sort with cycle detection (Kahn's algorithm) ---
    sorted_artifacts = _topo_sort(artifacts, path)

    return schema.model_copy(update={"artifacts": sorted_artifacts})


def _topo_sort(artifacts: list[ArtifactSpec], path: Path) -> list[ArtifactSpec]:
    """Return artifacts in topological order using Kahn's algorithm.

    Raises :class:`SchemaError` if a cycle is detected, identifying the
    artifact IDs involved.
    """
    id_to_artifact: dict[str, ArtifactSpec] = {a.id: a for a in artifacts}

    # in-degree: number of prerequisites not yet processed
    in_degree: dict[str, int] = {a.id: len(a.requires) for a in artifacts}

    # adjacency: for each node, the nodes that depend on it
    dependents: dict[str, list[str]] = {a.id: [] for a in artifacts}
    for artifact in artifacts:
        for req in artifact.requires:
            dependents[req].append(artifact.id)

    # Start with nodes that have no prerequisites
    queue: deque[str] = deque(aid for aid, deg in in_degree.items() if deg == 0)
    # Preserve relative order among nodes at the same level by sorting
    # alphabetically so the output is deterministic.
    queue = deque(sorted(queue))

    result: list[ArtifactSpec] = []

    while queue:
        current = queue.popleft()
        result.append(id_to_artifact[current])
        next_batch: list[str] = []
        for dep in dependents[current]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                next_batch.append(dep)
        queue.extend(sorted(next_batch))

    if len(result) != len(artifacts):
        # Identify nodes still in a cycle (those with in_degree > 0)
        cycle_nodes = sorted(aid for aid, deg in in_degree.items() if deg > 0)
        raise SchemaError(
            f"Cycle detected in artifact dependency graph in {path}: "
            f"involved artifact ids are {cycle_nodes}"
        )

    return result
