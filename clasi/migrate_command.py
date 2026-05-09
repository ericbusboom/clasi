"""Implementation of the `clasi migrate` command.

Migrates an existing project from the old ``docs/clasi/`` layout to the
new ``.clasi/`` layout in a single, idempotent operation.

Steps
-----
1. Guard: ``.clasi/`` must not already exist (double-run protection).
2. Guard: no execution lock may be held for any active sprint.
3. Move ``docs/clasi/`` → ``.clasi/`` (``git mv`` if inside a git repo,
   ``shutil.move`` otherwise).
4. Update ``.gitignore``: replace ``docs/clasi/log/`` entry with
   ``.clasi/log/``.
5. Re-run ``clasi install --force`` (via ``run_init``) to refresh rule
   files and agent prompts.
6. Print a restart notice.

Public interface::

    run_migrate(target: str) -> None
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click

from clasi.init_command import run_init


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


def _update_gitignore(target: Path) -> None:
    """Replace ``docs/clasi/log/`` with ``.clasi/log/`` in .gitignore.

    If ``.gitignore`` does not exist, or the old entry is not present,
    the function does nothing (does not create the file).
    """
    gitignore = target / ".gitignore"
    if not gitignore.exists():
        return

    original = gitignore.read_text(encoding="utf-8")
    updated = original.replace("docs/clasi/log/", ".clasi/log/")
    if updated != original:
        gitignore.write_text(updated, encoding="utf-8")
        click.echo("  Updated: .gitignore (docs/clasi/log/ → .clasi/log/)")
    else:
        click.echo("  Unchanged: .gitignore (no docs/clasi/log/ entry found)")


def _check_no_execution_lock(target: Path) -> None:
    """Raise SystemExit if any execution lock is currently held.

    Checks the CLASI state database at ``docs/clasi/.clasi.db`` (the
    pre-migration location).  If the database does not exist, no lock
    can be held.
    """
    db_path = target / "docs" / "clasi" / ".clasi.db"
    if not db_path.exists():
        return

    from clasi.state_db import get_lock_holder

    holder = get_lock_holder(db_path)
    if holder:
        click.echo(
            f"Error: execution lock is held by sprint '{holder['sprint_id']}' "
            f"(acquired {holder['acquired_at']}). "
            "Release the lock before migrating.",
            err=True,
        )
        raise SystemExit(1)


def run_migrate(target: str) -> None:
    """Migrate a project from ``docs/clasi/`` to ``.clasi/``.

    Parameters
    ----------
    target:
        Path to the project root (string; resolved internally).

    Raises
    ------
    SystemExit(1):
        If ``.clasi/`` already exists, or if an execution lock is held.
    """
    target_path = Path(target).resolve()
    src = target_path / "docs" / "clasi"
    dst = target_path / ".clasi"

    # ── Guard: double-run protection ──────────────────────────────────────
    if dst.exists():
        click.echo(
            "Error: .clasi/ already exists. Migration has already been run "
            "or the directory was created manually.",
            err=True,
        )
        raise SystemExit(1)

    # ── Guard: source must exist ───────────────────────────────────────────
    if not src.exists():
        click.echo(
            "Error: docs/clasi/ not found. Nothing to migrate.",
            err=True,
        )
        raise SystemExit(1)

    # ── Guard: no execution lock ───────────────────────────────────────────
    _check_no_execution_lock(target_path)

    click.echo(f"Migrating CLASI artifacts: docs/clasi/ → .clasi/")
    click.echo()

    # ── Move the directory ─────────────────────────────────────────────────
    if _is_git_repo(target_path):
        click.echo("  Using: git mv docs/clasi .clasi")
        _git_mv(src, dst, target_path)
    else:
        click.echo("  Using: shutil.move (not a git repo)")
        shutil.move(str(src), str(dst))

    # ── Remove now-empty docs/clasi parent dirs if empty ──────────────────
    docs_dir = target_path / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        try:
            # Only remove if empty — don't disturb other docs/ content.
            docs_dir.rmdir()
            click.echo("  Removed: docs/ (was empty after migration)")
        except OSError:
            pass  # docs/ has other content — leave it alone

    # ── Update .gitignore ─────────────────────────────────────────────────
    click.echo(".gitignore:")
    _update_gitignore(target_path)
    click.echo()

    # ── Refresh rule files and agent prompts ──────────────────────────────
    click.echo("Refreshing CLASI install (rule files and agent prompts):")
    run_init(target, claude=True)

    # ── Done ──────────────────────────────────────────────────────────────
    click.echo()
    click.echo("=" * 60)
    click.echo("Migration complete.")
    click.echo()
    click.echo("IMPORTANT: restart any open CLASI sessions so that the MCP")
    click.echo("server picks up the new .clasi/ path.")
    click.echo("=" * 60)
