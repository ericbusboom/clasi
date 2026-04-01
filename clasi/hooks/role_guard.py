#!/usr/bin/env python3
"""CLASI role guard hook — blocks dispatchers from writing files directly."""
from clasi.hook_handlers import handle_hook
handle_hook("role-guard")
