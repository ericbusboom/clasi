#!/usr/bin/env python3
"""CLASI role guard: blocks team-lead from writing files directly.

Fires on PreToolUse for Edit, Write, MultiEdit.
Reads TOOL_INPUT from stdin as JSON.
"""
import json
import sys
from pathlib import Path

SAFE_PREFIXES = [".claude/", "CLAUDE.md", "AGENTS.md"]


def main() -> None:
    tool_input = json.load(sys.stdin)
    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("new_path")
        or ""
    )

    if not file_path:
        sys.exit(0)  # Can't determine path, allow

    # Check OOP bypass
    if Path(".clasi-oop").exists():
        sys.exit(0)

    # Check recovery state
    db_path = Path("docs/clasi/.clasi.db")
    if db_path.exists():
        try:
            from claude_agent_skills.state_db import get_recovery_state

            recovery = get_recovery_state(str(db_path))
            if recovery and file_path in recovery["allowed_paths"]:
                sys.exit(0)
        except Exception:
            pass  # DB read failure -- default to blocking

    # Check safe list
    for prefix in SAFE_PREFIXES:
        if file_path == prefix or file_path.startswith(prefix):
            sys.exit(0)

    # Block
    print(
        f"CLASI ROLE VIOLATION: team-lead attempted direct file write to: {file_path}"
    )
    print(
        "The team-lead does not write files. Dispatch to the appropriate subagent:"
    )
    print("- sprint-planner for sprint/architecture/ticket artifacts")
    print("- code-monkey for source code and tests")
    print("- todo-worker for TODOs")
    print("- ad-hoc-executor for out-of-process changes")
    print('Call get_agent_definition("team-lead") to review your delegation map.')
    sys.exit(1)


if __name__ == "__main__":
    main()
