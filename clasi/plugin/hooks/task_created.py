#!/usr/bin/env python3
"""CLASI TaskCreated hook — logs when a task starts."""
from clasi.hook_handlers import read_payload, handle_task_created
handle_task_created(read_payload())
