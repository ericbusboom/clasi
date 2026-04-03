#!/usr/bin/env python3
"""CLASI TaskCompleted hook — validates task completion."""
from clasi.hook_handlers import read_payload, handle_task_completed
handle_task_completed(read_payload())
