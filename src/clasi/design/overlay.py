"""Overlay lifecycle: git-anchored copy/commit/diff/apply for sprint design overlays.

A sprint's ``clasi/sprints/NNN-slug/design/`` directory holds a *complete
updated copy* of each canonical design doc the sprint touches, under a
derived overlay slug filename (not necessarily the canonical basename —
see :func:`seed_and_commit`). This module implements the four-step
lifecycle around that directory. Each step assumes/produces a specific
git state:

1. :func:`seed_and_commit` — copies each named canonical doc into the
   sprint's ``design/`` directory *verbatim* (byte-identical at copy
   time), under its derived overlay slug, and commits them in a single
   commit, before any edits happen. Runs on ``main``, at sprint creation
   (late branching — see sprint.md Open Question 3's resolution).
   Precondition: none. Postcondition: the sprint's ``design/`` directory
   contains one pristine copy per named doc, committed; the pristine,
   last-committed state of each file is exactly what this commit
   recorded.

2. :func:`generate_diffs` — for each ``.md`` file in the sprint's
   ``design/`` directory (excluding ``*.diff.md`` files) whose current
   working-tree content differs from its pristine (last-committed at the
   seed commit — see below) version, writes a human-readable
   ``<name>.diff.md`` alongside it: fenced ```diff body plus frontmatter
   including ``source_hash``, the SHA-256 of the current overlay content
   (this is exactly the hash ``clasi.design.validator``'s staleness
   check reads — see ticket 004). Precondition: :func:`seed_and_commit`
   has run. Postcondition: every edited overlay file has an up-to-date
   ``.diff.md`` sibling; regenerating without further edits reproduces
   identical content (idempotent), since it always diffs against the same
   pristine baseline and re-derives the same hash.

   "Pristine" here means the content committed by :func:`seed_and_commit`
   (or, if that commit is no longer resolvable, the earliest commit that
   introduced the file) — **not** "whatever the file looked like before
   the most recent edit." Two successive edits both diff against the
   original seed content, not against each other.

3. :func:`commit_edits` — stages and commits exactly the sprint's
   ``design/`` directory (working-tree edits plus any newly generated
   ``.diff.md`` files) in a single commit, leaving the rest of the
   working tree's dirty state untouched. Intended to run at
   pre-execution approval. Precondition: :func:`seed_and_commit` has run.
   Postcondition: ``git status`` for the ``design/`` directory is clean;
   nothing outside it was staged or committed.

4. :func:`apply` — copies each overlay ``.md`` file (excluding
   ``*.diff.md`` files) over its corresponding canonical doc. Intended to
   run at sprint close. Precondition: none beyond the overlay directory
   existing. Postcondition: every canonical doc named by an overlay file
   is byte-identical to that overlay file. Raises
   :class:`OverlayApplyError` without writing anything if any overlay
   file cannot be mapped to a canonical doc — a partial apply would leave
   the canonical doc set in an inconsistent state, and ticket 006 gates
   the version-bump/tag step on apply succeeding.

   Canonical targets are **not** re-derived from the overlay directory's
   own layout (``canonical_design_dir / overlay_file.name``) — under the
   co-located ``DESIGN.md`` model (sprint 022), that flat join is wrong
   for every subsystem doc, and ``DESIGN.md`` is not even a unique
   filename across subsystems. Instead, :func:`seed_and_commit` records
   each overlay file's recorded canonical (source) path in a small JSON
   manifest (``_sources.json``) written alongside the overlay files, and
   :func:`apply` resolves targets by reading that manifest — never by
   filename matching. This is what lets a multi-subsystem overlay
   directory hold several files all named ``DESIGN.md`` and still resolve
   each one back to its own distinct subsystem directory.

This is the only module in ``clasi.design`` that shells out to git for
design-doc purposes; it composes ``clasi.design.paths``,
``clasi.design.store``, and ``clasi.design.validator`` but does not
decide *when* in the sprint lifecycle these steps run (that wiring is
ticket 006). Git calls go through the shared ``clasi.gitutil.run_git``
helper (an explicit ``cwd`` on every invocation, no bare
``subprocess.run(["git", ...])``) — the same helper ``clasi.sprint`` and
``clasi.tools.artifact_tools`` use.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from clasi.gitutil import run_git

_SOURCES_MANIFEST_NAME = "_sources.json"
"""Filename of the seed-time overlay-file -> canonical-path manifest.

