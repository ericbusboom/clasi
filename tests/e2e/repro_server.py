"""Minimal MCP server with a tool that calls query() — for reproducing dispatch issues."""

import json
import os

from mcp.server.fastmcp import FastMCP

server = FastMCP("test-server")


@server.tool()
async def dispatch_test(message: str) -> str:
    """Call query() to spawn a subagent that echoes a message."""
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, ProcessError

    stderr_path = os.path.join(os.getcwd(), "query-stderr.log")
    stderr_file = open(stderr_path, "w")

    options = ClaudeAgentOptions(
        cwd=os.getcwd(),
        allowed_tools=["Read"],
        permission_mode="bypassPermissions",
        model="haiku",
        debug_stderr=stderr_file,
    )

    result_text = ""
    try:
        async for msg in query(
            prompt=f"Reply with exactly: {message}",
            options=options,
        ):
            if isinstance(msg, ResultMessage):
                result_text = msg.result
    except ProcessError as e:
        stderr_file.close()
        stderr_content = ""
        try:
            stderr_content = open(stderr_path).read().strip()
        except OSError:
            pass
        return json.dumps({
            "status": "error",
            "message": str(e),
            "exit_code": e.exit_code,
            "stderr_attr": e.stderr,
            "stderr_file": stderr_content,
        }, indent=2)
    except Exception as e:
        stderr_file.close()
        return json.dumps({
            "status": "error",
            "type": type(e).__name__,
            "message": str(e),
        }, indent=2)

    stderr_file.close()
    return json.dumps({"status": "success", "result": result_text}, indent=2)


@server.tool()
def echo(message: str) -> str:
    """Simple echo tool to verify MCP server works."""
    return json.dumps({"echo": message})


if __name__ == "__main__":
    server.run(transport="stdio")
