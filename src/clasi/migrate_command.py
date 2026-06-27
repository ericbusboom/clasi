"""Implementation of the `clasi migrate` command.

Detects and moves CLASI artifacts from legacy / alternate locations to the
locations defined by the project's ``paths:`` configuration (or the
built-in defaults if no config is present).

The public interface consists of three functions:

``detect_moves(project) -> list[Move]``
    Pure function: probes ``CANDIDATE_LOCATIONS`` and returns a list of
    ``Move`` objects describing what should be relocated.  Returns an empty
    list if everything is already in place.

``execute_moves(project, moves, dry_run=False)``
    Impure: carries out the relocations described by *moves*, rewrites
    ``.gitignore``, cleans up empty parent dirs, and optionally resets the
    project's DB connection if the database file moved.

``run_migrate(target: str) -> None``
    Thin wrapper: detect → execute → run_init → restart notice.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import click

from clasi.init_command import run_init

if TYPE_CHECKING:
    from clasi.project import Project


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class Move:
    """A planned file/directory relocation."""

    category: str
    src: Path
    dst: Path
    mode: str  # "move" | "merge"
    is_file: bool


# ---------------------------------------------------------------------------
# Candidate locations table
# ---------------------------------------------------------------------------

# Per-category ordered list of root-relative paths to probe as *sources*
# (legacy or alternate locations).  The first existing, non-empty entry wins.
# Destinations are always resolved live from the Project object.
CANDIDATE_LOCATIONS: dict[str, list[str]] = {
    "issues": [".clasi/issues", "docs/clasi/issues"],
    "sprints": [".clasi/sprints", "docs/clasi/sprints"],
    "reflections": [".clasi/reflections", "docs/clasi/reflections"],
    "architecture": [".clasi/architecture", "docs/clasi/architecture"],
    "design": [".clasi/design", "docs/clasi/design"],
    "logs": [".clasi/log", "docs/clasi/log"],
    "db": [".clasi/.clasi.db", "docs/clasi/.clasi.db"],
}

# Filenames that are platform-specific instruction or housekeeping files,
# never user-created CLASI artifacts.  Directories containing only these
# files are treated as "empty" by ``detect_moves`` so that platform
# installers writing rule files into legacy candidate dirs do not
# spuriously trigger migration.
_NON_ARTIFACT_NAMES: frozenset[str] = frozenset({"AGENTS.md", ".gitkeep", ".gitignore"})


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_git_repo(path: Path) -> bool:
    """Return True if *path* is inside a git repository."""
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _git_mv(src: Path, dst: Path, repo_root: Path) -> None:
    """Run ``git mv src dst`` from *repo_root*."""
    subprocess.run(
        ["git", "-C", str(repo_root), "mv", str(src), str(dst)],
        check=True,
    )


def _update_gitignore(target: Path, replacements: list[tuple[str, str]]) -> None:
    """Apply a list of ``(old_str, new_str)`` replacements to ``.gitignore``.

    If ``.gitignore`` does not exist, or none of the old strings are present,
    the function does nothing (does not create the file).

    Parameters
    ----------
    target:
        Project root directory.
    replacements:
        List of ``(old_str, new_str)`` pairs to apply in order.
    """
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        return

    original = gitignore.read_text(encoding="utf-8")
    updated = original
    for old_str, new_str in replacements:
        updated = updated.replace(old_str, new_str)

    if updated != original:
        gitignore.write_text(updated, encoding="utf-8")
        click.echo("  Updated: .gitignore")
    else:
        click.echo("  Unchanged: .gitignore (no matching entries found)")


def _check_no_execution_lock(target: Path, db_paths: list[Path] | None = None) -> None:
    """Raise SystemExit(1) if any execution lock is currently held.

    Parameters
    ----------
    target:
        Project root directory.
    db_paths:
        Explicit list of database file paths to check.  When ``None``, falls
        back to the legacy single-path check (``docs/clasi/.clasi.db``).
    """
    if db_paths is None:
        # Legacy fallback: original single-location check
        db_paths = [target / "docs" / "clasi" / ".clasi.db"]

    from clasi.state_db import get_lock_holder

    for db_path in db_paths:
        if not db_path.exists():
            continue
        holder = get_lock_holder(db_path)
        if holder:
            click.echo(
                f"Error: execution lock is held by sprint '{holder['sprint_id']}' "
                f"(acquired {holder['acquired_at']}). "
                "Release the lock before migrating.",
                err=True,
            )
            raise SystemExit(1)


def _cleanup_empty_parents(path: Path, stop_at: Path) -> None:
    """Remove *path* and its ancestors while they are empty, stopping at *stop_at*.

    ``stop_at`` itself is never removed.
    """
    current = path
    while current != stop_at and current != current.parent:
        if current.is_dir():
            try:
                current.rmdir()  # only succeeds when empty
                click.echo(f"  Removed empty dir: {current}")
            except OSError:
                break
        current = current.parent


# ---------------------------------------------------------------------------
# Public API: detect_moves
# ---------------------------------------------------------------------------


def detect_moves(project: Project) -> list[Move]:
    """Return a list of ``Move`` objects describing what should be relocated.

    This is a *pure* function — it inspects the filesystem but makes no
    changes.  Returns an empty list if everything is already in place (or
    there is nothing to move).

    Parameters
    ----------
    project:
        A ``Project`` instance whose path-resolution properties supply the
        migration *destination* for each category.
    """
    root = project.root

    # Map each category to its configured destination path.
    category_dst: dict[str, Path] = {
        "issues": project.issues_dir,
        "sprints": project.sprints_dir,
        "reflections": project.reflections_dir,
        "architecture": project.architecture_dir,
        "design": project.design_dir,
        "logs": project.log_dir,
        "db": project.db_path,
    }

    moves: list[Move] = []

    for category, candidates in CANDIDATE_LOCATIONS.items():
        dst = category_dst[category]
        is_file = category == "db"

        # Probe candidates in order; use the first that exists and is non-empty.
        src: Path | None = None
        for rel in candidates:
            candidate = root / rel
            if not candidate.exists():
                continue
            # For directories: skip if empty or contains only platform/housekeeping
            # files (AGENTS.md, .gitkeep, .gitignore).  These are not user artifacts
            # and should not trigger migration.
            if not is_file and candidate.is_dir():
                artifact_files = [
                    f for f in candidate.iterdir()
                    if f.name not in _NON_ARTIFACT_NAMES
                ]
                if not artifact_files:
                    continue
            src = candidate
            break

        if src is None:
            # Nothing to migrate for this category.
            continue

        # Resolve both paths to detect src == dst (already in place).
        try:
            src_resolved = src.resolve()
            dst_resolved = dst.resolve()
        except OSError:
            src_resolved = src
            dst_resolved = dst

        if src_resolved == dst_resolved:
            continue

        # Determine mode.
        if is_file:
            mode = "merge" if dst.exists() else "move"
        else:
            dst_artifact_files = (
                [f for f in dst.iterdir() if f.name not in _NON_ARTIFACT_NAMES]
                if dst.exists()
                else []
            )
            mode = "merge" if dst_artifact_files else "move"

        moves.append(Move(category=category, src=src, dst=dst, mode=mode, is_file=is_file))

    return moves


# ---------------------------------------------------------------------------
# Public API: execute_moves
# ---------------------------------------------------------------------------


def execute_moves(
    project: Project,
    moves: list[Move],
    dry_run: bool = False,
) -> None:
    """Execute the relocations described by *moves*.

    Parameters
    ----------
    project:
        The ``Project`` instance (used for repo root and to reset ``_db``).
    moves:
        List of ``Move`` objects as returned by ``detect_moves``.
    dry_run:
        When ``True``, print proposed actions without performing any I/O.
    """
    if not moves:
        return

    root = project.root

    # ── Guard: no execution lock ────────────────────────────────────────────
    all_db_paths: list[Path] = []
    for rel in CANDIDATE_LOCATIONS["db"]:
        all_db_paths.append(root / rel)
    # Also include the configured destination db path.
    all_db_paths.append(project.db_path)
    # Deduplicate while preserving order.
    seen: set[Path] = set()
    unique_db_paths: list[Path] = []
    for p in all_db_paths:
        if p not in seen:
            seen.add(p)
            unique_db_paths.append(p)

    if not dry_run:
        _check_no_execution_lock(root, unique_db_paths)

    is_git = _is_git_repo(root)

    gitignore_replacements: list[tuple[str, str]] = []
    db_moved = False

    for move in moves:
        src = move.src
        dst = move.dst

        if dry_run:
            action = "MERGE" if move.mode == "merge" else "MOVE"
            click.echo(f"  [dry-run] {action}: {src} → {dst}")
            continue

        # Ensure destination parent directory exists.
        dst.parent.mkdir(parents=True, exist_ok=True)

        if move.is_file:
            # DB file move.
            if dst.exists():
                click.echo(
                    f"  Warning: {dst} already exists; skipping (will not clobber)."
                )
            else:
                click.echo(f"  Moving file: {src} → {dst}")
                if is_git:
                    _git_mv(src, dst, root)
                else:
                    shutil.move(str(src), str(dst))
                db_moved = True
                _cleanup_empty_parents(src.parent, root)
        elif move.mode == "move":
            # Simple directory move — destination has no real artifact files.
            dst.mkdir(parents=True, exist_ok=True)
            # Remove any residual non-artifact housekeeping files (e.g. .gitkeep
            # placed by init's scaffold) so the destination directory can be
            # rmdir'd before the wholesale rename.
            if dst.exists():
                for _f in list(dst.iterdir()):
                    if _f.is_file() and _f.name in _NON_ARTIFACT_NAMES:
                        _f.unlink()
            if is_git:
                # git mv can move the directory wholesale.
                click.echo(f"  Moving (git mv): {src} → {dst}")
                # git mv fails if dst already exists (even if empty); remove first.
                if dst.exists() and not any(dst.iterdir()):
                    dst.rmdir()
                _git_mv(src, dst, root)
            else:
                click.echo(f"  Moving: {src} → {dst}")
                # shutil.move into an existing dir merges contents.
                if dst.exists() and not any(dst.iterdir()):
                    dst.rmdir()
                shutil.move(str(src), str(dst))
            _cleanup_empty_parents(src.parent, root)
        else:
            # mode == "merge" — dst is non-empty; move only non-conflicting files.
            click.echo(f"  Merging: {src} → {dst} (file-by-file, no clobber)")
            dst.mkdir(parents=True, exist_ok=True)
            for item in sorted(src.rglob("*")):
                if not item.is_file():
                    continue
                rel = item.relative_to(src)
                target_file = dst / rel
                target_file.parent.mkdir(parents=True, exist_ok=True)
                if target_file.exists():
                    click.echo(f"    Warning: {target_file} exists; skipping.")
                else:
                    click.echo(f"    Moving: {item} → {target_file}")
                    if is_git:
                        _git_mv(item, target_file, root)
                    else:
                        shutil.move(str(item), str(target_file))
            # Remove residual non-artifact files (e.g. .gitkeep) so that
            # _cleanup_empty_parents can rmdir the source directory.
            for item in sorted(src.rglob("*")):
                if item.is_file() and item.name in _NON_ARTIFACT_NAMES:
                    item.unlink()
            # Clean up (now potentially empty) source tree.
            _cleanup_empty_parents(src, root)

        # Record .gitignore replacement for log paths.
        if move.category == "logs":
            src_rel = str(src.relative_to(root)).rstrip("/") + "/"
            dst_rel = str(dst.relative_to(root)).rstrip("/") + "/"
            if src_rel != dst_rel:
                gitignore_replacements.append((src_rel, dst_rel))

    if not dry_run:
        # Update .gitignore for all moves that affect log paths.
        if gitignore_replacements:
            click.echo(".gitignore:")
            _update_gitignore(root, gitignore_replacements)

        # Reset the project's DB connection if the db file moved.
        if db_moved:
            project._db = None  # noqa: SLF001 — intentional internal reset


# ---------------------------------------------------------------------------
# Public API: run_migrate
# ---------------------------------------------------------------------------


def run_migrate(target: str, yes: bool = False) -> None:
    """Detect and execute all pending CLASI artifact relocations.

    Parameters
    ----------
    target:
        Path to the project root (string; resolved internally).
    yes:
        When ``True``, relocate without prompting (non-interactive / unattended).

    This function replaces the old hard-coded ``docs/clasi/ → .clasi/``
    migration with a config-driven detect-and-move approach.  It is
    idempotent: a second run with no pending moves prints "Nothing to
    migrate." and exits cleanly.
    """
    from clasi.project import Project

    target_path = Path(target).resolve()
    project = Project(target_path)

    moves = detect_moves(project)

    if not moves:
        click.echo("Nothing to migrate. All artifacts are already at their configured locations.")
        return

    click.echo(f"Migrating CLASI artifacts in: {target_path}")
    click.echo()

    for move in moves:
        action = "merge" if move.mode == "merge" else "move"
        click.echo(f"  Planned {action}: {move.src} → {move.dst}")
    click.echo()

    import sys

    if yes or not (sys.stdin.isatty() and sys.stdout.isatty()):
        # Non-interactive mode or --yes flag: execute without prompting.
        # (In non-interactive mode, the user explicitly invoked `clasi migrate`,
        # so we proceed without asking.  `--yes` skips the TTY prompt too.)
        execute_moves(project, moves)
    else:
        # Interactive TTY without --yes: ask for confirmation before moving.
        click.echo("Your files are not in the right spot. Proposed moves:")
        for m in moves:
            click.echo(f"  {m.src} → {m.dst}")
        if click.confirm("Move them?", default=False):
            execute_moves(project, moves)
        else:
            click.echo(
                "Hint: run `clasi migrate --yes` to relocate without prompting.",
            )
            return

    # ── Refresh rule files and agent prompts ──────────────────────────────
    click.echo()
    click.echo("Refreshing CLASI install (rule files and agent prompts):")
    run_init(target, claude=True)

    # ── Done ──────────────────────────────────────────────────────────────
    click.echo()
    click.echo("=" * 60)
    click.echo("Migration complete.")
    click.echo()
    click.echo("IMPORTANT: restart any open CLASI sessions so that the MCP")
    click.echo("server picks up the new artifact locations.")
    click.echo("=" * 60)