Deliberately not a ``.md`` file so :func:`_overlay_md_files` (and every
validator/diff routine that lists ``.md`` files in the overlay directory)
never mistakes it for an overlay doc.
"""


class OverlayError(Exception):
    """Base class for overlay lifecycle failures."""


class OverlayGitError(OverlayError):
    """Raised when a required git operation fails."""


class OverlayApplyError(OverlayError):
    """Raised when :func:`apply` cannot map an overlay file to a canonical doc.

    Raised *before* any canonical file is modified — apply either fully
    succeeds or leaves the canonical doc set untouched.
    """


def _content_hash(text: str) -> str:
    """Return a stable SHA-256 hex digest of *text*.

    Matches ``clasi.design.validator``'s ``_content_hash`` exactly — the
    staleness check there recomputes this same hash over the current
    overlay content and compares it against the ``source_hash`` this
    module records.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _overlay_md_files(design_dir: Path) -> list[Path]:
    """Return the sprint overlay ``.md`` files, excluding ``*.diff.md``."""
    if not design_dir.is_dir():
        return []
    return sorted(
        p
        for p in design_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and not p.name.endswith(".diff.md")
    )


# ---------------------------------------------------------------------------
# Step 1: seed + commit pristine copies
# ---------------------------------------------------------------------------


def _manifest_path(sprint_design_dir: Path) -> Path:
    return sprint_design_dir / _SOURCES_MANIFEST_NAME


