"""CLASI — Claude Agent Skills Instructions.

MCP server for AI-driven software engineering process.
"""

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("claude-agent-skills")
except Exception:
    __version__ = "0.0.0-unknown"
