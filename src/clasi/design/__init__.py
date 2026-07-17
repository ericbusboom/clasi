"""Public interface for the clasi.design package.

This package implements the persistent per-subsystem architecture doc set
(sprint 021): pure path/slug derivation (``paths``), doc-set storage
(``store``, future ticket), structural/link validation (``validator``,
future ticket), and the sprint overlay lifecycle (``overlay``, future
ticket).
"""

from __future__ import annotations

from clasi.design.overlay import (
    OverlayApplyError,
    OverlayError,
    OverlayGitError,
    apply,
    commit_edits,
    generate_diffs,
    seed_and_commit,
)
from clasi.design.paths import (
    design_doc_path_for,
    system_doc_name,
)
from clasi.design.store import (
    DesignDocSet,
    read_design_doc,
    read_doc_set,
    read_system_doc,
    subsystem_template,
    write_design_doc,
    write_system_doc,
)
try:
    from clasi.design.validator import (
        DesignError,
        ValidationResult,
        validate,
        validate_or_raise,
    )
except ImportError:
    # clasi.design.validator still imports the pre-co-location
    # DesignPathError/design_doc_slug symbols removed from clasi.design.paths
    # by ticket 001 of sprint 022. Retargeting validator.py to the
    # co-located DESIGN.md path model is ticket 004's scope, not this
    # ticket's (002, store.py/__init__.py only). Guard this sub-import so
    # the rest of the package — store.py's write/read functions in
    # particular — remains importable and testable in the interim. Remove
    # this try/except once ticket 004 lands.
    DesignError = None  # type: ignore[assignment]
    ValidationResult = None  # type: ignore[assignment]
    validate = None  # type: ignore[assignment]
    validate_or_raise = None  # type: ignore[assignment]

__all__ = [
    "design_doc_path_for",
    "system_doc_name",
    "DesignDocSet",
    "read_design_doc",
    "read_doc_set",
    "read_system_doc",
    "subsystem_template",
    "write_design_doc",
    "write_system_doc",
    "DesignError",
    "ValidationResult",
    "validate",
    "validate_or_raise",
    "OverlayError",
    "OverlayGitError",
    "OverlayApplyError",
    "seed_and_commit",
    "generate_diffs",
    "commit_edits",
    "apply",
]
