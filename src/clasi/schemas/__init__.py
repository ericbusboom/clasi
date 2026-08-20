"""Public interface for the clasi.schemas package."""

from __future__ import annotations

import importlib.resources as _res
from pathlib import Path

import yaml as _yaml

__all__ = [
    "ArtifactGraph",
    "SchemaError",
    "GateSpec",
    "ArtifactSpec",
    "WorkflowSchema",
    "get_active_schema_path",
]

# ``clasi.schemas.graph``/``clasi.schemas.models`` are Pydantic-model-backed
# and cost about 60-70ms of import time (measured via
# ``python -X importtime``, sprint 027 / ticket 003), dominated by importing
# pydantic itself. Several callers only need THIS PACKAGE to be importable
# so a resource path under it can be resolved (e.g.
# ``state_machine.loader``'s ``importlib.resources.files("clasi.schemas")``
# lookup, and ``state_db_class``'s schema-graph resource path) — they never
# touch ``ArtifactGraph``/``SchemaError``/etc. at all. Eagerly importing
# ``.graph``/``.models`` here meant EVERY such caller paid the pydantic
# import cost merely by causing this package's ``__init__`` to run, even on
# the hot per-hook-invocation status-inject path where nothing in this
# package's public surface is ever used.
#
# PEP 562 module ``__getattr__`` defers the submodule imports until one of
# these names is actually accessed as an attribute (``clasi.schemas.X`` or
# ``from clasi.schemas import X``), then caches the resolved value as a
# normal module global so repeat access is a plain attribute lookup, not a
# re-import. Behavior for every existing caller of these names is
# unchanged — only the timing of the underlying import moves from
# "always, at package-import time" to "on first real use".
_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "ArtifactGraph": ("clasi.schemas.graph", "ArtifactGraph"),
    "SchemaError": ("clasi.schemas.models", "SchemaError"),
    "GateSpec": ("clasi.schemas.models", "GateSpec"),
    "ArtifactSpec": ("clasi.schemas.models", "ArtifactSpec"),
    "WorkflowSchema": ("clasi.schemas.models", "WorkflowSchema"),
}


def __getattr__(name: str):
    """PEP 562 lazy resolution for the Pydantic-backed re-exports above."""
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module_name, attr_name = target
    value = getattr(importlib.import_module(module_name), attr_name)
    globals()[name] = value
    return value

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
