#!/usr/bin/env python3
"""CLASI role guard hook — blocks dispatchers from writing files directly."""
from clasi.hook_handlers import read_payload, handle_role_guard
handle_role_guard(read_payload())
