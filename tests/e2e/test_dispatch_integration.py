"""Integration tests for dispatch tools using real Claude subagent sessions.

These tests spawn actual ``claude -p`` processes via the Claude Agent SDK
``query()`` function.  They are slow (30-60s each) and cannot run from
inside a Claude Code session (nested sessions are not supported).

Run manually::

    CLAUDECODE= uv run pytest tests/e2e/test_dispatch_integration.py -v -m slow

They are excluded from the default ``uv run pytest`` invocation via the
``slow`` marker.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Markers / skips
# ---------------------------------------------------------------------------

skip_in_claude = pytest.mark.skipif(
    bool(os.environ.get("CLAUDECODE")),
    reason="Cannot spawn nested Claude sessions from inside Claude Code",
)

THIS_DIR = Path(__file__).resolve().parent
SERVER_SCRIPT = THIS_DIR / "repro_server.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_test_project(tmp_path: Path) -> Path:
    """Create a minimal project directory with git init.

    Returns the project directory path.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    # git init with initial commit
    subprocess.run(
        ["git", "init"], cwd=project, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=project, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=project, capture_output=True, check=True,
    )
    (project / ".gitignore").write_text("*.log\n")
    subprocess.run(
        ["git", "add", "."], cwd=project, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=project, capture_output=True, check=True,
    )
    return project


def write_mcp_config(project: Path, server_script: Path | None = None) -> Path:
    """Write a .mcp.json pointing at the given server script.

    If no script is provided, uses ``repro_server.py``.
    Returns the path to the config file.
    """
    script = server_script or SERVER_SCRIPT
    config = {
        "mcpServers": {
            "test-server": {
                "command": sys.executable,
                "args": [str(script)],
            }
        }
    }
    config_path = project / ".mcp.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def run_claude_with_mcp(
    project_dir: Path,
    prompt: str,
    allowed_tools: str = "mcp__test-server__*",
    *,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    """Run ``claude -p`` against a project with MCP config.

    Unsets CLAUDECODE so nested sessions work.
    """
    config_path = project_dir / ".mcp.json"
    cmd = [
        "claude", "-p", prompt,
        "--mcp-config", str(config_path),
        "--allowedTools", allowed_tools,
    ]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    return subprocess.run(
        cmd, cwd=project_dir, capture_output=True, text=True,
        env=env, timeout=timeout,
    )


def read_mcp_log(project_dir: Path) -> str:
    """Read the dispatch stderr log if it exists."""
    log_path = project_dir / "query-stderr.log"
    if log_path.exists():
        return log_path.read_text(encoding="utf-8").strip()
    return ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@skip_in_claude
@pytest.mark.slow
def test_standalone_query(tmp_path: Path) -> None:
    """query() works from a standalone script."""
    project = create_test_project(tmp_path)

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    result = subprocess.run(
        [sys.executable, str(THIS_DIR / "repro_standalone.py")],
        cwd=project,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"repro_standalone.py failed with exit {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "SUCCESS" in result.stdout, (
        f"Expected 'SUCCESS' in output, got: {result.stdout}"
    )


@skip_in_claude
@pytest.mark.slow
def test_query_from_mcp_server(tmp_path: Path) -> None:
    """query() works when called from inside an MCP server tool."""
    project = create_test_project(tmp_path)
    write_mcp_config(project)

    # Commit the .mcp.json so the project is clean
    subprocess.run(
        ["git", "add", ".mcp.json"], cwd=project, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "add mcp config"],
        cwd=project, capture_output=True,
    )

    result = run_claude_with_mcp(
        project,
        "Call the dispatch_test tool with message='hello from mcp'. "
        "Report the exact JSON result.",
    )

    assert result.returncode == 0, (
        f"claude -p failed with exit {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # The repro_server dispatch_test returns JSON with "status": "success"
    assert "success" in result.stdout.lower(), (
        f"Expected 'success' in output, got: {result.stdout}\n"
        f"stderr log: {read_mcp_log(project)}"
    )


@skip_in_claude
@pytest.mark.slow
def test_echo_tool_mcp(tmp_path: Path) -> None:
    """Basic MCP echo tool works (sanity check for MCP connectivity)."""
    project = create_test_project(tmp_path)
    write_mcp_config(project)

    subprocess.run(
        ["git", "add", ".mcp.json"], cwd=project, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "add mcp config"],
        cwd=project, capture_output=True,
    )

    result = run_claude_with_mcp(
        project,
        "Call the echo tool with message='ping'. Report the result.",
    )

    assert result.returncode == 0, (
        f"claude -p failed with exit {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "ping" in result.stdout.lower(), (
        f"Expected 'ping' in output, got: {result.stdout}"
    )


