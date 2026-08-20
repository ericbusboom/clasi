"""Dry-run proof for ticket 020-003's reconciled version-bump cadence.

The issue this ticket closes measured 11 version-bump commits in 36 total
across one real sprint (about one per ticket) — noise with no release
value, produced by the old per-commit/per-ticket bump instruction in
`.claude/rules/git-commits.md` and the programmer agent's own workflow
step. The new policy removes the manual bump entirely for sprint work and
relies on `close_sprint`'s existing bump-once-per-sprint behavior (gated
by `version_trigger`, default `every_change`, evaluated only at
`sprint_close`).

This test drives a real git repository through a 3-ticket sprint under
the *new* policy — three ticket-completion commits, zero manual version
bumps among them — then calls the real `close_sprint` MCP tool (full
lifecycle: precondition self-repair, archive, real `git rebase` +
`--no-ff` merge, real `compute_next_version`/`update_version_file`/
`git commit`/`git tag`) and inspects the resulting git log. It asserts
exactly one `chore: bump version` commit exists for the whole sprint,
proving the new cadence satisfies the ticket's numeric target (at most
1-2 bumps for a 3+-ticket sprint, not one per ticket) against the real
code path, not a mock of `close_sprint` or of the versioning module.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from clasi.frontmatter import write_frontmatter
from clasi.mcp_server import set_project
from clasi.state_db import acquire_lock, advance_phase, record_gate
from clasi.tools.artifact_tools import (
    close_sprint,
    create_sprint,
    create_ticket,
    move_ticket_to_done,
    update_ticket_status,
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root, check=True, capture_output=True,
    )


def _git_commit(root: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


def _bump_commit_count(root: Path) -> int:
    """Count commits across all branches whose subject starts with the
    real bump message close_sprint writes (`chore: bump version to ...`).
    """
    log = _run(["git", "log", "--all", "--oneline"], cwd=root)
    return sum(
        1 for line in log.stdout.splitlines() if "chore: bump version to" in line
    )


def _ticket_commit_count(root: Path) -> int:
    log = _run(["git", "log", "--all", "--oneline"], cwd=root)
    return sum(1 for line in log.stdout.splitlines() if "implement ticket" in line)


@pytest.fixture
def work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real git repo, seeded as a CLASI project root with a pyproject.toml
    so compute_next_version/detect_version_file have a real version file
    to bump — exercising the actual bump mechanism, not a stub.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git_init(root)

    (root / "pyproject.toml").write_text(
        '[project]\nname = "dry-run-project"\nversion = "0.20260101.1"\n',
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
    advance_phase(db_path, sprint_id)  # architecture-review -> stakeholder-review
    record_gate(db_path, sprint_id, "stakeholder_approval", "passed")
    advance_phase(db_path, sprint_id)  # stakeholder-review -> ticketing


class TestVersionBumpCadenceDryRun:
    """A 3-ticket sprint, closed once, must produce exactly one bump commit."""

    def test_three_ticket_sprint_produces_exactly_one_bump_commit(
        self, work_dir: Path
    ) -> None:
        create_result = json.loads(create_sprint("Cadence Dry Run"))
        sprint_id = create_result["id"]
        sprint_dir = Path(create_result["path"])
        branch_name = create_result["branch"]

        # Point sprint.md at the branch this test will actually create,
        # and mark it active so close_sprint's lifecycle can proceed.
        write_frontmatter(
            sprint_dir / "sprint.md",
            {
                "id": sprint_id,
                "title": "Cadence Dry Run",
                "status": "active",
                "branch": branch_name,
            },
        )

        _advance_to_ticketing(work_dir, sprint_id)

        # --- Create 3 tickets (the ticket's "3+-ticket sprint" requirement).
        ticket_paths = []
        for i in range(3):
            create_ticket(sprint_id, f"Do thing {i}")
            ticket_path = sprint_dir / "tickets" / f"00{i + 1}-do-thing-{i}.md"
            assert ticket_path.exists(), f"expected ticket file at {ticket_path}"
            ticket_paths.append(ticket_path)

        db_path = work_dir / ".clasi" / ".clasi.db"
        acquire_lock(db_path, sprint_id)
        advance_phase(db_path, sprint_id)  # ticketing -> executing

        # --- Create the real sprint branch and commit three tickets' worth
        # of work on it -- under the NEW policy, no manual bump commit
        # accompanies any of these (that's the whole point being tested).
        _run(["git", "checkout", "-b", branch_name], cwd=work_dir)
        for i, ticket_path in enumerate(ticket_paths):
            (work_dir / f"feature_{i}.py").write_text(
                f"# work for ticket {i}\n", encoding="utf-8"
            )
            update_ticket_status(str(ticket_path), "done")
            move_ticket_to_done(str(ticket_path))
            _git_commit(work_dir, f"feat: implement ticket {i} ({sprint_id}-00{i + 1})")

        # Sanity check: three ticket commits landed, zero bump commits yet --
        # this is what "no per-ticket bump" looks like on disk.
        assert _ticket_commit_count(work_dir) == 3
        assert _bump_commit_count(work_dir) == 0

        advance_phase(db_path, sprint_id)  # executing -> closing
        advance_phase(db_path, sprint_id)  # closing -> done

        # --- Close the sprint through the real close_sprint MCP tool:
        # full lifecycle (precondition self-repair, archive, real git
        # rebase + --no-ff merge, real version bump + tag). Tests are
        # skipped (test_command="") because this is a synthetic repo with
        # no test suite of its own; push/branch-delete are disabled to
        # keep the test hermetic (no remote, no destructive branch state).
        result = json.loads(
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command="",
            )
        )
        assert result["status"] == "success", result
        assert result["git"]["merged"] is True
        assert "version" in result, "close_sprint did not report a version bump"

        # --- The actual assertion this ticket exists to prove: at most
        # 1-2 bump commits for the WHOLE sprint, not one per ticket (which
        # would be 3, matching the noise pattern the issue measured).
        bump_commits = _bump_commit_count(work_dir)
        assert bump_commits == 1, (
            f"expected exactly 1 bump commit for a 3-ticket sprint under "
            f"the new cadence, found {bump_commits}"
        )
        assert bump_commits <= 2

        # And the 3 ticket commits are still exactly 3 -- confirming no
        # bump commits were interleaved among them (the old one-per-ticket
        # pattern would show ticket/bump pairs; this shows a clean 3:1
        # ticket-to-bump ratio instead of 3:3).
        assert _ticket_commit_count(work_dir) == 3

        # --- No double-bump: close_sprint's own version_trigger gate is
        # the ONLY bump site now that manual per-commit bumps are gone.
        # Calling it once must not somehow produce two bump commits (e.g.
        # one from _close_sprint_full's own commit step plus a stray
        # leftover from a legacy path).
        tags = _run(["git", "tag", "-l"], cwd=work_dir).stdout.split()
        assert len(tags) <= 1, f"expected at most one version tag, found {tags}"


class TestVersionBumpCommitScoping:
    """Regression for 027/002: close_sprint's real bump commit sweeping
    unrelated untracked/modified files into the release commit (sprint
    026's config/devices.json incident, 'chore: bump version to
    0.20260819.1', 5b9afb7). Drives the same real `close_sprint` path as
    the cadence test above, but the point here is what the bump commit's
    file list contains, not how many bump commits exist.
    """

    def test_bump_commit_excludes_unrelated_untracked_and_modified_files(
        self, work_dir: Path
    ) -> None:
        # An unrelated tracked file that predates the sprint branch --
        # committed to master before the branch exists, so its committed
        # content is bit-identical on both master and the sprint branch.
        # It gets a local, uncommitted modification right before
        # close_sprint runs and is never staged by any ticket commit --
        # exactly the config/devices.json shape (untracked before the
        # fix; here proven for both untracked *and* modified-tracked).
        # Keeping the committed blob identical on both branches also
        # means the merge step's real `git rebase` + `git checkout
        # master` + `git merge --no-ff` never need to touch this path,
        # so the uncommitted local edit survives the whole lifecycle
        # undisturbed regardless of the bug being tested.
        tracked_file = work_dir / "unrelated_tracked.txt"
        tracked_file.write_text("original\n", encoding="utf-8")
        _run(["git", "add", "unrelated_tracked.txt"], cwd=work_dir)
        _run(
            ["git", "commit", "-m", "chore: add unrelated tracked file"],
            cwd=work_dir,
        )

        create_result = json.loads(create_sprint("Scoped Bump"))
        sprint_id = create_result["id"]
        sprint_dir = Path(create_result["path"])
        branch_name = create_result["branch"]

        write_frontmatter(
            sprint_dir / "sprint.md",
            {
                "id": sprint_id,
                "title": "Scoped Bump",
                "status": "active",
                "branch": branch_name,
            },
        )

        _advance_to_ticketing(work_dir, sprint_id)

        create_ticket(sprint_id, "Do thing")
        ticket_path = sprint_dir / "tickets" / "001-do-thing.md"
        assert ticket_path.exists(), f"expected ticket file at {ticket_path}"

        db_path = work_dir / ".clasi" / ".clasi.db"
        acquire_lock(db_path, sprint_id)
        advance_phase(db_path, sprint_id)  # ticketing -> executing

        _run(["git", "checkout", "-b", branch_name], cwd=work_dir)

        (work_dir / "feature.py").write_text("# ticket work\n", encoding="utf-8")
        update_ticket_status(str(ticket_path), "done")
        move_ticket_to_done(str(ticket_path))
        _git_commit(work_dir, f"feat: implement ticket ({sprint_id}-001)")

        # Seed the unrelated untracked file and modify the unrelated
        # tracked file. Both are left deliberately uncommitted, planted
        # after the last ticket commit -- nothing in this sprint's own
        # work ever touches or stages them.
        untracked_file = work_dir / "unrelated_untracked.txt"
        untracked_file.write_text("scratch\n", encoding="utf-8")
        tracked_file.write_text("locally modified, never staged\n", encoding="utf-8")

        advance_phase(db_path, sprint_id)  # executing -> closing
        advance_phase(db_path, sprint_id)  # closing -> done

        result = json.loads(
            close_sprint(
                sprint_id=sprint_id,
                branch_name=branch_name,
                main_branch="master",
                push_tags=False,
                delete_branch=False,
                test_command="",
            )
        )
        assert result["status"] == "success", result
        assert "version" in result, "close_sprint did not report a version bump"

        # Both files remain exactly as left: the untracked file is still
        # untracked, and the tracked file's local edit is still unstaged
        # -- neither was swept into any commit the close created.
        status = _run(["git", "status", "--porcelain"], cwd=work_dir).stdout
        assert "?? unrelated_untracked.txt" in status, status
        assert " M unrelated_tracked.txt" in status, status
        assert untracked_file.read_text(encoding="utf-8") == "scratch\n"
        assert (
            tracked_file.read_text(encoding="utf-8")
            == "locally modified, never staged\n"
        )

        # The bump commit's changed-file list is exactly the version file
        # it wrote -- no incidental inclusions from either unrelated file
        # (a full assertion needs both: nothing extra went in, and the
        # unrelated files stayed out).
        log = _run(["git", "log", "--all", "--oneline"], cwd=work_dir).stdout
        bump_lines = [
            line for line in log.splitlines() if "chore: bump version to" in line
        ]
        assert len(bump_lines) == 1, f"expected exactly one bump commit, found {bump_lines}"
        bump_sha = bump_lines[0].split()[0]

        changed_files = _run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", bump_sha],
            cwd=work_dir,
        ).stdout.split()
        # The bump commit legitimately includes the paths this close run's
        # own steps produced -- the version file, plus the archived sprint
        # directory's old/new location (Step 3's move, which close_sprint
        # has always folded into this same commit so the tree is clean for
        # Step 6's merge, and which this ticket does not touch). The one
        # thing that must never appear here is a file that predates the
        # close and belongs to no ticket -- exactly the config/devices.json
        # shape from the sprint 026 incident, reproduced here as both an
        # untracked and a modified-tracked file.
        assert "pyproject.toml" in changed_files, (
            f"bump commit must include the version file, found {changed_files}"
        )
        assert "unrelated_untracked.txt" not in changed_files, changed_files
        assert "unrelated_tracked.txt" not in changed_files, changed_files
