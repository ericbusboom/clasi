#!/usr/bin/env python3
"""E2E verification script for CLASI-built projects.

Takes a completed project directory (output of ``run_e2e.py``) and
validates that both the application and the CLASI process artifacts are
correct.

Usage::

    python tests/e2e/verify.py <project-dir>

Exit code 0 means all checks passed; non-zero means at least one failed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


class CheckResult(NamedTuple):
    name: str
    passed: bool
    detail: str = ""


def _pass(name: str, detail: str = "") -> CheckResult:
    return CheckResult(name=name, passed=True, detail=detail)


def _fail(name: str, detail: str = "") -> CheckResult:
    return CheckResult(name=name, passed=False, detail=detail)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _check_app_starts(project_dir: Path) -> CheckResult:
    """Verify that ``python -m guessing_game`` starts without errors."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "guessing_game"],
            cwd=str(project_dir),
            input="q\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return _pass("Application starts")
        return _fail("Application starts", f"exit {result.returncode}: {result.stderr[:200]}")
    except FileNotFoundError:
        return _fail("Application starts", "guessing_game package not found")
    except subprocess.TimeoutExpired:
        return _fail("Application starts", "timed out after 10s")


def _check_menu(project_dir: Path) -> CheckResult:
    """Verify the menu displays the expected options."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "guessing_game"],
            cwd=str(project_dir),
            input="q\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = result.stdout
        if "1." in out and "2." in out and "3." in out and "q" in out.lower():
            return _pass("Menu displays correctly")
        return _fail("Menu displays correctly", f"unexpected output: {out[:200]}")
    except Exception as exc:
        return _fail("Menu displays correctly", str(exc))


def _play_game(project_dir: Path, choice: str, guess: str, name: str) -> CheckResult:
    """Play a game with the correct guess and check for success."""
    try:
        # Send: choice, correct guess, then quit
        stdin_text = f"{choice}\n{guess}\nq\n"
        result = subprocess.run(
            [sys.executable, "-m", "guessing_game"],
            cwd=str(project_dir),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=10,
        )
        out = result.stdout.lower()
        if "correct" in out or "got it" in out:
            return _pass(f"Game {choice} works ({name})")
        return _fail(f"Game {choice} works ({name})", f"no success message in: {result.stdout[:300]}")
    except Exception as exc:
        return _fail(f"Game {choice} works ({name})", str(exc))


def _check_sprints(project_dir: Path) -> CheckResult:
    """Verify 4 sprint directories exist in done/ with correct status."""
    done_dir = project_dir / "docs" / "clasi" / "sprints" / "done"
    if not done_dir.exists():
        return _fail("4 sprints completed", "done/ directory does not exist")

    sprint_dirs = [d for d in sorted(done_dir.iterdir()) if d.is_dir()]
    if len(sprint_dirs) < 4:
        return _fail("4 sprints completed", f"found {len(sprint_dirs)} sprint(s)")

    for sd in sprint_dirs[:4]:
        sprint_file = sd / "sprint.md"
        if not sprint_file.exists():
            return _fail("4 sprints completed", f"missing sprint.md in {sd.name}")
        content = sprint_file.read_text(encoding="utf-8")
        if "status: done" not in content:
            return _fail("4 sprints completed", f"sprint {sd.name} not status: done")

    return _pass("4 sprints completed", f"found {len(sprint_dirs)} sprint dir(s)")


def _check_tickets_done(project_dir: Path) -> CheckResult:
    """Verify all tickets are in done/ directories with done status."""
    done_dir = project_dir / "docs" / "clasi" / "sprints" / "done"
    if not done_dir.exists():
        return _fail("All tickets done", "sprints/done/ does not exist")

    issues = []
    for sd in sorted(done_dir.iterdir()):
        if not sd.is_dir():
            continue
        tickets_dir = sd / "tickets"
        if not tickets_dir.exists():
            continue

        # Check for tickets NOT in done/
        for f in tickets_dir.glob("*.md"):
            issues.append(f"ticket {f.name} in {sd.name}/tickets/ (not in done/)")

        # Check tickets in done/
        done_tickets = sd / "tickets" / "done"
        if done_tickets.exists():
            for f in done_tickets.glob("*.md"):
                content = f.read_text(encoding="utf-8")
                if "status: done" not in content:
                    issues.append(f"ticket {f.name} in {sd.name} not status: done")
                # Check acceptance criteria
                unchecked = re.findall(r"- \[ \]", content)
                if unchecked:
                    issues.append(f"ticket {f.name} in {sd.name} has {len(unchecked)} unchecked criteria")

    if issues:
        return _fail("All tickets done", "; ".join(issues[:5]))
    return _pass("All tickets done")


def _check_dispatch_logs(project_dir: Path) -> CheckResult:
    """Verify dispatch logs exist, contain content, and include sub-dispatch logs.

    Checks:
    - Log files exist and are non-empty.
    - Each sprint directory has at least one ``ticket-*`` log file
      (proving sprint-executor logged code-monkey dispatches).
    - Each sprint directory has planner sub-dispatch log files beyond
      any ``sprint-planner-*`` entries (e.g. ``architect-*``,
      ``architecture-reviewer-*``, ``technical-lead-*``).
    - Dispatches to templated agents include ``template_used`` in
      frontmatter.
    """
    import yaml

    # Agents that require template_used in their dispatch logs
    templated_agents = {"sprint-planner", "sprint-executor", "code-monkey"}

    log_dir = project_dir / "docs" / "clasi" / "log"
    if not log_dir.exists():
        return _fail("Dispatch logs exist", "log/ directory does not exist")

    log_files = list(log_dir.rglob("*.md"))
    if not log_files:
        return _fail("Dispatch logs exist", "no log files found")

    empty = [f.name for f in log_files if f.stat().st_size < 10]
    if empty:
        return _fail("Dispatch logs exist", f"empty logs: {', '.join(empty[:3])}")

    # Check per-sprint sub-dispatch logs
    sprints_log_dir = log_dir / "sprints"
    if sprints_log_dir.is_dir():
        issues: list[str] = []
        for sprint_dir in sorted(sprints_log_dir.iterdir()):
            if not sprint_dir.is_dir():
                continue
            sprint_files = list(sprint_dir.glob("*.md"))

            # Check for ticket-level logs (sprint-executor -> code-monkey)
            ticket_logs = [f for f in sprint_files if f.name.startswith("ticket-")]
            if not ticket_logs:
                issues.append(f"{sprint_dir.name}: no ticket-* log files")

            # Check for planner sub-dispatch logs (architect, reviewer, etc.)
            # These are files NOT matching ticket-* or sprint-planner-* patterns
            planner_sub_logs = [
                f for f in sprint_files
                if not f.name.startswith("ticket-")
                and not f.name.startswith("sprint-planner-")
            ]
            if not planner_sub_logs:
                issues.append(
                    f"{sprint_dir.name}: no planner sub-dispatch logs"
                    " (e.g. architect-*, architecture-reviewer-*)"
                )

            # Check template_used for dispatches to templated agents
            for log_file in sprint_files:
                content = log_file.read_text(encoding="utf-8")
                if not content.startswith("---"):
                    continue
                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue
                try:
                    fm = yaml.safe_load(parts[1])
                except Exception:
                    continue
                if not isinstance(fm, dict):
                    continue
                child = fm.get("child", "")
                if child in templated_agents and not fm.get("template_used"):
                    issues.append(
                        f"{log_file.name}: dispatch to '{child}' missing template_used"
                    )

        if issues:
            return _fail("Dispatch logs exist", "; ".join(issues[:5]))

    return _pass("Dispatch logs exist", f"{len(log_files)} log file(s)")


def _check_tests_pass(project_dir: Path) -> CheckResult:
    """Run pytest in the project and check exit code."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=short", "-q"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return _pass("Project tests pass", result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "")
        return _fail("Project tests pass", f"exit {result.returncode}: {result.stdout[-200:]}")
    except subprocess.TimeoutExpired:
        return _fail("Project tests pass", "timed out after 60s")
    except Exception as exc:
        return _fail("Project tests pass", str(exc))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify(project_dir: str | Path) -> list[CheckResult]:
    """Run all verification checks against a project directory.

    Returns a list of :class:`CheckResult` tuples.
    """
    pd = Path(project_dir)
    if not pd.is_dir():
        raise ValueError(f"Not a directory: {pd}")

    results: list[CheckResult] = []
    results.append(_check_app_starts(pd))
    results.append(_check_menu(pd))
    results.append(_play_game(pd, "1", "7", "number"))
    results.append(_play_game(pd, "2", "blue", "color"))
    results.append(_play_game(pd, "3", "Paris", "city"))
    results.append(_check_sprints(pd))
    results.append(_check_tickets_done(pd))
    results.append(_check_dispatch_logs(pd))
    results.append(_check_tests_pass(pd))

    return results


def print_results(results: list[CheckResult]) -> None:
    """Print a formatted summary table of results."""
    print()
    print("=== E2E Verification Results ===")
    for r in results:
        tag = "PASS" if r.passed else "FAIL"
        line = f"[{tag}] {r.name}"
        if r.detail:
            line += f"  ({r.detail})"
        print(line)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print()
    print(f"{passed}/{total} checks passed")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <project-dir>", file=sys.stderr)
        sys.exit(2)

    project_dir = Path(sys.argv[1])
    if not project_dir.is_dir():
        print(f"Error: not a directory: {project_dir}", file=sys.stderr)
        sys.exit(2)

    results = verify(project_dir)
    print_results(results)

    if all(r.passed for r in results):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
