"""Public interface for the clasi.schemas package."""

from __future__ import annotations

import importlib.resources as _res
from pathlib import Path

import yaml as _yaml

from clasi.schemas.graph import ArtifactGraph
from clasi.schemas.models import ArtifactSpec, GateSpec, SchemaError, WorkflowSchema

__all__ = [
    "ArtifactGraph",
    "SchemaError",
    "GateSpec",
    "ArtifactSpec",
    "WorkflowSchema",
    "get_active_schema_path",
]

# Valid process names and their schema sub-directory names.
_PROCESS_SCHEMA_DIRS: dict[str, str] = {
    "se": "se-process",
    "solo": "solo-process",
}
_DEFAULT_PROCESS = "se"


def get_active_schema_path(project_root: Path | None = None) -> Path:
    """Return the path to the active workflow schema for *project_root*.

    Reads ``.clasi/config.yaml`` inside *project_root* and looks for a
    ``process:`` key.  Recognised values are ``"se"`` (default) and
    ``"solo"``.  Any unrecognised value falls back to ``"se"``.

    If *project_root* is ``None`` or the config file does not exist, the
    ``se`` schema is returned.

    Returns:
        Absolute :class:`~pathlib.Path` to the schema file bundled with the
        package (inside ``clasi/schemas/<process-dir>/schema.yaml``).
    """
    process = _DEFAULT_PROCESS

    if project_root is not None:
        config_path = Path(project_root) / ".clasi" / "config.yaml"
        if config_path.exists():
            try:
                data = _yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    raw = data.get("process", _DEFAULT_PROCESS)
                    if raw in _PROCESS_SCHEMA_DIRS:
                        process = raw
            except _yaml.YAMLError:
                pass  # fall back to default

    schema_dir = _PROCESS_SCHEMA_DIRS[process]
    schema_file: Path = Path(
        str(_res.files("clasi.schemas").joinpath(schema_dir, "schema.yaml"))
    )
    return schema_file