def _read_sources_manifest(sprint_design_dir: Path) -> dict[str, str]:
    """Return the overlay-filename -> canonical-path manifest, or ``{}``.

    Missing manifest (e.g. a pre-022 overlay directory, or one built by
    hand in a test) is treated as "no recorded sources" rather than an
    error here — callers decide whether that is fatal.
    """
    manifest_path = _manifest_path(sprint_design_dir)
    if not manifest_path.is_file():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def _write_sources_manifest(
    sprint_design_dir: Path, mapping: dict[str, str]
) -> Path:
    """Merge *mapping* into the existing manifest (if any) and write it back."""
    manifest_path = _manifest_path(sprint_design_dir)
    existing = _read_sources_manifest(sprint_design_dir)
    existing.update(mapping)
    manifest_path.write_text(
        json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest_path


def seed_and_commit(
    canonical_paths: list[Path],
    sprint_design_dir: Path,
    *,
    repo_root: Path,
    slugs: list[str] | None = None,
    commit_message: str = "chore: seed sprint design overlay",
) -> list[Path]:
    """Copy each canonical doc into *sprint_design_dir* and commit them.

    Copies each path in *canonical_paths* verbatim (byte-identical at
    copy time) into ``sprint_design_dir/<slug>``, records each seeded
    file's canonical source path in the overlay directory's
    ``_sources.json`` manifest keyed by that same slug (read later by
    :func:`apply` to resolve targets), then stages and commits exactly
    those copied files plus the manifest in a single commit before
    returning. This establishes the "pristine" baseline that
    :func:`generate_diffs` compares against.

    Args:
        canonical_paths: Absolute paths to canonical design documents
            (the system doc, or a subsystem's ``DESIGN.md``) to seed into
            the sprint.
        sprint_design_dir: The sprint's ``design/`` directory (created if
            it does not exist).
        repo_root: The git repository root to run git commands in.
        slugs: Overlay filename to use for each corresponding entry in
            *canonical_paths* (same order, same length). Callers (e.g.
            ``seed_sprint_design_overlay``) derive a unique, stable,
            reversible slug per doc so co-located docs that share a
            basename (``DESIGN.md``) do not collide in the flat overlay
            directory. Defaults to each canonical path's own basename
            (``canonical_path.name``) when omitted — the pre-slug
            behavior, still correct whenever no two seeded docs in the
            same call share a basename.
        commit_message: Commit message for the seed commit.

    Returns:
        The list of paths written under *sprint_design_dir*, in the same
        order as *canonical_paths*.

    Raises:
        OverlayGitError: If staging or committing fails.
    """
    sprint_design_dir.mkdir(parents=True, exist_ok=True)

    if slugs is None:
        slugs = [canonical_path.name for canonical_path in canonical_paths]

    seeded: list[Path] = []
    manifest_update: dict[str, str] = {}
    for canonical_path, slug in zip(canonical_paths, slugs):
        dest = sprint_design_dir / slug
        shutil.copyfile(canonical_path, dest)
        seeded.append(dest)
        manifest_update[slug] = str(canonical_path.resolve())

    if not seeded:
        return seeded

    manifest_path = _write_sources_manifest(sprint_design_dir, manifest_update)

    add_result = run_git(
        ["add", *[str(p) for p in seeded], str(manifest_path)], repo_root
    )
    if add_result.returncode != 0:
        raise OverlayGitError(
            f"Failed to stage seeded overlay files: {add_result.stderr.strip()}"
        )

    commit_result = run_git(["commit", "-m", commit_message], repo_root)
    if commit_result.returncode != 0:
        raise OverlayGitError(
            f"Failed to commit seeded overlay files: {commit_result.stderr.strip()}"
        )

    return seeded


# ---------------------------------------------------------------------------
# Step 2: diff generation
# ---------------------------------------------------------------------------


def _pristine_content(overlay_file: Path, repo_root: Path) -> str | None:
    """Return the earliest-committed (pristine/seed) content of *overlay_file*.

    Walks the file's commit history in *repo_root* and returns the
    content from the oldest commit that touched it — the seed commit
    written by :func:`seed_and_commit`. Returns ``None`` if the file has
    no commit history yet (e.g. seeded but not yet committed, or not
    tracked at all), in which case there is no pristine baseline to diff
    against.
    """
    rel_path = overlay_file.relative_to(repo_root)
    # Deliberately no --follow: seed_and_commit copies (not `git mv`s) the
    # canonical doc into the sprint dir, so the two paths have unrelated
    # git history. --follow's rename/copy detection would otherwise walk
    # past the seed commit into the *canonical* doc's own history and
    # return its original content instead of the sprint's seed content.
    log_result = run_git(
        ["log", "--format=%H", "--", str(rel_path)],
        repo_root,
    )
    if log_result.returncode != 0:
        return None
    commits = [c for c in log_result.stdout.strip().split("\n") if c]
    if not commits:
        return None
    earliest = commits[-1]

    show_result = run_git(["show", f"{earliest}:{rel_path}"], repo_root)
    if show_result.returncode != 0:
        return None
    return show_result.stdout


def _diff_md_path(overlay_file: Path) -> Path:
    return overlay_file.with_suffix("").with_suffix(".diff.md")


def _render_diff_body(name: str, pristine: str, current: str) -> str:
    """Render a human-readable diff body: before/after fenced sections.

    Per the issue's explicit requirement, this is *not* raw
    ``patch(1)``/unified-diff syntax — it is a fenced ```diff block
    produced from a unified diff (for a compact, familiar +/- view) but
    always wrapped in markdown fencing with a heading, so it reads as
    prose-adjacent documentation rather than a patch file to be applied.
    """
    import difflib

    pristine_lines = pristine.splitlines(keepends=True)
    current_lines = current.splitlines(keepends=True)
    unified = difflib.unified_diff(
        pristine_lines,
        current_lines,
        fromfile=f"{name} (pristine)",
        tofile=f"{name} (current)",
    )
    diff_text = "".join(unified)
    if not diff_text:
        diff_text = "(no textual differences)\n"

    return (
        f"# Diff: {name}\n\n"
        f"Comparison of the sprint overlay copy of `{name}` against its "
        "pristine (seed-commit) canonical version.\n\n"
        "```diff\n"
        f"{diff_text}"
        "```\n"
    )


def generate_diffs(sprint_design_dir: Path, *, repo_root: Path) -> list[Path]:
    """Write ``<name>.diff.md`` for each edited overlay file in *sprint_design_dir*.

    For every ``.md`` file in *sprint_design_dir* (excluding
    ``*.diff.md`` files) whose current content differs from its pristine
    (seed-commit) content, writes a human-readable diff file alongside
    it. Files that match their pristine content exactly are skipped (no
    diff file is written or updated for them). Idempotent: re-running
    with no further edits regenerates byte-identical ``.diff.md``
    content, since the pristine baseline and the hash are both
    deterministic functions of already-committed/current content.

    Args:
        sprint_design_dir: The sprint's ``design/`` directory.
        repo_root: The git repository root (used to resolve pristine
            content via git history).

    Returns:
        The list of ``.diff.md`` paths written, in filename order.
    """
    written: list[Path] = []
    for overlay_file in _overlay_md_files(sprint_design_dir):
        current = overlay_file.read_text(encoding="utf-8")
        pristine = _pristine_content(overlay_file, repo_root)
        if pristine is None or pristine == current:
            continue

        diff_body = _render_diff_body(overlay_file.name, pristine, current)
        diff_path = _diff_md_path(overlay_file)
        frontmatter = {
            "source_file": overlay_file.name,
            "source_hash": _content_hash(current),
        }
        _write_diff_file(diff_path, frontmatter, diff_body)
        written.append(diff_path)

    return written


def _write_diff_file(path: Path, frontmatter: dict[str, str], body: str) -> None:
    from clasi.artifact import Artifact

    Artifact(path).write(frontmatter, body)


# ---------------------------------------------------------------------------
# Step 3: commit edits
# ---------------------------------------------------------------------------


def commit_edits(
    sprint_design_dir: Path,
    *,
    repo_root: Path,
    commit_message: str = "chore: commit sprint design overlay edits",
) -> bool:
    """Stage and commit exactly *sprint_design_dir*'s changes.

    Runs ``git add <sprint_design_dir>`` (scoped to that directory, never
    a blanket ``git add -A``) followed by ``git commit``, so only the
    sprint's ``design/`` directory is committed — any other dirty state
    in the working tree is left untouched.

    Args:
        sprint_design_dir: The sprint's ``design/`` directory.
        repo_root: The git repository root to run git commands in.
        commit_message: Commit message for the edits commit.

    Returns:
        ``True`` if a commit was created, ``False`` if there was nothing
        to commit (the directory was already clean).

    Raises:
        OverlayGitError: If staging or committing fails for a reason
            other than "nothing to commit".
    """
    add_result = run_git(["add", str(sprint_design_dir)], repo_root)
    if add_result.returncode != 0:
        raise OverlayGitError(
            f"Failed to stage sprint design overlay changes: "
            f"{add_result.stderr.strip()}"
        )

    status_result = run_git(
        ["status", "--porcelain", "--", str(sprint_design_dir)], repo_root
    )
    if not status_result.stdout.strip():
        return False

    commit_result = run_git(["commit", "-m", commit_message], repo_root)
    if commit_result.returncode != 0:
        raise OverlayGitError(
            f"Failed to commit sprint design overlay changes: "
            f"{commit_result.stderr.strip()}"
        )
    return True


# ---------------------------------------------------------------------------
# Step 4: apply
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyPlan:
    """Resolved overlay-file -> canonical-doc mapping for :func:`apply`."""

    overlay_to_canonical: dict[Path, Path]


def _resolve_apply_plan(sprint_design_dir: Path) -> ApplyPlan:
    """Resolve each overlay file's canonical target from the seed manifest.

    Reads ``_sources.json`` (written by :func:`seed_and_commit`) rather
    than deriving a target from the overlay file's name or the overlay
    directory's own layout — a name-based/flat-join lookup cannot
    distinguish two subsystems whose overlay files share the basename
    ``DESIGN.md`` but belong under different source directories.
    """
    manifest = _read_sources_manifest(sprint_design_dir)
    mapping: dict[Path, Path] = {}
    unresolved: list[Path] = []

    for overlay_file in _overlay_md_files(sprint_design_dir):
        recorded = manifest.get(overlay_file.name)
        if recorded is None:
            unresolved.append(overlay_file)
            continue
        canonical_path = Path(recorded)
        if not canonical_path.parent.is_dir():
            unresolved.append(overlay_file)
            continue
        mapping[overlay_file] = canonical_path

    if unresolved:
        names = ", ".join(str(p) for p in unresolved)
        raise OverlayApplyError(
            "Cannot determine canonical target for overlay file(s): "
            f"{names}. No canonical files were modified."
        )

    return ApplyPlan(overlay_to_canonical=mapping)


def apply(sprint_design_dir: Path) -> list[Path]:
    """Copy each overlay ``.md`` file over its corresponding canonical doc.

    Resolves the full overlay-to-canonical mapping *before* writing
    anything, by reading each overlay file's recorded canonical (source)
    path from the ``_sources.json`` manifest that :func:`seed_and_commit`
    wrote alongside it — never by re-deriving a target from the overlay
    file's name or a flat target directory (see the module docstring). If
    any overlay file's canonical target cannot be determined, raises
    :class:`OverlayApplyError` and leaves every canonical file untouched
    (fail loudly, no partial apply — ticket 006 gates the
    version-bump/tag step on this succeeding).

    Args:
        sprint_design_dir: The sprint's ``design/`` directory.

    Returns:
        The list of canonical paths written, in filename order.

    Raises:
        OverlayApplyError: If any overlay file cannot be mapped to a
            canonical doc (e.g. no manifest entry for it, or its recorded
            canonical directory no longer exists). No files are modified
            in this case.
    """
    plan = _resolve_apply_plan(sprint_design_dir)

    applied: list[Path] = []
    for overlay_file, canonical_path in plan.overlay_to_canonical.items():
        canonical_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(overlay_file, canonical_path)
        applied.append(canonical_path)

    return applied
