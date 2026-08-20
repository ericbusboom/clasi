"""ClasiStateReader — production StateReader implementation.

This module provides :class:`ClasiStateReader`, which satisfies the
:class:`~clasi.state_machine.context.StateReader` protocol by reading
real data from three sources:

- **Filesystem**: Path existence checks, markdown file reads
- **Git**: ``subprocess.run(["git", ...], cwd=project.root)``
- **StateDB**: ``project.db`` — the SQLite sprint lifecycle database

Each method is a direct read, no mutations.  All methods handle errors
gracefully and return safe defaults on failure (``False`` / ``""`` /
``None`` / ``0``).

As of sprint 026, the git-subprocess-backed methods (``git_branch``,
``default_branch``, ``branch_merged``) memoize their underlying
``subprocess.run`` result per :class:`ClasiStateReader` instance via
:meth:`ClasiStateReader._run_git` — never across instances or processes.
Every other method remains an uncached direct read on every call.

As of sprint 027, ``git_branch`` and ``default_branch`` additionally try
a direct loose-file read (``.git/HEAD`` / ``.git/refs/remotes/origin/HEAD``)
before falling back to the subprocess path — see
:meth:`ClasiStateReader._git_branch_fast` /
:meth:`ClasiStateReader._default_branch_fast`. The fallback, when taken,
is still memoized exactly as before. ``branch_merged`` is unchanged — it
always spawns a real ``git`` subprocess (a merge-base/ancestry check is
not a single ref-file read).

Data sources per method
-----------------------

+----------------------------+------------------+
| Method                     | Source           |
+============================+==================+
| file_exists                | Filesystem       |
| git_branch                 | .git/HEAD*       |
| default_branch             | .git/refs/*HEAD  |
| execution_lock             | StateDB          |
| sprint_phase               | StateDB          |
| sprint_gate                | StateDB          |
| sprint_branch              | sprint.md FM     |
| ticket_status              | ticket FM        |
| all_tickets_done           | ticket FMs       |
| ticket_in_done_dir         | Filesystem       |
| exception_block            | ticket FM        |
| programmer_dispatched      | ticket FM        |
| sprint_flag                | sprint.md FM     |
| branch_merged              | git subprocess   |
| dependencies_done          | ticket FMs       |
| acceptance_criteria_met    | ticket body text |
| tests_passing              | .clasi/test-cache|
| blocker_identified         | ticket FM        |
| blocker_resolved           | ticket FM        |
| reopen_requested           | ticket FM        |
| any_sprint_in_phase        | StateDB          |
| ticket_count               | Filesystem       |
| overview_exists            | Filesystem       |
| sprint_artifact_exists     | Filesystem       |
| ticket_file_present        | Filesystem       |
+----------------------------+------------------+

``*`` — fast path is a direct ref-file read; falls back to the git
subprocess call (memoized, as before) whenever it can't confidently
answer. See the sprint-027 paragraph above.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.project import Project

# Sentinel distinguishing "not yet resolved" from "resolved to None" in
# ClasiStateReader._git_dir()'s memoization -- None is itself a valid
# resolved value (no .git found at all).
_UNSET = object()

_HEADS_PREFIX = "refs/heads/"
_ORIGIN_HEAD_PREFIX = "refs/remotes/origin/"


def _looks_like_object_id(text: str) -> bool:
    """Return True if *text* looks like a full git object id (SHA-1/SHA-256).

    Used to recognize a detached-HEAD ``.git/HEAD`` payload (a raw hex
    object id) as opposed to a symbolic ref line or unrecognized content
    this module should not guess about.
    """
    return len(text) in (40, 64) and all(c in "0123456789abcdef" for c in text.lower())


class ClasiStateReader:
    """Production implementation of the ``StateReader`` protocol.

    Constructed from a :class:`~clasi.project.Project` instance.  All
    methods are read-only; none write to the filesystem, git, or the DB.

    Args:
        project: The :class:`~clasi.project.Project` whose state is being read.
    """

    def __init__(self, project: "Project") -> None:
        self._project = project
        # Per-instance git-subprocess memoization (sprint 026 / ticket 003).
        # Keyed on the git argument tuple (excluding the leading "git"
        # itself). Populated lazily on first call; a hook process
        # constructs exactly one ClasiStateReader and discards it at exit,
        # so this cache never outlives — or is shared across — a single
        # process. It exists purely to collapse the many repeated
        # predicate-driven calls to the SAME git query (e.g.
        # ``is_on_sprint_branch`` invoking ``git_branch()`` once per state/
        # transition it's checked against) into a single subprocess call.
        self._git_cache: dict[tuple[str, ...], "subprocess.CompletedProcess[str]"] = {}
        # Resolved real git-directory, memoized per instance (sprint 027 /
        # ticket 003) — see _git_dir().
        self._git_dir_cache: "Path | None | object" = _UNSET

    def _run_git(self, *args: str) -> "subprocess.CompletedProcess[str]":
        """Run ``git <args>`` in the project root, memoized per instance.

        Repeated calls with the identical *args* tuple within this
        reader's lifetime return the cached :class:`subprocess.CompletedProcess`
        instead of shelling out again. Never persisted across instances —
        see the cache-safety constraint in this sprint's ``status-DESIGN.md``
        overlay (process-lifetime only, no cross-invocation cache).
        """
        if args not in self._git_cache:
            self._git_cache[args] = subprocess.run(
                ["git", *args],
                cwd=self._project.root,
                capture_output=True,
                text=True,
            )
        return self._git_cache[args]

    # ------------------------------------------------------------------
    # Git-directory / ref-file fast path (sprint 027 / ticket 003)
    #
    # git_branch() and default_branch() answer questions git itself
    # resolves by reading a loose ref file (no repository-wide history
    # walk involved) — HEAD's symref for the current branch, and
    # refs/remotes/origin/HEAD's symref for the configured default
    # branch. Reading those files directly avoids spawning a `git`
    # subprocess entirely for the common case (about 20-30ms of process-
    # creation overhead per spawn on this machine, per 026/007's own
    # Measurement Notes), while falling back to the exact same
    # subprocess-based method used before whenever the fast path can't
    # confidently produce the answer (missing file, unreadable, or
    # unrecognized content) — so behavior for every edge case the
    # subprocess path already handled (non-git directory, detached HEAD,
    # no remote configured, ...) is unchanged.
    #
    # branch_merged() is NOT given a fast path: `git branch --merged
    # <default>` is a real ancestry/merge-base computation over the full
    # commit graph (loose objects + packfiles + packed-refs), not a
    # single ref-file read — reimplementing that from raw git internals
    # would risk exactly the "keep behavior identical" divergence this
    # ticket must avoid, for a call that (per profiling) only fires for
    # sprint states other than "executing" anyway.
    # ------------------------------------------------------------------

    def _git_dir(self) -> "Path | None":
        """Resolve and memoize this project's real git directory.

        Handles both a normal repository (``.git`` is a directory) and a
        linked worktree or submodule (``.git`` is a file containing a
        ``gitdir: <path>`` pointer, per git's own convention). Returns
        ``None`` if neither form is found — callers treat that as "fall
        back to the git subprocess", which itself already returns a safe
        default for a non-git directory.

        Memoized per instance: the answer cannot change within a single
        hook invocation's lifetime (same cache-lifetime contract as
        ``_git_cache`` above).
        """
        if self._git_dir_cache is _UNSET:
            self._git_dir_cache = self._resolve_git_dir()
        return self._git_dir_cache  # type: ignore[return-value]

    def _resolve_git_dir(self) -> "Path | None":
        dot_git = self._project.root / ".git"
        try:
            if dot_git.is_dir():
                return dot_git
            if dot_git.is_file():
                text = dot_git.read_text(encoding="utf-8").strip()
                if text.startswith("gitdir:"):
                    pointer = text[len("gitdir:"):].strip()
                    pointer_path = Path(pointer)
                    if not pointer_path.is_absolute():
                        pointer_path = (self._project.root / pointer_path).resolve()
                    if pointer_path.is_dir():
                        return pointer_path
        except Exception:
            pass
        return None

    def _read_ref_file(self, relative_path: str) -> "str | None":
        """Read a loose ref/HEAD file directly, bypassing a git spawn.

        Returns the stripped file content, or ``None`` if the git
        directory can't be resolved, the file doesn't exist, or it can't
        be read. ``None`` must always be treated by callers as "fall
        back to the subprocess-based path" — never as a semantic result
        (an empty/missing ref is not the same thing as "detached" or
        "no remote", which are decided by the *fallback* method's own
        established semantics).
        """
        git_dir = self._git_dir()
        if git_dir is None:
            return None
        try:
            path = git_dir / relative_path
            if not path.is_file():
                return None
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return None

    def _git_branch_fast(self) -> "str | None":
        """Resolve the current branch name from ``.git/HEAD`` directly.

        Mirrors ``git branch --show-current``'s own output exactly:
        attached HEAD returns the branch name; detached HEAD returns
        ``""``. Returns ``None`` (never a guess) whenever the file's
        content isn't one of those two recognized shapes, so the caller
        falls back to the real subprocess call.
        """
        content = self._read_ref_file("HEAD")
        if content is None:
            return None
        if content.startswith("ref:"):
            ref = content[len("ref:"):].strip()
            if ref.startswith(_HEADS_PREFIX):
                return ref[len(_HEADS_PREFIX):]
            return None  # symref outside refs/heads/ — don't guess
        if _looks_like_object_id(content):
            return ""  # detached HEAD, matches --show-current's empty output
        return None

    def _default_branch_fast(self) -> "str | None":
        """Resolve the default branch from ``refs/remotes/origin/HEAD``.

        That ref is always a symbolic ref when it exists at all (git
        never packs symrefs — only direct/OID refs go into
        ``packed-refs``), so a direct loose-file read is safe whenever
        the file is present. Returns ``None`` (never a guess, e.g. never
        "master") when the file is absent or unrecognized, so the caller
        falls back to the real subprocess call and its own established
        "master" fallback.
        """
        content = self._read_ref_file("refs/remotes/origin/HEAD")
        if content is None:
            return None
        if not content.startswith("ref:"):
            return None
        ref = content[len("ref:"):].strip()
        if ref.startswith(_ORIGIN_HEAD_PREFIX):
            return ref[len(_ORIGIN_HEAD_PREFIX):]
        return ref

    # ------------------------------------------------------------------
    # Filesystem methods
    # ------------------------------------------------------------------

    def file_exists(self, path: str) -> bool:
        """Return True if *path* exists relative to the project root.

        Source: filesystem (``Path.exists()``).
        """
        try:
            return (self._project.root / path).exists()
        except Exception:
            return False

    def overview_exists(self) -> bool:
        """Return True iff the project overview file exists.

        Source: filesystem. Derives path from project.design_dir so that
        changing design_dir propagates automatically.
        """
        try:
            return (self._project.design_dir / "overview.md").exists()
        except Exception:
            return False

    def sprint_artifact_exists(self, sprint_id: str, artifact_name: str) -> bool:
        """Return True iff artifact_name exists in the sprint directory.

        Source: filesystem. Resolves the sprint dir via project.get_sprint()
        which uses ID-prefix glob (<id>-*), matching the write side exactly.
        Returns False if the sprint is not found or on any error.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            return (sprint.path / artifact_name).exists()
        except Exception:
            return False

    def ticket_file_present(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True iff a ticket file for ticket_id exists in the sprint's tickets tree.

        Source: filesystem. Delegates to _find_ticket_path which searches
        both tickets/ and tickets/done/ with slug-aware glob + frontmatter confirm.
        """
        return self._find_ticket_path(sprint_id, ticket_id) is not None

    # ------------------------------------------------------------------
    # Git methods
    # ------------------------------------------------------------------

    def git_branch(self) -> str:
        """Return the current git branch name.

        Source: a direct read of ``.git/HEAD`` (fast path — see
        :meth:`_git_branch_fast`) when that can confidently answer;
        otherwise falls back to ``git branch --show-current`` in
        ``project.root``, exactly as before. Returns ``""`` on any
        subprocess or decode error, or for a detached HEAD.

        The fallback subprocess call is memoized per instance via
        :meth:`_run_git` — repeated calls within one reader's lifetime
        shell out at most once.
        """
        fast = self._git_branch_fast()
        if fast is not None:
            return fast
        try:
            result = self._run_git("branch", "--show-current")
            if result.returncode != 0:
                return ""
            return result.stdout.strip()
        except Exception:
            return ""

    def default_branch(self) -> str:
        """Return the repository default branch name.

        Source: a direct read of ``.git/refs/remotes/origin/HEAD`` (fast
        path — see :meth:`_default_branch_fast`) when that file exists
        and resolves cleanly; otherwise falls back to ``git symbolic-ref
        refs/remotes/origin/HEAD`` exactly as before, with a fallback to
        ``"master"`` if the remote reference is not set.

        Resolution order:
        1. Direct read of ``refs/remotes/origin/HEAD`` under the
           resolved git directory → strip ``refs/remotes/origin/`` prefix.
        2. ``git symbolic-ref refs/remotes/origin/HEAD`` → strip
           ``refs/remotes/origin/`` prefix.
        3. Fall back to ``"master"``.

        The fallback subprocess call is memoized per instance via
        :meth:`_run_git` — repeated calls within one reader's lifetime
        shell out at most once.
        """
        fast = self._default_branch_fast()
        if fast is not None:
            return fast
        try:
            result = self._run_git("symbolic-ref", "refs/remotes/origin/HEAD")
            if result.returncode == 0:
                ref = result.stdout.strip()
                # refs/remotes/origin/main → main
                prefix = "refs/remotes/origin/"
                if ref.startswith(prefix):
                    return ref[len(prefix):]
                return ref
        except Exception:
            pass
        return "master"

    def branch_merged(self, sprint_id: str) -> bool:
        """Return True if the sprint branch has been merged into the default branch.

        Source: ``git branch --merged <default_branch>`` in ``project.root``.
        Reads the sprint branch name from the sprint.md frontmatter.
        Returns False on any error or if the branch name is empty.

        The ``git branch --merged <default>`` call itself does not depend
        on *sprint_id* — it lists every branch merged into the default
        branch, then checks membership — so it is memoized via
        :meth:`_run_git` keyed only on the resolved *default* branch name.
        Calling this for multiple sprints in the same reader instance
        shells out once, not once per sprint.
        """
        try:
            sprint_branch = self.sprint_branch(sprint_id)
            if not sprint_branch:
                return False
            default = self.default_branch()
            result = self._run_git("branch", "--merged", default)
            if result.returncode != 0:
                return False
            merged_branches = [b.strip().lstrip("* ") for b in result.stdout.splitlines()]
            return sprint_branch in merged_branches
        except Exception:
            return False

    # ------------------------------------------------------------------
    # StateDB methods
    # ------------------------------------------------------------------

    def execution_lock(self) -> dict | None:
        """Return the current execution lock dict, or None if no lock is held.

        Source: ``StateDB.get_lock_holder()``.
        """
        try:
            return self._project.db.get_lock_holder()
        except Exception:
            return None

    def sprint_phase(self, sprint_id: str) -> str:
        """Return the phase string for *sprint_id*.

        Source: ``StateDB.get_sprint_state()["phase"]``.
        Returns ``""`` if the sprint is not registered or any error occurs.
        """
        try:
            state = self._project.db.get_sprint_state(sprint_id)
            return state.get("phase", "")
        except Exception:
            return ""

    def sprint_gate(self, sprint_id: str, gate: str) -> dict | None:
        """Return the gate result dict for *sprint_id* / *gate*, or None.

        Source: ``StateDB.get_sprint_state()["gates"]`` — finds the entry
        matching *gate*.  Returns None if the gate has not been recorded or
        any error occurs.
        """
        try:
            state = self._project.db.get_sprint_state(sprint_id)
            for g in state.get("gates", []):
                if g.get("gate_name") == gate:
                    return g
            return None
        except Exception:
            return None

    def any_sprint_in_phase(self, phase: str) -> bool:
        """Return True if any *active* (non-archived) sprint is currently in *phase*.

        Source: iterates sprint directories and calls
        ``StateDB.get_sprint_state()`` for each registered sprint. A sprint
        whose directory lives under ``sprints/done/`` is archived and is
        excluded regardless of its recorded DB phase — an archived sprint
        can be permanently stuck at an earlier phase (e.g. its DB phase
        never advanced past ``ticketing`` even though its frontmatter
        status is ``done``), and counting it would produce a false
        positive that a real writer can never clear. Returns False on any
        error.
        """
        try:
            for sprint in self._project.list_sprints():
                sid = sprint.id
                if not sid:
                    continue
                try:
                    if sprint.path.parent.name == "done":
                        continue
                except Exception:
                    pass
                try:
                    state = self._project.db.get_sprint_state(sid)
                    if state.get("phase") == phase:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Sprint frontmatter methods
    # ------------------------------------------------------------------

    def sprint_branch(self, sprint_id: str) -> str:
        """Return the git branch name associated with *sprint_id*.

        Source: sprint.md frontmatter ``branch:`` field.
        Returns ``""`` if the sprint is not found or has no branch field.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            return sprint.branch
        except Exception:
            return ""

    def sprint_flag(self, sprint_id: str, flag: str) -> str:
        """Return the value of a sprint flag from sprint.md frontmatter.

        Source: sprint.md frontmatter — looks up *flag* as a key.
        Returns ``""`` if the sprint is not found, the key is absent, or
        the value is not a string.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            val = sprint.sprint_doc.frontmatter.get(flag, "")
            return str(val) if val is not None else ""
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Ticket helper: locate a ticket file
    # ------------------------------------------------------------------

    def _find_ticket_path(self, sprint_id: str, ticket_id: str) -> Path | None:
        """Return the Path to the ticket file for *sprint_id* / *ticket_id*.

        Searches both ``tickets/`` and ``tickets/done/`` directories.
        Returns None if not found.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            # Search active tickets directory first, then done/
            for location in [sprint.tickets_dir, sprint.tickets_done_dir]:
                if not location.exists():
                    continue
                for f in location.glob("*.md"):
                    # Fast filename check: most ticket files start with the ID
                    if f.stem.startswith(ticket_id + "-") or f.stem == ticket_id:
                        # Confirm by reading frontmatter
                        from clasi.frontmatter import read_frontmatter
                        fm = read_frontmatter(f)
                        if fm.get("id") == ticket_id:
                            return f
        except Exception:
            pass
        return None

    def _read_ticket_frontmatter(self, sprint_id: str, ticket_id: str) -> dict:
        """Return the frontmatter dict for the ticket, or {} on any error."""
        path = self._find_ticket_path(sprint_id, ticket_id)
        if path is None:
            return {}
        try:
            from clasi.frontmatter import read_frontmatter
            return read_frontmatter(path)
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Ticket methods
    # ------------------------------------------------------------------

    def ticket_status(self, sprint_id: str, ticket_id: str) -> str:
        """Return the status string for the given ticket.

        Source: ticket frontmatter ``status:`` field.
        Returns ``""`` if the ticket is not found.
        """
        fm = self._read_ticket_frontmatter(sprint_id, ticket_id)
        return fm.get("status", "")

    def all_tickets_done(self, sprint_id: str) -> bool:
        """Return True if every active ticket in *sprint_id* has status ``done``.

        Source: ticket frontmatter files in ``tickets/`` (not ``tickets/done/`` —
        those are already confirmed done by their location). Listed via the
        shared ``list_ticket_files`` helper (sprint 030 ticket 003), which
        excludes ``*-plan.md`` companion files — a stray plan file left in
        ``tickets/`` cannot make this permanently False.

        A sprint with no active tickets (empty ``tickets/`` directory) returns
        True — there is nothing blocking completion.

        Returns False on any filesystem or frontmatter error.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            tickets_dir = sprint.tickets_dir
            from clasi.frontmatter import read_frontmatter
            from clasi.ticket import list_ticket_files
            for f in list_ticket_files(tickets_dir):
                try:
                    fm = read_frontmatter(f)
                    if fm.get("status") != "done":
                        return False
                except Exception:
                    return False
            return True
        except Exception:
            return False

    def ticket_in_done_dir(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if the ticket file is under ``tickets/done/``.

        Source: filesystem — checks parent directory name of the ticket file.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            done_dir = sprint.tickets_done_dir
            if not done_dir.exists():
                return False
            # Only search the done directory
            from clasi.frontmatter import read_frontmatter
            for f in done_dir.glob("*.md"):
                try:
                    fm = read_frontmatter(f)
                    if fm.get("id") == ticket_id:
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def exception_block(self, sprint_id: str, ticket_id: str) -> dict | None:
        """Return the exception block dict for *ticket_id*, or None.

        Source: ticket frontmatter ``exception:`` block.
        Returns None if absent or if the value is not a dict.
        """
        fm = self._read_ticket_frontmatter(sprint_id, ticket_id)
        val = fm.get("exception")
        return dict(val) if isinstance(val, dict) else None

    def programmer_dispatched(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if a programmer agent has been dispatched for *ticket_id*.

        Source: ticket frontmatter ``status:`` field.

        Implementation note: we use ``status == "in-progress"`` as a proxy for
        "a programmer has been dispatched."  The ``active_agents`` table records
        only *running* agents and is cleared on agent stop, so it cannot reliably
        indicate past dispatch.  A ticket transitions to ``in-progress`` exactly
        when the programmer agent begins work, making this the most stable signal
        available from durable storage.
        """
        return self.ticket_status(sprint_id, ticket_id) == "in-progress"

    def dependencies_done(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if all tickets in ``depends-on`` for *ticket_id* are done.

        Source: ticket frontmatter ``depends-on:`` list; each entry is checked
        via :meth:`ticket_status`.

        Returns True if the ``depends-on`` list is empty (no dependencies).
        Returns False on any error.
        """
        fm = self._read_ticket_frontmatter(sprint_id, ticket_id)
        depends_on = fm.get("depends-on", [])
        if isinstance(depends_on, str):
            depends_on = [depends_on] if depends_on else []
        if not depends_on:
            return True
        for dep_id in depends_on:
            status = self.ticket_status(sprint_id, str(dep_id))
            if status != "done":
                return False
        return True

    def acceptance_criteria_met(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if all acceptance-criteria checkboxes in the ticket are checked.

        Source: ticket body text — scans for Markdown checkboxes.

        Logic:
        - If any ``- [ ]`` (unchecked) checkbox is found, returns False.
        - If at least one ``- [x]`` (checked) is found and none are unchecked,
          returns True.
        - If no checkboxes are found at all, returns False (cannot confirm met).

        Returns False on any error.
        """
        path = self._find_ticket_path(sprint_id, ticket_id)
        if path is None:
            return False
        try:
            from clasi.frontmatter import read_document
            _, body = read_document(path)
            has_checked = False
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("- [ ]"):
                    return False  # At least one unchecked — not met
                if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
                    has_checked = True
            return has_checked
        except Exception:
            return False

    def tests_passing(self) -> bool:
        """Return True if the project's test suite is known to be passing.

        Source: ``.clasi/test-cache`` marker file in the project's ``.clasi/``
        directory.

        Implementation note: running the full test suite on every ``clasi status``
        call would be unacceptably slow.  This method reads a cached signal instead.
        The ``.clasi/test-cache`` file is written by CI or a post-commit hook
        (not by ``clasi status`` itself) to record that the tests passed.  If the
        file is absent, we conservatively return False.
        """
        try:
            return (self._project.clasi_dir / "test-cache").exists()
        except Exception:
            return False

    def blocker_identified(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if a non-empty exception block is present in the ticket.

        Source: ticket frontmatter ``exception:`` block.
        An exception block that is a non-empty dict counts as a blocker.
        """
        block = self.exception_block(sprint_id, ticket_id)
        return bool(block)

    def blocker_resolved(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if the exception block has been resolved.

        Source: ticket frontmatter ``exception:`` block; checks for
        ``resolved: true``.
        """
        block = self.exception_block(sprint_id, ticket_id)
        if not block:
            return False
        return bool(block.get("resolved"))

    def reopen_requested(self, sprint_id: str, ticket_id: str) -> bool:
        """Return True if the ticket has ``reopen_requested: true`` in frontmatter.

        Source: ticket frontmatter ``reopen_requested:`` field.
        """
        fm = self._read_ticket_frontmatter(sprint_id, ticket_id)
        return bool(fm.get("reopen_requested"))

    def ticket_count(self, sprint_id: str) -> int:
        """Return the number of ticket ``.md`` files in ``tickets/`` (excluding ``done/``).

        Source: the shared ``list_ticket_files`` helper (sprint 030 ticket
        003) on ``tickets/``, which excludes ``*-plan.md`` companion files
        so a stray plan file cannot inflate this count.
        Returns 0 if the directory does not exist or on any error.
        """
        try:
            sprint = self._project.get_sprint(sprint_id)
            tickets_dir = sprint.tickets_dir
            from clasi.ticket import list_ticket_files
            return len(list_ticket_files(tickets_dir))
        except Exception:
            return 0
