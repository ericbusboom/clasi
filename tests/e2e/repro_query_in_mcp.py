#!/usr/bin/env python3
"""Minimal reproduction: query() fails when called from inside an MCP server.

Creates a temp project with .mcp.json pointing at repro_server.py, then:
  TEST 0: echo tool via MCP (verify connectivity)
  TEST 1: query() from standalone script (should work)
  TEST 2: query() from inside MCP server tool (the bug)

Usage:
    CLAUDECODE= uv run python tests/e2e/repro_query_in_mcp.py
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SERVER_SCRIPT = THIS_DIR / "repro_server.py"
PROJECT_DIR = THIS_DIR / "repro_project"


def setup():
    if PROJECT_DIR.exists():
        shutil.rmtree(PROJECT_DIR)
    PROJECT_DIR.mkdir()

    mcp_config = {
        "mcpServers": {
            "test-server": {
                "command": sys.executable,
                "args": [str(SERVER_SCRIPT)],
            }
        }
    }
    (PROJECT_DIR / ".mcp.json").write_text(json.dumps(mcp_config, indent=2))

    subprocess.run(["git", "init"], cwd=PROJECT_DIR, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=PROJECT_DIR, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=PROJECT_DIR, capture_output=True)


def run_claude(prompt, extra_args=None):
    cmd = [
        "claude", "-p", prompt,
        "--mcp-config", str(PROJECT_DIR / ".mcp.json"),
        "--allowedTools", "mcp__test-server__*",
    ]
    if extra_args:
        cmd.extend(extra_args)

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(cmd, cwd=PROJECT_DIR, capture_output=True, text=True, env=env)
    return result


def test_echo():
    print("=" * 60)
    print("TEST 0: echo tool via MCP (verify connectivity)")
    print("=" * 60)
    r = run_claude("Call the echo tool with message='ping'. Report the result.")
    print(f"  stdout: {r.stdout.strip()}")
    print(f"  exit: {r.returncode}")
    print()


def test_standalone():
    print("=" * 60)
    print("TEST 1: query() from standalone script")
    print("=" * 60)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    r = subprocess.run(
        [sys.executable, str(THIS_DIR / "repro_standalone.py")],
        cwd=PROJECT_DIR, capture_output=True, text=True, env=env,
    )
    print(f"  stdout: {r.stdout.strip()}")
    print(f"  exit: {r.returncode}")
    print()


def test_dispatch_via_mcp():
    print("=" * 60)
    print("TEST 2: query() from inside MCP server tool")
    print("=" * 60)
    r = run_claude("Call dispatch_test with message='hello from mcp'. Report the exact JSON.")
    print(f"  stdout: {r.stdout.strip()}")
    print(f"  exit: {r.returncode}")

    stderr_log = PROJECT_DIR / "query-stderr.log"
    if stderr_log.exists():
        content = stderr_log.read_text().strip()
        print(f"  query stderr: {content or '(empty)'}")
    print()


def main():
    print(f"Project: {PROJECT_DIR}")
    setup()
    test_echo()
    test_standalone()
    test_dispatch_via_mcp()

    print("=" * 60)
    print("If TEST 1 passes and TEST 2 fails, query() cannot run")
    print("from inside a stdio MCP server.")


if __name__ == "__main__":
    main()
