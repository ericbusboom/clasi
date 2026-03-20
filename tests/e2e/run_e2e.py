#!/usr/bin/env python3
"""E2E test harness for the CLASI SE process.

Creates a temporary project, initializes CLASI, copies a guessing-game
spec, and dispatches a team-lead subagent to implement it across 4
sprints.  The temp directory persists after exit so ``verify.py`` can
inspect the results.

Usage::

    python tests/e2e/run_e2e.py

The script prints the temp directory path on completion.  Point
``verify.py`` at that directory to validate the results::

    python tests/e2e/verify.py <temp-dir>
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = Path(__file__).resolve().parent
_SPEC_FILE = _THIS_DIR / "guessing-game-spec.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, printing the command and capturing output."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        print(f"  [FAIL] exit {result.returncode}")
        if result.stdout.strip():
            print(f"  stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"  stderr: {result.stderr.strip()}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result


def _create_temp_project() -> Path:
    """Create a persistent temporary directory for the project."""
    tmp = Path(tempfile.mkdtemp(prefix="clasi-e2e-"))
    print(f"[INFO] Temp project directory: {tmp}")
    return tmp


def _init_clasi(project_dir: Path) -> None:
    """Run ``clasi init`` in the project directory."""
    print("[STEP] Initializing CLASI ...")
    _run(["clasi", "init"], cwd=project_dir)
    print("  [OK] CLASI initialized")


def _copy_spec(project_dir: Path) -> Path:
    """Copy the guessing-game spec into the project root."""
    print("[STEP] Copying spec ...")
    if not _SPEC_FILE.exists():
        raise FileNotFoundError(f"Spec file not found: {_SPEC_FILE}")
    dest = project_dir / "guessing-game-spec.md"
    shutil.copy2(str(_SPEC_FILE), str(dest))
    print(f"  [OK] Spec copied to {dest}")
    return dest


def _init_git(project_dir: Path) -> None:
    """Initialize a git repo with an initial commit."""
    print("[STEP] Initializing git ...")
    _run(["git", "init"], cwd=project_dir)
    _run(["git", "add", "."], cwd=project_dir)
    _run(["git", "commit", "-m", "Initial commit: CLASI init + spec"], cwd=project_dir)
    print("  [OK] Git initialized with initial commit")


def _build_subagent_prompt(spec_path: Path) -> str:
    """Compose the prompt for the team-lead subagent."""
    return f"""\
You are the team-lead for this project.  Your job is to implement the
application described in ``{spec_path.name}`` following the CLASI SE
process installed in this project.

Read ``{spec_path.name}`` first.  It contains a guessing-game CLI spec
with a sprint plan that calls for 4 sprints:

1. Project structure and menu
2. Number guessing game
3. Color guessing game
4. City guessing game

For each sprint:
- Plan the sprint using the CLASI SE process (create sprint, write
  planning docs, architecture review, stakeholder approval, ticketing).
- Execute all tickets.
- Close the sprint (merge, archive, tag).

Auto-approve all review gates (architecture review, stakeholder review).

After all 4 sprints are done the project should have:
- A working ``guessing_game`` package runnable via ``python -m guessing_game``
- 4 closed sprints in ``docs/clasi/sprints/done/``
- All tickets in ``tickets/done/`` with status done
- Passing tests (``pytest``)
"""


def _dispatch_subagent(project_dir: Path, spec_path: Path) -> bool:
    """Dispatch the team-lead subagent via ``claude`` CLI.

    Returns True if the subagent exited successfully, False otherwise.
    """
    print("[STEP] Dispatching team-lead subagent ...")
    prompt = _build_subagent_prompt(spec_path)

    # The ``claude`` CLI accepts a prompt on stdin with --print or can be
    # invoked with a -p flag.  We use -p for direct prompting.
    result = _run(
        [
            "claude",
            "-p", prompt,
            "--allowedTools", "Bash,Read,Write,Edit,Glob,Grep,Agent",
        ],
        cwd=project_dir,
        check=False,
    )

    if result.returncode == 0:
        print("  [OK] Subagent completed successfully")
        return True
    else:
        print(f"  [FAIL] Subagent exited with code {result.returncode}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_e2e() -> tuple[Path, bool]:
    """Run the full E2E test and return (project_dir, success)."""
    project_dir = _create_temp_project()

    try:
        _init_clasi(project_dir)
        spec_path = _copy_spec(project_dir)
        _init_git(project_dir)
        success = _dispatch_subagent(project_dir, spec_path)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        success = False

    return project_dir, success


def main() -> None:
    """CLI entry point."""
    print("=" * 60)
    print("CLASI E2E Test Harness")
    print("=" * 60)

    project_dir, success = run_e2e()

    print()
    print("=" * 60)
    print(f"Project directory: {project_dir}")
    print(f"Result: {'PASS' if success else 'FAIL'}")
    print("=" * 60)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
