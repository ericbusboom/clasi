#!/usr/bin/env python3
"""Set up a test project for E2E testing.

Creates a project directory, initializes CLASI and git, and copies the
guessing-game spec into docs/.

Usage::

    python tests/e2e/setup_project.py [target-dir]

If no target directory is given, creates ``tests/e2e/project/``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SPEC_FILE = _THIS_DIR / "guessing-game-spec.md"


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  [FAIL] exit {result.returncode}")
        if result.stdout.strip():
            print(f"  stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"  stderr: {result.stderr.strip()}")
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result


def setup_project(target: Path | None = None) -> Path:
    """Create and initialize a test project directory.

    Steps:
    1. Create the directory (removes existing if present)
    2. Run ``clasi init``
    3. Run ``git init`` with an initial commit
    4. Copy the spec to ``docs/guessing-game-spec.md``

    Returns the project directory path.
    """
    project = target or (_THIS_DIR / "project")
    if project.exists():
        shutil.rmtree(project)
    project.mkdir(parents=True)
    print(f"[STEP] Created project directory: {project}")

    print("[STEP] Initializing CLASI ...")
    _run(["clasi", "init"], cwd=project)

    print("[STEP] Initializing git ...")
    _run(["git", "init"], cwd=project)
    _run(["git", "add", "."], cwd=project)
    _run(["git", "commit", "-m", "Initial commit: CLASI init"], cwd=project)

    print("[STEP] Copying spec ...")
    if not _SPEC_FILE.exists():
        raise FileNotFoundError(f"Spec file not found: {_SPEC_FILE}")
    docs_dir = project / "docs"
    docs_dir.mkdir(exist_ok=True)
    dest = docs_dir / "guessing-game-spec.md"
    shutil.copy2(str(_SPEC_FILE), str(dest))
    _run(["git", "add", "docs/"], cwd=project)
    _run(["git", "commit", "-m", "Add guessing-game spec"], cwd=project)

    print(f"[DONE] Project ready at {project}")
    return project


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    setup_project(target)


if __name__ == "__main__":
    main()
