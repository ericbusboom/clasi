"""Artifact dependency graph for workflow schemas."""

from __future__ import annotations

from clasi.schemas.models import ArtifactSpec, GateSpec, WorkflowSchema


class ArtifactGraph:
    """Read-only query interface over a loaded :class:`WorkflowSchema`.

    Accepts a fully validated and topologically-sorted ``WorkflowSchema``
    (as returned by :func:`clasi.schemas.loader.load`) and exposes query
    methods that the state DB and skill stubs can use.
    """

    def __init__(self, schema: WorkflowSchema) -> None:
        self._schema = schema
        # Index by ID for O(1) lookup; order is preserved in schema.artifacts.
        self._index: dict[str, ArtifactSpec] = {a.id: a for a in schema.artifacts}

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def phases(self) -> list[str]:
        """Return artifact IDs in topological order.

        The loader already sorts ``schema.artifacts``; this method simply
        returns the IDs in that order.
        """
        return [a.id for a in self._schema.artifacts]

    def artifact(self, id: str) -> ArtifactSpec:
        """Return the :class:`ArtifactSpec` with the given *id*.

        Raises :class:`KeyError` if no artifact with that ID exists.
        """
        try:
            return self._index[id]
        except KeyError:
            raise KeyError(f"No artifact with id {id!r}")

    def requires(self, id: str) -> list[str]:
        """Return the direct dependency IDs for artifact *id*.

        Raises :class:`KeyError` if *id* does not name a known artifact.
        """
        return list(self.artifact(id).requires)

    def gate_for(self, id: str) -> GateSpec | None:
        """Return the :class:`GateSpec` for artifact *id*, or ``None``.

        Raises :class:`KeyError` if *id* does not name a known artifact.
        """
        return self.artifact(id).gate

    def instruction_for(self, id: str) -> str | None:
        """Return the ``instruction`` field for artifact *id*, or ``None``.

        Raises :class:`KeyError` if *id* does not name a known artifact.
        """
        return self.artifact(id).instruction
