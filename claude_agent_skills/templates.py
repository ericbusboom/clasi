"""
Artifact templates for sprints, tickets, briefs, architecture, and use cases.

Templates are stored as .md files in the templates/ directory and loaded
at import time. Use str.format() with named placeholders for dynamic values.
"""

import re
import unicodedata
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load(name: str) -> str:
    """Load a template file by name (without extension)."""
    return (_TEMPLATES_DIR / f"{name}.md").read_text(encoding="utf-8")


def slugify(title: str) -> str:
    """Convert a title to a filesystem-safe slug.

    >>> slugify("Add User Authentication")
    'add-user-authentication'
    >>> slugify("MCP Server & Tools!")
    'mcp-server-tools'
    """
    # Normalize unicode, lowercase
    s = unicodedata.normalize("NFKD", title).lower()
    # Replace non-alphanumeric with hyphens
    s = re.sub(r"[^a-z0-9]+", "-", s)
    # Strip leading/trailing hyphens
    s = s.strip("-")
    return s


SPRINT_TEMPLATE = _load("sprint")
SPRINT_BRIEF_TEMPLATE = _load("sprint-brief")
SPRINT_USECASES_TEMPLATE = _load("sprint-usecases")
SPRINT_ARCHITECTURE_TEMPLATE = _load("sprint-architecture")
TICKET_TEMPLATE = _load("ticket")
REVIEW_CHECKLIST_TEMPLATE = _load("review-checklist")
OVERVIEW_TEMPLATE = _load("overview")
