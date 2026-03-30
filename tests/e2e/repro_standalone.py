"""Standalone query() test — runs outside any MCP server context."""

import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    try:
        async for msg in query(
            prompt="Reply with exactly: hello standalone",
            options=ClaudeAgentOptions(
                cwd=".",
                allowed_tools=["Read"],
                permission_mode="bypassPermissions",
                model="haiku",
            ),
        ):
            if isinstance(msg, ResultMessage):
                print(f"SUCCESS: {msg.result}")
                return
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
