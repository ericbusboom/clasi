#!/usr/bin/env python3
"""CLASI role guard: blocks dispatchers from writing files directly.

Fires on PreToolUse for Edit, Write, MultiEdit.
Reads TOOL_INPUT from stdin as JSON.

Tier-aware enforcement:
- Tier 2 (task workers: code-monkey, architect, etc.) — ALLOWED to write
- Tier 1 (domain controllers: sprint-executor, sprint-planner) — BLOCKED
- Tier 0 (main controller: team-lead) — BLOCKED
- No tier set (interactive session with CLAUDE.md) — BLOCKED (team-lead)

The agent tier is passed via CLASI_AGENT_TIER environment variable,
set by Agent.dispatch() in agent.py.
"""
import json
import os
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

    # Task workers (tier 2) are allowed to write files — that's their job
    agent_tier = os.environ.get("CLASI_AGENT_TIER", "")
    if agent_tier == "2":
        sys.exit(0)

    # Check OOP bypass
    if Path(".clasi-oop").exists():
        sys.exit(0)

    # Check recovery state
    db_path = Path("docs/clasi/.clasi.db")
    if db_path.exists():
        try:
            from clasi.state_db import get_recovery_state

            recovery = get_recovery_state(str(db_path))
            if recovery and file_path in recovery["allowed_paths"]:
                sys.exit(0)
        except Exception:
            pass  # DB read failure -- default to blocking

    # Check safe list
    for prefix in SAFE_PREFIXES:
        if file_path == prefix or file_path.startswith(prefix):
            sys.exit(0)

    # Block — determine who's violating
    agent_name = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    print(
        f"CLASI ROLE VIOLATION: {agent_name} (tier {agent_tier or '0'}) "
        f"attempted direct file write to: {file_path}"
    )
    print(
        "Dispatchers do not write files. Dispatch to the appropriate subagent:"
    )
    if agent_tier == "1":
        # Domain controller — should dispatch to task workers
        print("- code-monkey for source code and tests")
        print("- architect for architecture documents")
        print("- technical-lead for ticket plans")
    else:
        # Team-lead (tier 0 or unknown)
        print("- sprint-planner for sprint/architecture/ticket artifacts")
        print("- sprint-executor for ticket execution")
        print("- code-monkey for source code and tests")
        print("- todo-worker for TODOs")
        print("- ad-hoc-executor for out-of-process changes")
    sys.exit(1)


if __name__ == "__main__":
    main()
