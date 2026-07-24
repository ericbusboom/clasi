"""Validator for the persistent per-subsystem design doc set.

Mirrors ``clasi.schemas.loader``'s shape: an entry point (``validate``)
that runs an ordered sequence of independent, read-only checks and
collects *every* failure before returning/raising, so a caller sees all
problems in one pass rather than fixing them one at a time.

Two check groups:

1. **Canonical doc set structure** (always run): ``design.md`` present;
   every declared subsystem directory has a co-located ``DESIGN.md`` that
   exists and is non-empty; no unmapped source roots (a subsystem source
   directory with no ``DESIGN.md``); no stray ``DESIGN.md`` under a
   directory that isn't a recognized subsystem.
2. **Sprint overlay** (run only when an overlay directory is given): every
   overlay ``.md`` file (other than ``*.diff.md`` files themselves) has a
   recorded canonical target in the overlay's ``_sources.json`` manifest
   (written by ``clasi.design.overlay.seed_and_commit``) that resolves to
   a real, known doc in the project's doc set — resolution is by manifest
   entry, never by matching the overlay file's own basename, since
   co-located subsystem docs can share the basename ``DESIGN.md``;
   overlay frontmatter references resolve; every overlay file has a
   corresponding ``<name>.diff.md`` that is not stale.

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
diff was generated (see ``clasi.design.overlay``) — chosen over mtime
comparison because mtimes are not preserved across git clones/checkouts
and would produce false "stale" positives after a fresh checkout of an
up-to-date overlay.

Co-located model (sprint 022)
------------------------------

As of sprint 022, a subsystem's design doc lives at
``<subsystem_path>/DESIGN.md`` — the doc's location *is* its identity
(``clasi.design.paths.design_doc_path_for``). There is no README, no
frontmatter-based backlink between a design doc and anything else, no
slug derivation, and therefore no filename-collision possibility between
subsystems (each has its own directory). The remaining structural
checks are:

- Every declared source root has its own required root-level
  ``DESIGN.md`` overview that exists and is non-empty, and every declared
  subsystem's ``DESIGN.md`` exists and is non-empty ("missing design
  doc").
- No stray ``DESIGN.md`` exists under a source root at a path other than
  a recognized expected doc path — the root's own overview doc or a
  subsystem's own doc — e.g. one nested a level too deep, or inside a
  hidden/``__pycache__`` directory ``store.py`` deliberately does not
  enumerate as a subsystem ("orphaned doc", narrowed in scope from the
  pre-co-location flat-``docs/design/`` version of this check).

The five project-level docs that still live in ``docs/design/``
alongside the system doc (``overview.md``, ``specification.md``,
``usecases.md``, ``state-machines.md``, ``worktree-process.md``) are not
part of the co-located per-subsystem doc set — they have no frontmatter
shape to recognize and no source directory to co-locate into. They are
never reported as orphan errors; each is recorded as a distinct
informational entry in ``ValidationResult.info`` instead (unchanged
behavior from the pre-co-location validator, carried forward per this
ticket).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from clasi.artifact import Artifact
from clasi.design.paths import SUBSYSTEM_DOC_NAME, system_doc_name
from clasi.design.store import read_doc_set

if TYPE_CHECKING:
    from clasi.project import Project

_SOURCES_MANIFEST_NAME = "_sources.json"
"""Filename of the seed-time overlay-file -> canonical-path manifest.

