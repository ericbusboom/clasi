"""Validator for the persistent per-subsystem design doc set.

Mirrors ``clasi.schemas.loader``'s shape: an entry point (``validate``)
that runs an ordered sequence of independent, read-only checks and
collects *every* failure before returning/raising, so a caller sees all
problems in one pass rather than fixing them one at a time.

Two check groups:

1. **Canonical doc set structure** (always run): ``design.md`` present;
   one design doc per declared subsystem; every design doc's frontmatter
   ``readme_path`` resolves to an existing README; every subsystem
   README's frontmatter ``design_doc_path`` resolves to an existing
   design doc; no orphaned docs (a design doc in ``docs/design/`` with no
   matching source directory); no unmapped source roots (a subsystem
   source directory with no design doc).
2. **Sprint overlay** (run only when an overlay directory is given): every
   overlay ``.md`` filename (other than ``*.diff.md`` files themselves)
   matches an existing canonical doc's filename; overlay frontmatter
   references resolve; every overlay file has a corresponding
   ``<name>.diff.md`` that is not stale.

Message format contract
------------------------

Callers that consume ``ValidationResult.messages`` (e.g. the bootstrap
and skill-rework tickets) can rely on: each message is a single-line,
human-readable string naming the specific file(s) and defect involved —
never a generic "validation failed." ``DesignError`` (raised only by the
CLI/programmatic-strict callers, see :func:`validate_or_raise`) joins all
collected messages with newlines, so splitting its ``str()`` on ``"\\n"``
recovers the individual messages.

Staleness detection for overlay ``.diff.md`` files compares the SHA-256
content hash of the overlay ``.md`` file against a hash recorded in the
``.diff.md`` file's own frontmatter (``source_hash``) at the time the
diff was generated (see ``clasi.design.overlay``, ticket 005) — chosen
over mtime comparison because mtimes are not preserved across git
clones/checkouts and would produce false "stale" positives after a
fresh checkout of an up-to-date overlay.

Informational vs. error messages (sprint 021, ticket 011)
-----------------------------------------------------------

The orphan check in ``_check_subsystem_docs`` only applies to ``.md``
files under ``docs/design/`` (other than the system doc, ``design.md``)
whose frontmatter carries the *subsystem-doc shape* — both
``source_paths`` and ``readme_path`` keys present. This is the shape
:func:`clasi.design.store.write_design_doc` always writes.

A ``.md`` file in ``docs/design/`` without that shape (no frontmatter,
or frontmatter missing one or both of those keys) is not a subsystem
doc as far as this validator is concerned, and is therefore never
reported as an "Orphaned design doc" *error* — this covers non-subsystem
prose such as the project's frozen initiation docs (``overview.md``,
``specification.md``, ``usecases.md``, ``state-machines.md``,
``worktree-process.md``) living alongside the subsystem doc set.

It is, however, not silently ignored: it is recorded as a distinct
*informational* entry in ``ValidationResult.info``, separate from
``ValidationResult.messages``. This keeps a stale or corrupted
subsystem doc (frontmatter accidentally stripped) visible in validator
output rather than disappearing from view, while not failing
``ok``/the CLI exit code. ``ValidationResult.ok`` is defined purely off
``messages`` — ``info`` entries never affect it. A genuine orphan (a
file *with* the subsystem-doc frontmatter shape but no matching
declared subsystem) is still reported as an "Orphaned design doc" error
in ``messages``, exactly as before.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from clasi.artifact import Artifact
from clasi.design.paths import DesignPathError, design_doc_slug, system_doc_name
from clasi.design.store import read_doc_set

if TYPE_CHECKING:
    from clasi.project import Project


class DesignError(Exception):
    """Raised when the design doc set (or a sprint overlay) is invalid.

    ``str(error)`` joins every collected failure message with newlines —
    see the module docstring's "Message format contract."
    """


@dataclass
class ValidationResult:
    """Structured pass/fail result from :func:`validate`.

    Attributes:
        ok: ``True`` iff ``messages`` is empty.
        messages: One entry per independently-detected failure, each an
            actionable, specific string (see module docstring). Empty on
            success.
        info: One entry per independently-detected informational
            condition — currently, ``.md`` files under ``docs/design/``
            that lack the subsystem-doc frontmatter shape and are
            therefore not orphan-checked (see the module docstring's
            "Informational vs. error messages" section). Never affects
            ``ok`` or exit codes. Empty when there is nothing to report.
    """

    messages: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.messages


def _content_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Canonical doc set checks
# ---------------------------------------------------------------------------


def _check_system_doc_present(project: Project, messages: list[str]) -> None:
    system_doc = Artifact(project.design_dir / system_doc_name())
    if not system_doc.exists:
        messages.append(
            f"Missing top-level design document: {system_doc.path} does not exist."
        )


def _has_subsystem_doc_shape(frontmatter: dict) -> bool:
    """Return whether *frontmatter* carries the subsystem design-doc shape.

    The shape is both ``source_paths`` and ``readme_path`` keys present —
    the shape :func:`clasi.design.store.write_design_doc` always writes.
    Presence, not truthiness, is what's tested: ``write_system_doc`` sets
    ``readme_path`` to ``None`` for the (separately special-cased) system
    doc, and a subsystem doc could legitimately have an empty
    ``source_paths`` list, so a falsy-but-present value still counts as
    the shape. A ``.md`` file without this shape is not orphan-checked —
    see the module docstring.
    """
    return "source_paths" in frontmatter and "readme_path" in frontmatter


def _check_subsystem_docs(
    project: Project, messages: list[str], info: list[str]
) -> None:
    """Check one-doc-per-subsystem, bidirectional links, and orphans/unmapped roots."""
    doc_set = read_doc_set(project)
    design_dir = project.design_dir

    # --- Unmapped source roots: subsystem dir with no design doc ---
    for subsystem_path, doc in doc_set.subsystem_docs.items():
        if not doc.exists:
            messages.append(
                f"Unmapped source root: subsystem directory {subsystem_path} "
                f"has no design doc at {doc.path}."
            )

    # --- Design doc -> README backlink ---
    for subsystem_path, doc in doc_set.subsystem_docs.items():
        if not doc.exists:
            continue  # already reported above
        fm = doc.frontmatter
        readme_path_value = fm.get("readme_path")
        if not readme_path_value:
            messages.append(
                f"Design doc {doc.path} has no readme_path in its frontmatter "
                f"(expected a backlink to {subsystem_path / 'README.md'})."
            )
            continue
        readme = Artifact(Path(readme_path_value))
        if not readme.exists:
            messages.append(
                f"Design doc {doc.path} references readme_path "
                f"{readme_path_value!s} which does not exist."
            )

    # --- README -> design doc backlink ---
    for subsystem_path, readme in doc_set.readmes.items():
        if not readme.exists:
            messages.append(
                f"Subsystem {subsystem_path} has no README.md at {readme.path} "
                "linking back to its design doc."
            )
            continue
        fm = readme.frontmatter
        design_doc_path_value = fm.get("design_doc_path")
        if not design_doc_path_value:
            messages.append(
                f"README {readme.path} has no design_doc_path in its "
                "frontmatter (expected a backlink to its design doc)."
            )
            continue
        design_doc = Artifact(Path(design_doc_path_value))
        if not design_doc.exists:
            messages.append(
                f"README {readme.path} references design_doc_path "
                f"{design_doc_path_value!s} which does not exist."
            )

    # --- Filename collisions: two subsystems, or a subsystem and the
    # system doc, resolving to the same expected filename. Computed
    # individually (not via set-union) so a collision is detected and
    # reported explicitly instead of silently collapsing into one set
    # entry, which would let both "system doc present" and "subsystem has
    # a doc" checks pass even though only one file can physically exist.
    name_to_subsystems: dict[str, list[Path]] = {}
    for subsystem_path in doc_set.subsystem_docs:
        try:
            slug = design_doc_slug(subsystem_path, project.sources)
        except DesignPathError as exc:
            messages.append(
                f"Cannot derive a design-doc filename for subsystem "
                f"{subsystem_path}: {exc}"
            )
            continue
        name_to_subsystems.setdefault(slug, []).append(subsystem_path)

    system_name = system_doc_name()
    for name, subsystem_paths in sorted(name_to_subsystems.items()):
        if name == system_name:
            for subsystem_path in subsystem_paths:
                messages.append(
                    f"Design doc filename collision: subsystem "
                    f"{subsystem_path} resolves to {name!r}, which is the "
                    "reserved top-level system document name."
                )
        if len(subsystem_paths) > 1:
            joined = ", ".join(str(p) for p in subsystem_paths)
            messages.append(
                f"Design doc filename collision: subsystems {joined} all "
                f"resolve to {name!r}."
            )

    expected_names = {system_name} | set(name_to_subsystems)

    # --- Orphaned docs: doc in docs/design/ with no matching source dir ---
    if not design_dir.is_dir():
        return

    for entry in sorted(design_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue
        if entry.name == system_name:
            continue
        if not _has_subsystem_doc_shape(Artifact(entry).frontmatter):
            info.append(
                f"Non-subsystem doc (no frontmatter shape recognized): "
                f"{entry} — not orphan-checked."
            )
            continue
        if entry.name not in expected_names:
            messages.append(
                f"Orphaned design doc: {entry} does not correspond to any "
                "declared subsystem source directory."
            )


def _check_canonical_doc_set(
    project: Project, messages: list[str], info: list[str]
) -> None:
    _check_system_doc_present(project, messages)
    _check_subsystem_docs(project, messages, info)


# ---------------------------------------------------------------------------
# Sprint overlay checks
# ---------------------------------------------------------------------------


def _canonical_doc_names(project: Project) -> set[str]:
    doc_set = read_doc_set(project)
    names = {system_doc_name()}
    for subsystem_path in doc_set.subsystem_docs:
        try:
            names.add(design_doc_slug(subsystem_path, project.sources))
        except DesignPathError:
            continue
    return names


def _check_overlay(project: Project, overlay_dir: Path, messages: list[str]) -> None:
    if not overlay_dir.is_dir():
        messages.append(f"Sprint overlay directory {overlay_dir} does not exist.")
        return

    canonical_names = _canonical_doc_names(project)

    overlay_files = sorted(
        p
        for p in overlay_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and not p.name.endswith(".diff.md")
    )

    for overlay_file in overlay_files:
        # --- Filename matches an existing canonical doc ---
        if overlay_file.name not in canonical_names:
            messages.append(
                f"Sprint overlay file {overlay_file} does not match any "
                "existing canonical design doc filename."
            )

        # --- Frontmatter references resolve ---
        overlay_artifact = Artifact(overlay_file)
        fm = overlay_artifact.frontmatter
        for fm_key in ("source_paths", "readme_path"):
            if fm_key not in fm:
                continue
            value = fm[fm_key]
            candidates = value if isinstance(value, list) else [value]
            for candidate in candidates:
                if not candidate:
                    continue
                candidate_path = Path(candidate)
                if not candidate_path.exists():
                    messages.append(
                        f"Sprint overlay file {overlay_file} has "
                        f"{fm_key}={candidate!s} which does not resolve to "
                        "an existing file."
                    )

        # --- Corresponding .diff.md exists and is not stale ---
        diff_file = overlay_file.with_suffix("").with_suffix(".diff.md")
        if not diff_file.exists():
            messages.append(
                f"Sprint overlay file {overlay_file} has no corresponding "
                f"diff file {diff_file} (or it has not been generated)."
            )
            continue

        current_hash = _content_hash(overlay_file.read_text(encoding="utf-8"))
        diff_artifact = Artifact(diff_file)
        recorded_hash = diff_artifact.frontmatter.get("source_hash")
        if recorded_hash != current_hash:
            messages.append(
                f"Sprint overlay diff {diff_file} is stale: its recorded "
                f"source_hash does not match the current content of "
                f"{overlay_file}. Regenerate the diff."
            )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def validate(project: Project, overlay_dir: str | Path | None = None) -> ValidationResult:
    """Validate *project*'s canonical design doc set, and optionally a sprint overlay.

    Runs the canonical doc-set structure/link checks unconditionally, then
    the sprint-overlay checks when *overlay_dir* is given. All checks run
    to completion — every independent failure is collected, not just the
    first — matching ``clasi.schemas.loader.load``'s "collect all
    failures" behavior.

    Args:
        project: The project whose ``sources``/``design_dir`` define the
            expected doc set.
        overlay_dir: Optional path to a sprint's
            ``clasi/sprints/NNN-slug/design/`` directory to additionally
            validate. ``None`` skips overlay checks entirely.

    Returns:
        A :class:`ValidationResult`; check ``.ok`` or inspect
        ``.messages``. Never raises on validation failure — see
        :func:`validate_or_raise` for a raising variant.
    """
    messages: list[str] = []
    info: list[str] = []
    _check_canonical_doc_set(project, messages, info)
    if overlay_dir is not None:
        _check_overlay(project, Path(overlay_dir), messages)
    return ValidationResult(messages=messages, info=info)


def validate_or_raise(project: Project, overlay_dir: str | Path | None = None) -> ValidationResult:
    """Like :func:`validate`, but raises :class:`DesignError` on failure.

    The exact same underlying checks as :func:`validate` — this is a thin
    raising wrapper, used by the CLI entry point. Both ``validate`` and
    ``validate_or_raise`` share the same check functions with no logic
    duplicated between the CLI and MCP tool paths.
    """
    result = validate(project, overlay_dir)
    if not result.ok:
        raise DesignError("\n".join(result.messages))
    return result
