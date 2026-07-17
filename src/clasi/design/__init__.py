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

__all__ = [
    "DesignPathError",
    "design_doc_slug",
    "readme_path_for",
    "system_doc_name",
]
