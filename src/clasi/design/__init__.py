"""Public interface for the clasi.design package.

This package implements the persistent per-subsystem architecture doc set
(sprint 021): pure path/slug derivation (``paths``), doc-set storage
(``store``, future ticket), structural/link validation (``validator``,
future ticket), and the sprint overlay lifecycle (``overlay``, future
ticket).
"""

from __future__ import annotations

from clasi.design.paths import (
    DesignPathError,
    design_doc_slug,
    readme_path_for,
    system_doc_name,
)
from clasi.design.store import (
    DesignDocSet,
    read_design_doc,
    read_doc_set,
    read_readme,
    read_system_doc,
    write_design_doc,
    write_readme,
    write_system_doc,
)

__all__ = [
    "DesignPathError",
    "design_doc_slug",
    "readme_path_for",
    "system_doc_name",
    "DesignDocSet",
    "read_design_doc",
    "read_doc_set",
    "read_readme",
    "read_system_doc",
    "write_design_doc",
    "write_readme",
    "write_system_doc",
]
