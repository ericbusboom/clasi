"""The heart of ticket 030/004: a failed close_sprint is resumable.

Drives a real scratch git repository (never this repo's own sprint 030)
through close_sprint's full lifecycle twice: an attempt that fails at the
"merge" step -- *after* tests and the version bump have both already
completed for real -- followed by a retry with the injected failure
lifted. Asserts the three properties SUC-002's acceptance criteria and
the sprint's own Success Criteria name explicitly:

- a single version tag exists after the retry, not two (no double-mint
  for an unchanged HEAD);
- the execution lock is released, not held by the archived sprint, both
  immediately after the failed attempt (force_close already ran before
  the injected failure) and after the successful retry;
- the tests step and the version-bump step are each not meaningfully
  redone on the retry -- proven by a real invocation counter (a script
  that increments a counter file each time it actually runs, not a
  process-return-code stub) for tests, and a call-count spy wrapping the
  real compute_next_version for the version bump, rather than asserting
  against a mocked subprocess call sequence.

The failure is injected via Sprint.merge_branch specifically (not the
"tests" step itself) because that is the only failure point after which
*all three* of the above are simultaneously meaningful to assert: a
failure at "tests" would mean tests never completed on attempt 1 (nothing
to prove "not redone"), and would mean no tag was minted yet either
(nothing to prove "not double-minted").
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from clasi.frontmatter import write_frontmatter
from clasi.mcp_server import set_project
from clasi.sprint import Sprint
from clasi.state_db import acquire_lock, advance_phase, get_lock_holder, get_recovery_state, record_gate
from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    move_ticket_to_done,
    update_ticket_status,
)
import clasi.tools.artifact_tools as artifact_tools_module


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)


def _git_commit(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", message], cwd=root, check=True, capture_output=True)


@pytest.fixture
def work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real, scratch git repository seeded as a CLASI project -- never
    this repo's own sprint 030 -- so close_sprint's real version-bump/tag
    machinery has real git tags and a real version file to work against."""
    root = tmp_path / "repo"
    root.mkdir()
    _git_init(root)

    (root / "pyproject.toml").write_text(
        '[project]\nname = "resumability-dry-run"\nversion = "0.20260101.1"\n',
        encoding="utf-8",
    )
    clasi_dir = root / ".clasi"
    clasi_dir.mkdir(parents=True, exist_ok=True)
    (clasi_dir / "config.yaml").write_text("process: se\n", encoding="utf-8")
    _git_commit(root, "initial")

    monkeypatch.chdir(root)
    set_project(root)
    return root


def _advance_to_ticketing(work_dir: Path, sprint_id: str) -> None:
    db_path = work_dir / ".clasi" / ".clasi.db"
    advance_phase(db_path, sprint_id)  # roadmap -> planning-docs
    advance_phase(db_path, sprint_id)  # planning-docs -> architecture-review
    record_gate(db_path, sprint_id, "architecture_review", "passed")
    advance_phase(db_path, sprint_id)  # architecture-review -> ticketing (031/002)
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")


