"""Design doc store: read/write the persistent ``docs/design/`` doc set.

Thin wrapper over ``Artifact`` (``clasi.artifact``) specialized to the two
document shapes this sprint introduces: the top-level system document
(``design.md``) and per-subsystem design docs, plus the subsystem
``README.md`` files that link back to them. Mirrors the established
``Artifact``-wrapper pattern used elsewhere in the codebase (see
``clasi.issue.Issue``, ``clasi.ticket.Ticket``).

This module knows the *shape* of a design doc and a subsystem README (what
frontmatter fields they carry) but does not:

- Validate cross-doc consistency (bidirectional links resolving, no
  orphaned docs, etc.) — that is ``clasi.design.validator`` (ticket 004).
- Touch git — that is ``clasi.design.overlay`` (ticket 005).

Frontmatter contract
---------------------

**Design doc** (``docs/design/design.md`` or
``docs/design/<slug>.md``):

- ``source_paths``: list[str] — repo-relative source path(s) this doc
  describes. For the system document this is typically every declared
  source root; for a subsystem doc it is normally a single entry.
- ``readme_path``: str | None — repo-relative path to the subsystem's
  ``README.md`` that links back to this doc. ``None``/absent for the
  system document, which has no single owning subsystem directory.

**Subsystem README** (``<subsystem>/README.md``):

- ``subsystem``: str — the subsystem's name (conventionally its
  directory name).
- ``description``: str — a one-line description of the subsystem.
- ``design_doc_path``: str — repo-relative path to the subsystem's
  design doc in ``docs/design/``.

Overwrite semantics
--------------------

``write_design_doc``, ``write_readme``, and ``write_system_doc`` are
**full-overwrite** operations: each call replaces the entire frontmatter
and body content of the target file, matching ``Artifact.write``'s own
overwrite-in-place contract. This module does not merge new content into
an existing document's body — a bootstrap re-run or a careless call will
silently replace hand-edited body content.

Callers that must not destroy existing content (e.g. a bootstrap skill
re-running against a subsystem that already has a hand-edited README)
are responsible for reading the existing document first (``Artifact``/
``read_design_doc``/``read_readme``) and deciding whether to preserve or
merge its body before calling the write functions here. No merge logic
is implemented in this module — full-copy overwrite is the only mode it
offers, consistent with the "agents write whole documents reliably"
decision recorded in the sprint's architecture (Design Rationale,
sprint.md section 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, TYPE_CHECKING

from clasi.artifact import Artifact
from clasi.design.paths import design_doc_slug, readme_path_for, system_doc_name

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
    """Maps each subsystem source path to its design-doc ``Artifact``."""
    readmes: dict[Path, Artifact]
    """Maps each subsystem source path to its README ``Artifact``."""


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
    directories, derives each one's canonical design-doc filename via
    ``clasi.design.paths.design_doc_slug``, and returns ``Artifact``
    handles for the system document, every subsystem design doc, and
    every subsystem README. Handles are returned whether or not the
    underlying files exist yet (check ``Artifact.exists``) — this
    function only knows the *expected* shape of the doc set, not whether
    it has been written.

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
    readmes: dict[Path, Artifact] = {}

    for root in sources:
        for subsystem_path in _subsystem_dirs(root):
            slug = design_doc_slug(subsystem_path, sources)
            subsystem_docs[subsystem_path] = Artifact(design_dir / slug)
            readmes[subsystem_path] = Artifact(readme_path_for(subsystem_path))

    return DesignDocSet(
        system_doc=system_doc,
        subsystem_docs=subsystem_docs,
        readmes=readmes,
    )


def write_design_doc(
    project: Project,
    subsystem_path: Path,
    content: str,
    *,
    extra_frontmatter: dict[str, Any] | None = None,
) -> Artifact:
    """Write a subsystem design doc to ``docs/design/<slug>.md``.

    Overwrites the entire file (frontmatter and body) if it already
    exists — see the module docstring's "Overwrite semantics".

    Args:
        project: The owning project (supplies ``sources`` and
            ``design_dir``).
        subsystem_path: Absolute, resolved path to the subsystem's
            source directory (must be located under one of
            ``project.sources`` or ``design_doc_slug`` raises
            ``DesignPathError``).
        content: The design doc's full markdown body.
        extra_frontmatter: Optional additional frontmatter fields merged
            in alongside the required ``source_paths``/``readme_path``
            fields. Caller-supplied keys do not override the two
            required fields.

    Returns:
        The ``Artifact`` that was written.
    """
    sources = project.sources
    slug = design_doc_slug(subsystem_path, sources)
    doc_path = project.design_dir / slug
    readme_path = readme_path_for(subsystem_path)

    frontmatter: dict[str, Any] = dict(extra_frontmatter or {})
    frontmatter["source_paths"] = [str(subsystem_path)]
    frontmatter["readme_path"] = str(readme_path)

    artifact = Artifact(doc_path)
    artifact.write(frontmatter, content)
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
    frontmatter["readme_path"] = None

    artifact = Artifact(project.design_dir / system_doc_name())
    artifact.write(frontmatter, content)
    return artifact


def write_readme(
    subsystem_path: Path,
    project: Project,
    *,
    name: str,
    description: str,
    content: str = "",
    extra_frontmatter: dict[str, Any] | None = None,
) -> Artifact:
    """Write a subsystem ``README.md`` with design-doc-linking frontmatter.

    Overwrites the entire file (frontmatter and body) if it already
    exists — see the module docstring's "Overwrite semantics". Callers
    that must preserve an existing README's hand-edited body should read
    it first (``Artifact(readme_path_for(subsystem_path)).content``) and
    pass the preserved text as *content*; this function performs no
    merge on its own.

    Args:
        subsystem_path: Absolute, resolved path to the subsystem's
            source directory. The README is written to
            ``<subsystem_path>/README.md``.
        project: The owning project (supplies ``sources`` to derive the
            design-doc backlink).
        name: The subsystem's name (frontmatter ``subsystem`` field).
        description: A one-line description of the subsystem
            (frontmatter ``description`` field).
        content: The README's full markdown body (default empty).
        extra_frontmatter: Optional additional frontmatter fields merged
            in alongside the required fields. Caller-supplied keys do
            not override the required fields.

    Returns:
        The ``Artifact`` that was written.
    """
    sources = project.sources
    slug = design_doc_slug(subsystem_path, sources)
    design_doc_path = project.design_dir / slug

    frontmatter: dict[str, Any] = dict(extra_frontmatter or {})
    frontmatter["subsystem"] = name
    frontmatter["description"] = description
    frontmatter["design_doc_path"] = str(design_doc_path)

    artifact = Artifact(readme_path_for(subsystem_path))
    artifact.write(frontmatter, content)
    return artifact


def read_design_doc(project: Project, subsystem_path: Path) -> Artifact:
    """Return the ``Artifact`` handle for a subsystem's design doc.

    Does not require the file to exist — check ``Artifact.exists``
    before reading ``.frontmatter``/``.content``.
    """
    slug = design_doc_slug(subsystem_path, project.sources)
    return Artifact(project.design_dir / slug)


def read_readme(subsystem_path: Path) -> Artifact:
    """Return the ``Artifact`` handle for a subsystem's ``README.md``.

    Does not require the file to exist — check ``Artifact.exists``
    before reading ``.frontmatter``/``.content``.
    """
    return Artifact(readme_path_for(subsystem_path))


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
    It carries placeholder YAML frontmatter (``source_paths``,
    ``readme_path``) matching this module's design-doc frontmatter
    contract, plus the HTML-comment authoring guidance and section
    structure an agent fills in.

    The **bootstrap-design** skill instructs agents to start every new
    subsystem design doc from this template's body, replacing the
    placeholder frontmatter values with the real subsystem
    ``source_paths``/``readme_path`` before writing via
    :func:`write_design_doc`.

    Returns:
        The template file's full text, including its placeholder
        frontmatter block.
    """
    template_path = resources.files("clasi.design.templates") / "subsystem-design.md"
    return template_path.read_text(encoding="utf-8")
