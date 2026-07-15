"""Sprint: OO wrapper around a sprint directory."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING


class MergeConflictError(RuntimeError):
    """Raised by Sprint.merge_branch() when a merge conflict occurs.

    Attributes:
        conflicted_files: List of files with conflicts (may be empty).
    """

    def __init__(self, message: str, conflicted_files: list[str]) -> None:
        super().__init__(message)
        self.conflicted_files = conflicted_files

from clasi.artifact import Artifact
from clasi.templates import (
    SPRINT_TEMPLATE,
    TICKET_TEMPLATE,
    slugify,
)

if TYPE_CHECKING:
    from clasi.project import Project
    from clasi.ticket import Ticket


class Sprint:
    """A sprint directory with its planning artifacts and tickets."""

    def __init__(self, path: Path, project: Project):
        self._path = Path(path)
        self._project = project

    @property
    def path(self) -> Path:
        return self._path

    @property
    def project(self) -> Project:
        return self._project

    @property
    def id(self) -> str:
        """From sprint.md frontmatter 'id' field."""
        return self.sprint_doc.frontmatter.get("id", "")

    @property
    def title(self) -> str:
        """From sprint.md frontmatter 'title' field."""
        return self.sprint_doc.frontmatter.get("title", "")

    @property
    def slug(self) -> str:
        """Directory name without the ID prefix."""
        name = self._path.name
        sid = self.id
        if sid and name.startswith(sid + "-"):
            return name[len(sid) + 1 :]
        return name

    @property
    def branch(self) -> str:
        """From sprint.md frontmatter 'branch' field."""
        return self.sprint_doc.frontmatter.get("branch", "")

    @property
    def status(self) -> str:
        """From sprint.md frontmatter 'status' field."""
        return self.sprint_doc.frontmatter.get("status", "unknown")

    @property
    def worktree(self) -> bool:
        """From sprint.md frontmatter 'worktree' field. Opt-in for parallel
        execution; default False (serial) for backward compatibility."""
        return bool(self.sprint_doc.frontmatter.get("worktree", False))

    @property
    def phase(self) -> str:
        """From StateDB if available, else inferred from directory location."""
        sid = self.id
        if sid:
            try:
                state = self._project.db.get_sprint_state(sid)
                return state.get("phase", "unknown")
            except Exception:
                pass
        # Fallback: if under done/, phase is "done"
        if self._path.parent.name == "done":
            return "done"
        return "unknown"

    # --- Named artifacts ---

    @property
    def sprint_doc(self) -> Artifact:
        """sprint.md artifact."""
        return Artifact(self._path / "sprint.md")

    @property
    def usecases(self) -> Artifact:
        """usecases.md artifact."""
        return Artifact(self._path / "usecases.md")

    @property
    def technical_plan(self) -> Artifact:
        """technical-plan.md artifact."""
        return Artifact(self._path / "technical-plan.md")

    @property
    def architecture(self) -> Artifact:
        """architecture-update.md artifact."""
        return Artifact(self._path / "architecture-update.md")

    # --- Well-known file paths ---

    @property
    def sprint_md(self) -> Path:
        """Path to sprint.md."""
        return self._path / "sprint.md"

    @property
    def usecases_md(self) -> Path:
        """Path to usecases.md."""
        return self._path / "usecases.md"

    @property
    def architecture_update_md(self) -> Path:
        """Path to architecture-update.md."""
        return self._path / "architecture-update.md"

    @property
    def tickets_dir(self) -> Path:
        """Path to the tickets/ directory."""
        return self._path / "tickets"

    @property
    def tickets_done_dir(self) -> Path:
        """Path to the tickets/done/ directory."""
        return self._path / "tickets" / "done"

    @property
    def issues_dir(self) -> Path:
        """Path to the issues/ directory within this sprint."""
        return self._path / "issues"

    @property
    def issues_done_dir(self) -> Path:
        """Path to the issues/done/ directory within this sprint."""
        return self._path / "issues" / "done"

    # --- Ticket management ---

    def list_tickets(self, status: str | None = None) -> list[Ticket]:
        """List tickets in this sprint, optionally filtered by status."""
        from clasi.ticket import Ticket
        from clasi.frontmatter import read_frontmatter

        results: list[Ticket] = []

        for location in [self.tickets_dir, self.tickets_done_dir]:
            if not location.exists():
                continue
            for f in sorted(location.glob("*.md")):
                fm = read_frontmatter(f)
                if status and fm.get("status") != status:
                    continue
                results.append(Ticket(f, self))

        return results

    def list_issues(self) -> list:
        """List Issue objects from issues/ and issues/done/ directories.

        Returns Issue objects for all *.md files found in both
        ``self.issues_dir`` and ``self.issues_done_dir``, in sorted order.
        Returns an empty list if neither directory exists.
        """
        from clasi.issue import Issue

        results: list = []
        for location in [self.issues_dir, self.issues_done_dir]:
            if not location.exists():
                continue
            for f in sorted(location.glob("*.md")):
                results.append(Issue(f, self._project))
        return results

    def get_ticket(self, ticket_id: str) -> Ticket:
        """Get a ticket by its ID."""
        from clasi.ticket import Ticket
        from clasi.frontmatter import read_frontmatter

        for location in [self.tickets_dir, self.tickets_done_dir]:
            if not location.exists():
                continue
            for f in sorted(location.glob("*.md")):
                fm = read_frontmatter(f)
                if fm.get("id") == ticket_id:
                    return Ticket(f, self)
        raise ValueError(f"Ticket '{ticket_id}' not found in sprint {self.id}")

    def create_ticket(self, title: str, issue: str | None = None) -> Ticket:
        """Create a new ticket in this sprint's tickets/ directory.

        When ``issue`` is not provided, automatically links to issues
        listed in the sprint's ``sprint.md`` frontmatter ``todos`` field.
        """
        from clasi.ticket import Ticket
        from clasi.frontmatter import read_frontmatter

        # Auto-link to sprint issues when no explicit issue given
        if issue is None:
            sprint_issues = self.sprint_doc.frontmatter.get("todos")
            if sprint_issues and isinstance(sprint_issues, list):
                if len(sprint_issues) == 1:
                    issue = sprint_issues[0]

        self.tickets_dir.mkdir(parents=True, exist_ok=True)
        self.tickets_done_dir.mkdir(exist_ok=True)

        ticket_id = self._next_ticket_id()
        ticket_slug = slugify(title)
        path = self.tickets_dir / f"{ticket_id}-{ticket_slug}.md"

        content = TICKET_TEMPLATE.format(id=ticket_id, title=title)
        path.write_text(content, encoding="utf-8")

        if issue is not None:
            fm = read_frontmatter(path)
            fm["issue"] = issue
            Artifact(path).write(fm, Artifact(path).content)

        return Ticket(path, self)

    def _next_ticket_id(self) -> str:
        """Determine the next ticket number within this sprint."""
        from clasi.frontmatter import read_frontmatter

        max_id = 0
        for location in [self.tickets_dir, self.tickets_done_dir]:
            if not location.exists():
                continue
            for f in location.glob("*.md"):
                fm = read_frontmatter(f)
                try:
                    num = int(fm.get("id", "0"))
                    max_id = max(max_id, num)
                except (ValueError, TypeError):
                    pass
        return f"{max_id + 1:03d}"

    # --- Git branch management ---

    def create_branch(self) -> str:
        """Create the sprint git branch and check it out.

        Uses the branch name from sprint.md frontmatter.  If the branch
        already exists, checks it out instead of creating a new one.

        Returns the branch name on success.
        Raises RuntimeError if git operations fail.
        """
        branch_name = self.branch
        if not branch_name:
            raise RuntimeError(
                f"Sprint {self.id} has no 'branch' field in sprint.md frontmatter"
            )

        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Branch may already exist — try checking it out
            result = subprocess.run(
                ["git", "checkout", branch_name],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to create/checkout branch '{branch_name}': "
                    f"{result.stderr.strip()}"
                )
        return branch_name

    def merge_branch(self, main_branch: str = "master") -> dict:
        """Merge the sprint branch into main_branch using --no-ff.

        Idempotent: if the branch no longer exists or is already an
        ancestor of main_branch, returns without error.

        Returns a dict with keys:
          - branch_exists (bool)
          - merged (bool)
          - already_merged (bool)

        Raises RuntimeError on checkout or merge failure (conflict
        information is included in the message).
        """
        branch_name = self.branch
        if not branch_name:
            raise RuntimeError(
                f"Sprint {self.id} has no 'branch' field in sprint.md frontmatter"
            )

        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            capture_output=True,
            text=True,
        ).returncode == 0

        if not branch_exists:
            return {"branch_exists": False, "merged": True, "already_merged": True}

        is_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", branch_name, main_branch],
            capture_output=True,
            text=True,
        ).returncode == 0

        if is_ancestor:
            return {"branch_exists": True, "merged": True, "already_merged": True}

        # Rebase sprint branch onto main before merging.
        # Two-argument form avoids requiring a checkout first:
        #   git rebase <upstream> <branch>
        rebase = subprocess.run(
            ["git", "rebase", main_branch, branch_name],
            capture_output=True,
            text=True,
        )
        if rebase.returncode != 0:
            subprocess.run(["git", "rebase", "--abort"], capture_output=True)
            raise RuntimeError(
                f"Rebase of {branch_name} onto {main_branch} failed: "
                f"{rebase.stderr.strip()}"
            )

        checkout = subprocess.run(
            ["git", "checkout", main_branch],
            capture_output=True,
            text=True,
        )
        if checkout.returncode != 0:
            raise RuntimeError(
                f"Failed to checkout {main_branch}: {checkout.stderr.strip()}"
            )

        merge = subprocess.run(
            ["git", "merge", "--no-ff", branch_name],
            capture_output=True,
            text=True,
        )
        if merge.returncode != 0:
            conflict_result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                capture_output=True,
                text=True,
            )
            conflicted = [
                f.strip()
                for f in conflict_result.stdout.strip().split("\n")
                if f.strip()
            ]
            subprocess.run(["git", "merge", "--abort"], capture_output=True)
            raise MergeConflictError(
                f"Merge conflict: {merge.stderr.strip()}",
                conflicted_files=conflicted,
            )

        return {"branch_exists": True, "merged": True, "already_merged": False}

    def delete_branch(self) -> bool:
        """Delete the sprint branch locally.

        Uses `git branch -d` (safe delete — refuses if unmerged).

        Returns True if the branch was deleted, False if it did not exist.
        Raises RuntimeError if the delete command fails for another reason.
        """
        branch_name = self.branch
        if not branch_name:
            raise RuntimeError(
                f"Sprint {self.id} has no 'branch' field in sprint.md frontmatter"
            )

        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            capture_output=True,
            text=True,
        ).returncode == 0

        if not branch_exists:
            return False

        result = subprocess.run(
            ["git", "branch", "-d", branch_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to delete branch '{branch_name}': {result.stderr.strip()}"
            )
        return True

    def ticket_counts(self) -> dict:
        """Return a count of tickets by status.

        Returns a dict with keys: open, in_progress, done, exception.
        Only counts tickets that have a non-empty id field.
        """
        counts: dict[str, int] = {"open": 0, "in_progress": 0, "done": 0, "exception": 0}
        for ticket in self.list_tickets():
            if not ticket.id:
                continue
            s = ticket.status
            if s == "in-progress":
                s = "in_progress"
            if s in counts:
                counts[s] += 1
        return counts

    def detail_promote(self) -> dict:
        """Promote a sprint from roadmap phase to planning-docs phase.

        Under the single-doc model, use cases and architecture live as
        sections inside sprint.md — there is nothing left to scaffold for
        them. This method creates tickets/ and tickets/done/ onto the
        sprint directory, then advances the state DB phase from 'roadmap'
        to 'planning-docs'.

        Returns a dict: {"sprint_id": ..., "phase": "planning-docs",
                          "files_written": [...]}.

        Raises ValueError if the sprint is not in roadmap phase or if the
        sprint has already been detail-planned (tickets/ already exists).
        """
        current_phase = self.phase
        if current_phase != "roadmap":
            raise ValueError(
                f"Sprint {self.id} is not in roadmap phase (current: {current_phase})"
            )

        if self.tickets_dir.exists():
            raise ValueError(
                f"Sprint {self.id} is already detail-planned (tickets/ exists)"
            )

        sprint_id = self.id

        files_written: list[str] = []

        # Create tickets/ and tickets/done/ directories
        self.tickets_dir.mkdir(parents=True, exist_ok=True)
        self.tickets_done_dir.mkdir(exist_ok=True)
        files_written.append(str(self.tickets_dir))
        files_written.append(str(self.tickets_done_dir))

        # Update sprint.md frontmatter status to reflect new phase
        self.sprint_doc.update_frontmatter(status="planning-docs")

        # Advance phase from roadmap -> planning-docs
        self.advance_phase()

        return {
            "sprint_id": sprint_id,
            "phase": "planning-docs",
            "files_written": files_written,
        }

    def archive(self) -> dict:
        """Archive this sprint by updating status to 'done' and moving to sprints/done/.

        Under the single-doc model, architecture lives as a section inside
        sprint.md — there is nothing to copy into a dedicated architecture
        directory (full architecture consolidation, if wanted, is done on
        demand from sprint.md history via the consolidate-architecture
        skill, writing to ``project.design_dir``).

        Returns a dict with keys: old_path, new_path.
        Raises ValueError if the destination already exists.
        """
        import shutil

        sprint_dir = self._path
        project = self._project

        # Update sprint status to the state machine's terminal state.
        # `closed` is the only terminal state sprint.yaml defines; writing
        # `done` here (as this did until 019-007) minted a status the
        # machine does not recognise, which detect_inconsistencies then
        # reported as permanent state_drift. Sprints archived before that
        # fix still carry `status: done` on disk and are tolerated on read.
        self.sprint_doc.update_frontmatter(status="closed")

        # Move to done directory
        done_dir = project.sprints_dir / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        new_path = done_dir / sprint_dir.name

        if new_path.exists():
            raise ValueError(f"Destination already exists: {new_path}")

        shutil.move(str(sprint_dir), str(new_path))
        self._path = new_path

        return {"old_path": str(sprint_dir), "new_path": str(new_path)}

    # --- Serialization ---

    def to_dict(self) -> dict:
        """Serialize sprint to a plain dict suitable for JSON return.

        All Path objects are converted to strings.
        Returns keys: id, path, branch, files, phase.
        """
        return {
            "id": self.id,
            "path": str(self.path),
            "branch": self.branch,
            "files": {
                "sprint.md": str(self.sprint_md),
            },
            "phase": self.phase,
        }

    # --- Phase management (delegates to project.db) ---

    def advance_phase(self) -> dict:
        """Advance this sprint's phase in the state DB."""
        return self._project.db.advance_phase(self.id)

    def record_gate(self, gate: str, result: str, notes: str | None = None) -> dict:
        """Record a gate result for this sprint."""
        return self._project.db.record_gate(self.id, gate, result, notes)

    def acquire_lock(self) -> dict:
        """Acquire the execution lock for this sprint."""
        return self._project.db.acquire_lock(self.id)

    def release_lock(self) -> dict:
        """Release the execution lock for this sprint."""
        return self._project.db.release_lock(self.id)
