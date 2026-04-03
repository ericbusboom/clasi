#!/usr/bin/env python3
"""CLASI MCP guard hook — blocks team-lead from calling artifact-creation MCP tools."""
from clasi.hook_handlers import read_payload, handle_mcp_guard
handle_mcp_guard(read_payload())