Matches ``clasi.design.overlay._SOURCES_MANIFEST_NAME`` exactly — both
modules read/write the same file, written once by
``clasi.design.overlay.seed_and_commit`` and consulted here (read-only)
and by ``clasi.design.overlay.apply`` (also read-only) to resolve an
overlay file's canonical target without matching on basename.
"""


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
            other than the system doc (the 5 project-level docs, e.g.
            ``overview.md``) — see the module docstring's "Co-located
            model" section. Never affects ``ok`` or exit codes. Empty
            when there is nothing to report.
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


def _check_subsystem_docs(
    project: Project, messages: list[str], info: list[str]
) -> None:
    """Check one DESIGN.md per subsystem: existence and non-emptiness.

    Also checks for stray ``DESIGN.md`` files under a source root that
    don't correspond to any recognized subsystem's own doc path (e.g.
    nested one level too deep, or inside a directory ``store.py``
    deliberately excludes from subsystem enumeration) — the narrowed
    "orphaned doc" check, scoped to source roots rather than
    ``docs/design/`` now that subsystem docs are co-located.
    """
    doc_set = read_doc_set(project)

    # A declared source root carries a *required* root-level DESIGN.md
    # overview; every other entry is a per-subsystem doc one level down.
    # The two are distinguished only for message wording — both are
    # expected docs subject to the same existence/non-emptiness checks.
    declared_roots = set(project.sources)

    # --- Unmapped docs: an expected DESIGN.md (root overview or subsystem)
    # that is missing or empty ---
    expected_paths = set()
    for doc_source_path, doc in sorted(doc_set.subsystem_docs.items()):
        expected_paths.add(doc.path)
        kind = (
            "source root" if doc_source_path in declared_roots
            else "subsystem directory"
        )
        if not doc.exists:
            messages.append(
                f"Missing design doc: {kind} {doc_source_path} "
                f"has no DESIGN.md at {doc.path}."
            )
            continue
        if not doc.content.strip():
            messages.append(
                f"Empty design doc: {doc.path} exists but is empty or "
                "whitespace-only."
            )

    # --- Orphaned docs: a stray DESIGN.md under a source root that isn't a
    # recognized expected doc path (a root overview or a subsystem's own
    # doc) — e.g. one nested a level too deep ---
    for root in project.sources:
        if not root.is_dir():
            continue
        for candidate in sorted(root.rglob(SUBSYSTEM_DOC_NAME)):
            if candidate in expected_paths:
                continue
            messages.append(
                f"Orphaned design doc: {candidate} does not correspond to "
                "any declared source root or subsystem source directory."
            )

    # --- Project-level docs alongside the system doc: informational only ---
    design_dir = project.design_dir
    system_name = system_doc_name()
    if design_dir.is_dir():
        for entry in sorted(design_dir.iterdir()):
            if not entry.is_file() or entry.suffix != ".md":
                continue
            if entry.name == system_name:
                continue
            info.append(
                f"Non-subsystem doc (no frontmatter shape recognized): "
                f"{entry} — not orphan-checked."
            )


def _check_canonical_doc_set(
    project: Project, messages: list[str], info: list[str]
) -> None:
    _check_system_doc_present(project, messages)
    _check_subsystem_docs(project, messages, info)


# ---------------------------------------------------------------------------
# Sprint overlay checks
# ---------------------------------------------------------------------------


def _canonical_doc_paths(project: Project) -> set[Path]:
    """Return the set of real, known canonical design doc paths for *project*.

    The authoritative doc set: the system doc plus every declared source
    root's own overview doc and every subsystem's ``DESIGN.md`` (from
    :func:`read_doc_set`). Used to confirm an overlay file's manifest-recorded
    target is actually a member of the project's known doc set, not merely
    that some file with a matching basename exists somewhere.
    """
    doc_set = read_doc_set(project)
    paths = {doc_set.system_doc.path.resolve()}
    for doc in doc_set.subsystem_docs.values():
        paths.add(doc.path.resolve())
    return paths


def _read_overlay_sources_manifest(overlay_dir: Path) -> dict[str, str]:
    """Return the overlay-filename -> canonical-path manifest, or ``{}``.

    Mirrors ``clasi.design.overlay._read_sources_manifest`` (the manifest
    ticket 001 made authoritative) without importing it, since that
    function operates on a ``sprint_design_dir`` argument name/docstring
    scoped to the seed/apply lifecycle rather than validation — the
    reading logic itself (missing/malformed manifest is "no recorded
    sources," not an error here) is identical.
    """
    manifest_path = overlay_dir / _SOURCES_MANIFEST_NAME
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _check_overlay(project: Project, overlay_dir: Path, messages: list[str]) -> None:
    if not overlay_dir.is_dir():
        messages.append(f"Sprint overlay directory {overlay_dir} does not exist.")
        return

    canonical_paths = _canonical_doc_paths(project)
    manifest = _read_overlay_sources_manifest(overlay_dir)

    overlay_files = sorted(
        p
        for p in overlay_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and not p.name.endswith(".diff.md")
    )

    for overlay_file in overlay_files:
        # --- Canonical target resolves via the seed-time manifest, not the
        # overlay file's own basename (ticket 001 keys the manifest by the
        # overlay filename/slug; ticket 002 makes this the sole resolution
        # path so co-located docs sharing a basename, e.g. DESIGN.md, don't
        # collide) ---
        recorded = manifest.get(overlay_file.name)
        if recorded is None:
            messages.append(
                f"Sprint overlay file {overlay_file} has no entry in the "
                f"overlay's {_SOURCES_MANIFEST_NAME} manifest, so its "
                "canonical design doc target cannot be determined."
            )
        else:
            canonical_path = Path(recorded).resolve()
            if canonical_path not in canonical_paths:
                messages.append(
                    f"Sprint overlay file {overlay_file} has a "
                    f"{_SOURCES_MANIFEST_NAME} manifest entry pointing to "
                    f"{canonical_path}, which is not a known canonical "
                    "design doc for this project."
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

    Runs the canonical doc-set structure checks unconditionally, then the
    sprint-overlay checks when *overlay_dir* is given. All checks run to
    completion — every independent failure is collected, not just the
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