def _write_test_counter_script(work_dir: Path) -> tuple[str, Path]:
    """Write a tiny script that increments a counter file each time it is
    actually invoked and exits 0 -- a real subprocess spy, not a mocked
    return code. Returns (test_command, counter_file)."""
    script = work_dir / "_count_test_runs.py"
    script.write_text(
        "import pathlib, sys\n"
        "p = pathlib.Path(sys.argv[1])\n"
        "n = int(p.read_text()) if p.exists() else 0\n"
        "p.write_text(str(n + 1))\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    counter_file = work_dir / "_test_run_count.txt"
    test_command = f"{sys.executable} {script} {counter_file}"
    return test_command, counter_file


def _tags(work_dir: Path) -> list[str]:
    return [t for t in _run(["git", "tag", "-l"], work_dir).stdout.split() if t]


class TestCloseSprintResumability:
    """A failed close_sprint (merge step, after tests + version bump
    already succeeded) is resumable: single tag, lock released correctly
    per the failure point, and completed steps are not meaningfully
    redone on retry."""

    def test_failed_merge_then_retry_is_resumable(
        self, work_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        create_result = json.loads(create_sprint("Resumability Dry Run"))
        sprint_id = create_result["id"]
        sprint_dir = Path(create_result["path"])
        branch_name = create_result["branch"]

        write_frontmatter(
            sprint_dir / "sprint.md",
            {
                "id": sprint_id,
                "title": "Resumability Dry Run",
                "status": "active",
                "branch": branch_name,
            },
        )

        _advance_to_ticketing(work_dir, sprint_id)

        create_ticket(sprint_id, "Do the thing")
        ticket_path = sprint_dir / "tickets" / "001-do-the-thing.md"
        assert ticket_path.exists(), f"expected ticket file at {ticket_path}"

        db_path = work_dir / ".clasi" / ".clasi.db"
        acquire_lock(db_path, sprint_id)
        advance_phase(db_path, sprint_id)  # ticketing -> executing

        _run(["git", "checkout", "-b", branch_name], work_dir)
        (work_dir / "feature.py").write_text("# ticket work\n", encoding="utf-8")
        update_ticket_status(str(ticket_path), "done")
        move_ticket_to_done(str(ticket_path))
        _git_commit(work_dir, f"feat: implement ticket ({sprint_id}-001)")

        test_command, counter_file = _write_test_counter_script(work_dir)

        # --- Spy on the real compute_next_version -- wraps the real
        # function (never a stub), so the version actually computed and
        # tagged is real, but call_count proves whether it ran once or
        # twice across the two close_sprint attempts.
        real_compute_next_version = artifact_tools_module.compute_next_version
        compute_calls = {"n": 0}

        def _spy_compute_next_version(*args, **kwargs):
            compute_calls["n"] += 1
            return real_compute_next_version(*args, **kwargs)

        monkeypatch.setattr(
            artifact_tools_module, "compute_next_version", _spy_compute_next_version
        )

        # --- Fail Sprint.merge_branch exactly once (the first call) --
        # this is *after* precondition, tests, self-repair, archive,
        # force_close, and version_bump have all already run for real on
        # attempt 1, and before delete_branch/push_tags/prune_worktrees
        # on the eventual successful retry.
        real_merge_branch = Sprint.merge_branch
        merge_calls = {"n": 0}

        def _flaky_merge_branch(self, main_branch: str = "master"):
            merge_calls["n"] += 1
            if merge_calls["n"] == 1:
                raise RuntimeError("simulated merge failure (injected by test)")
            return real_merge_branch(self, main_branch)

        monkeypatch.setattr(Sprint, "merge_branch", _flaky_merge_branch)

        # ==================== Attempt 1: fails at "merge" ====================
        attempt1 = json.loads(
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command=test_command,
            )
        )

        assert attempt1["status"] == "error", attempt1
        assert attempt1["error"]["step"] == "merge", attempt1
        assert "archive" in attempt1["completed_steps"], attempt1
        assert "version_bump" in attempt1["completed_steps"], attempt1
        assert "merge" not in attempt1["completed_steps"], attempt1

        # The failure point is *after* force_close: the lock must already
        # be released, not held by the (now-archived) sprint -- this is
        # "released or held correctly per the failure point" for a
        # post-force_close failure.
        assert get_lock_holder(db_path) is None, (
            "lock must be released after a failure at 'merge', which runs "
            "after force_close"
        )

        # Recovery state was written naming the failed step, never
        # swallowed.
        recovery = get_recovery_state(db_path)
        assert recovery is not None
        assert recovery["step"] == "merge"

        # Exactly one tag exists already -- version_bump ran for real on
        # attempt 1, before the injected merge failure.
        tags_after_attempt1 = _tags(work_dir)
        assert len(tags_after_attempt1) == 1, tags_after_attempt1
        assert compute_calls["n"] == 1, compute_calls
        assert counter_file.read_text(encoding="utf-8").strip() == "1", (
            "tests must have run exactly once on attempt 1"
        )

        # ==================== Attempt 2: retry, merge now succeeds ====================
        attempt2 = json.loads(
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command=test_command,
            )
        )

        assert attempt2["status"] == "success", attempt2
        assert attempt2["git"]["merged"] is True, attempt2

        # --- The three resumability properties this ticket exists to prove ---

        # 1. A single version tag exists -- not two -- after the retry.
        tags_after_attempt2 = _tags(work_dir)
        assert len(tags_after_attempt2) == 1, (
            f"expected exactly one version tag after retry, found {tags_after_attempt2}"
        )
        assert tags_after_attempt2 == tags_after_attempt1, (
            "the retry must reuse attempt 1's tag, not mint a new one"
        )

        # 2. The execution lock is released, not held by the archived
        # sprint, after the successful retry.
        assert get_lock_holder(db_path) is None

        # 3. Steps already completed on attempt 1 (tests, version_bump)
        # are not meaningfully redone on the retry: the test-run counter
        # and the compute_next_version spy each still show exactly one
        # real invocation total, across both attempts.
        assert compute_calls["n"] == 1, (
            f"compute_next_version must not run again on retry, called {compute_calls['n']} times"
        )
        assert counter_file.read_text(encoding="utf-8").strip() == "1", (
            "the tests step must not re-run on retry -- it already passed "
            "on attempt 1, and the recovery pointer (failed at 'merge', "
            "after 'tests') proves that without needing to run them again"
        )

        # merge_branch's own body (not just the wrapper) really did run
        # on the second call -- two calls into the wrapper total.
        assert merge_calls["n"] == 2, merge_calls

        # And the recovery record is cleared on a fully successful close.
        assert get_recovery_state(db_path) is None
