#!/usr/bin/env python3
"""CLASI SubagentStart hook — logs when a subagent starts."""
from clasi.hook_handlers import read_payload, handle_subagent_start
handle_subagent_start(read_payload())
