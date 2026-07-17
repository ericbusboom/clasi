"""Design doc store: read/write the co-located ``DESIGN.md`` doc set.

Thin wrapper over ``Artifact`` (``clasi.artifact``) specialized to the two
document shapes this sprint introduces: the top-level system document
(``docs/design/design.md``) and per-subsystem design docs co-located as
``<subsystem_path>/DESIGN.md``. Mirrors the established ``Artifact``-wrapper
pattern used elsewhere in the codebase (see ``clasi.issue.Issue``,
``clasi.ticket.Ticket``).

This module knows the *shape* of a design doc but does not:

- Validate cross-doc consistency (orphaned docs, staleness, etc.) — that
  is ``clasi.design.validator`` (ticket 004).
- Touch git — that is ``clasi.design.overlay`` (ticket 005).

Frontmatter contract
---------------------

**Subsystem design doc** (``<subsystem_path>/DESIGN.md``): no frontmatter
is required or auto-populated. A ``DESIGN.md`` with a bare markdown body
and no ``---`` block at all is a valid document — the doc's location
*is* its identity (``clasi.design.paths.design_doc_path_for``), so there
is nothing to backlink and nothing that must be declared. Callers may
still pass ``extra_frontmatter`` to attach optional metadata; when given,
it is written as-is via the normal ``---``-delimited frontmatter block.

**System doc** (``docs/design/design.md``):

- ``source_paths``: list[str] — repo-relative path(s) of every declared
  source root, since the system doc has no single owning subsystem.

Overwrite semantics
--------------------

``write_design_doc`` and ``write_system_doc`` are **full-overwrite**
operations: each call replaces the entire content of the target file,
matching ``Artifact.write``'s own overwrite-in-place contract. This
module does not merge new content into an existing document's body — a
bootstrap re-run or a careless call will silently replace hand-edited
body content.

Callers that must not destroy existing content are responsible for
reading the existing document first (``Artifact``/``read_design_doc``)
and deciding whether to preserve or merge its body before calling the
write functions here. No merge logic is implemented in this module —
full-copy overwrite is the only mode it offers, consistent with the
"agents write whole documents reliably" decision recorded in the
sprint's architecture (Design Rationale, sprint.md section 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, TYPE_CHECKING

from clasi.artifact import Artifact
from clasi.design.paths import design_doc_path_for, system_doc_name

if TYPE_CHECKING:
    from clasi.project import Project


@dataclass(frozen=True)
class DesignDocSet:
    """Enumeration of the expected canonical design doc set for a project.

    Handles returned here are not guaranteed to exist on disk yet —
    existence checking is the validator's job (ticket 004). This is a
    pure enumeration over ``Project.sources`` and the source tree's
    top-level subsystem directories.
    """

    system_doc: Artifact
    subsystem_docs: dict[Path, Artifact]
    """Maps each subsystem source path to its ``DESIGN.md`` ``Artifact``."""


def _subsystem_dirs(source_root: Path) -> list[Path]:
    """Return the top-level subsystem directories under *source_root*.

    Only immediate subdirectories of the root count as subsystems —
    nested directories belong to the subsystem that contains them (per
    the issue: "the top-level directory that holds the code;
    subdirectories belong to the subsystem"). Hidden directories
    (leading ``.``) and ``__pycache__`` are excluded as non-subsystems.
    Returns an empty list if the root does not exist or has no
    subdirectories — this function does not require the source tree to
    exist yet, matching the doc-set enumeration's "not necessarily
    existing" contract.
    """
    if not source_root.is_dir():
        return []
    return sorted(
        p
        for p in source_root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__"
    )


def read_doc_set(project: Project) -> DesignDocSet:
    """Enumerate the expected canonical design doc set for *project*.

    Walks each of ``project.sources`` for its top-level subsystem
    directories and returns ``Artifact`` handles for the system document
    and every subsystem's co-located ``DESIGN.md``. Handles are returned
    whether or not the underlying files exist yet (check
    ``Artifact.exists``) — this function only knows the *expected* shape
    of the doc set, not whether it has been written.

    Args:
        project: The project whose ``sources`` config and ``design_dir``
            are used to derive the expected doc set.

    Returns:
        A ``DesignDocSet`` with the system doc, and one entry per
        subsystem directory found under every declared source root.
    """
    design_dir = project.design_dir
    sources = project.sources

    system_doc = Artifact(design_dir / system_doc_name())

    subsystem_docs: dict[Path, Artifact] = {}

    for root in sources:
        for subsystem_path in _subsystem_dirs(root):
            subsystem_docs[subsystem_path] = Artifact(
                design_doc_path_for(subsystem_path)
            )

    return DesignDocSet(
        system_doc=system_doc,
        subsystem_docs=subsystem_docs,
    )


def write_design_doc(
    project: Project,
    subsystem_path: Path,
    content: str,
    *,
    extra_frontmatter: dict[str, Any] | None = None,
) -> Artifact:
    """Write a subsystem design doc to ``<subsystem_path>/DESIGN.md``.

    Overwrites the entire file if it already exists — see the module
    docstring's "Overwrite semantics". No frontmatter is required or
    auto-populated: there is nothing to backlink, since the doc's
    location under ``subsystem_path`` already is its identity
    (``clasi.design.paths.design_doc_path_for``). When *extra_frontmatter*
    is omitted, the file is written as a bare markdown body with no
    ``---`` block at all.

    Args:
        project: Unused by this function directly; accepted for
            interface symmetry with ``write_system_doc`` and because
            future callers may need it for validation. Retained rather
            than dropped to avoid churning every call site twice within
            the same sprint (validator/overlay tickets still land).
        subsystem_path: Absolute, resolved path to the subsystem's
            source directory. The doc is written to
            ``subsystem_path / "DESIGN.md"``.
        content: The design doc's full markdown body.
        extra_frontmatter: Optional additional frontmatter fields. If
            given (even as an empty dict is not the same as ``None``),
            the file is written with a ``---``-delimited frontmatter
            block containing exactly these fields. If omitted
            (``None``), no frontmatter block is written at all.

    Returns:
        The ``Artifact`` that was written.
    """
    del project  # Unused: doc path is fully determined by subsystem_path.
    doc_path = design_doc_path_for(subsystem_path)
    artifact = Artifact(doc_path)

    if extra_frontmatter is None:
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(content, encoding="utf-8")
    else:
        artifact.write(dict(extra_frontmatter), content)

    return artifact


def write_system_doc(
    project: Project,
    content: str,
    *,
    extra_frontmatter: dict[str, Any] | None = None,
) -> Artifact:
    """Write the top-level system design doc to ``docs/design/design.md``.

    Overwrites the entire file (frontmatter and body) if it already
    exists — see the module docstring's "Overwrite semantics".

    Args:
        project: The owning project (supplies ``sources`` and
            ``design_dir``).
        content: The system doc's full markdown body.
        extra_frontmatter: Optional additional frontmatter fields merged
            in alongside the required ``source_paths`` field.
            Caller-supplied keys do not override it.

    Returns:
        The ``Artifact`` that was written.
    """
    frontmatter: dict[str, Any] = dict(extra_frontmatter or {})
    frontmatter["source_paths"] = [str(root) for root in project.sources]

    artifact = Artifact(project.design_dir / system_doc_name())
    artifact.write(frontmatter, content)
    return artifact


def read_design_doc(project: Project, subsystem_path: Path) -> Artifact:
    """Return the ``Artifact`` handle for a subsystem's ``DESIGN.md``.

    Does not require the file to exist — check ``Artifact.exists``
    before reading ``.frontmatter``/``.content``.
    """
    del project  # Unused: doc path is fully determined by subsystem_path.
    return Artifact(design_doc_path_for(subsystem_path))


def read_system_doc(project: Project) -> Artifact:
    """Return the ``Artifact`` handle for the top-level ``design.md``.

    Does not require the file to exist — check ``Artifact.exists``
    before reading ``.frontmatter``/``.content``.
    """
    return Artifact(project.design_dir / system_doc_name())


def subsystem_template() -> str:
    """Return the packaged subsystem design-doc template's full text.

    The template (``clasi/design/templates/subsystem-design.md``) ships
    as package data (see ``pyproject.toml``'s
    ``[tool.setuptools.package-data]``) so it is available regardless of
    the caller's working directory or install mode (editable or wheel).
    The template carries no frontmatter block — a co-located
    ``DESIGN.md`` requires none, since its location under the subsystem's
    own source directory is its identity. This function returns the
    packaged file's HTML-comment authoring guidance and section structure
    verbatim for an agent to fill in.

    The **bootstrap-design** skill instructs agents to start every new
    subsystem design doc from this template's body before writing via
    :func:`write_design_doc`.

    Returns:
        The template file's full text, including its placeholder
        frontmatter block.
    """
    template_path = resources.files("clasi.design.templates") / "subsystem-design.md"
    return template_path.read_text(encoding="utf-8")