@skip_in_claude
@pytest.mark.slow
def test_dispatch_error_is_fatal(tmp_path: Path) -> None:
    """When dispatch fails, the result contains fatal=True and stop instruction.

    We create a server that will fail the query() call by using an invalid
    model name, then verify the error JSON shape.
    """
    project = create_test_project(tmp_path)

    # Write a custom server that uses an invalid model to force a failure
    bad_server = project / "bad_server.py"
    bad_server.write_text(
        '''"""MCP server with a dispatch tool that will fail."""

import json
import os

from mcp.server.fastmcp import FastMCP

server = FastMCP("bad-server")


@server.tool()
async def dispatch_fail(message: str) -> str:
    """Call query() with an invalid model to force a failure."""
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, ProcessError

    stderr_path = os.path.join(os.getcwd(), "query-stderr.log")
    stderr_file = open(stderr_path, "w")

    options = ClaudeAgentOptions(
        cwd=os.getcwd(),
        allowed_tools=["Read"],
        permission_mode="bypassPermissions",
        model="nonexistent-model-that-will-fail",
        debug_stderr=stderr_file,
    )

    try:
        async for msg in query(
            prompt="Say hello",
            options=options,
        ):
            if isinstance(msg, ResultMessage):
                return json.dumps({"status": "success", "result": msg.result})
    except ProcessError as e:
        stderr_file.close()
        return json.dumps({
            "status": "error",
            "fatal": True,
            "message": str(e),
            "exit_code": e.exit_code,
            "instruction": (
                "DISPATCH FAILED. DO NOT attempt to do this work yourself. "
                "DO NOT proceed without the subagent. STOP and report this "
                "error to the stakeholder."
            ),
        }, indent=2)
    except Exception as e:
        stderr_file.close()
        return json.dumps({
            "status": "error",
            "fatal": True,
            "type": type(e).__name__,
            "message": str(e),
            "instruction": (
                "DISPATCH FAILED. DO NOT attempt to do this work yourself. "
                "STOP and report this error to the stakeholder."
            ),
        }, indent=2)

    stderr_file.close()
    return json.dumps({"status": "unexpected_success"})


if __name__ == "__main__":
    server.run(transport="stdio")
''',
        encoding="utf-8",
    )

    # Write config pointing at bad server
    config = {
        "mcpServers": {
            "test-server": {
                "command": sys.executable,
                "args": [str(bad_server)],
            }
        }
    }
    (project / ".mcp.json").write_text(json.dumps(config, indent=2))

    subprocess.run(
        ["git", "add", "."], cwd=project, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "add bad server"],
        cwd=project, capture_output=True,
    )

    result = run_claude_with_mcp(
        project,
        "Call the dispatch_fail tool with message='test'. "
        "Report the exact JSON result including all fields.",
        allowed_tools="mcp__test-server__*",
    )

    assert result.returncode == 0, (
        f"claude -p failed with exit {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    output = result.stdout.lower()
    # The tool should return error status with fatal flag
    assert "error" in output, (
        f"Expected 'error' in output, got: {result.stdout}"
    )
    assert "fatal" in output or "fail" in output, (
        f"Expected 'fatal' or 'fail' in output, got: {result.stdout}"
    )
