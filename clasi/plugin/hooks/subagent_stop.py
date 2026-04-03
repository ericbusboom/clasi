#!/usr/bin/env python3
"""CLASI SubagentStop hook — logs when a subagent finishes."""
from clasi.hook_handlers import read_payload, handle_subagent_stop
handle_subagent_stop(read_payload())
