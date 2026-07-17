"""Design doc set tools for the CLASI MCP server.

Exposes the persistent per-subsystem design doc set validator
(``clasi.design.validator``) over MCP, as a thin wrapper delegating to the
same underlying ``validate`` function the ``clasi design validate`` CLI
command uses — no validation logic is duplicated between the two entry
points.

Kept as a sibling module to ``artifact_tools.py`` (rather than added to
it) purely for file-size isolation: ``artifact_tools.py`` is already
about 100KB.
"""

import json
import logging

from clasi.design import validate
from clasi.mcp_server import server, get_project

logger = logging.getLogger("clasi.design_tools")


@server.tool()
def validate_design(overlay_dir: str | None = None) -> str:
    """Validate the project's persistent design doc set.

    Checks the canonical ``docs/design/`` doc set structure (top-level
    ``design.md`` present, one design doc per declared subsystem,
    bidirectional design-doc/README links resolve, no orphaned docs, no
    unmapped source roots) and, when *overlay_dir* is given, a sprint's
    ``design/`` overlay directory (overlay filenames match a canonical
    doc, overlay frontmatter references resolve, every overlay file has a
    non-stale ``.diff.md``).

    Args:
        overlay_dir: Optional path to a sprint's
            ``clasi/sprints/NNN-slug/design/`` directory to additionally
            validate. Omit (or pass the "NONE" sentinel) to validate only
            the canonical doc set.

    Returns:
        JSON object: ``{"ok": bool, "messages": [str, ...]}``. ``messages``
        is empty when ``ok`` is ``True``; otherwise each entry is an
        independently actionable failure description, so a caller can
        act on individual failures rather than parsing a single blob.
    """
    project = get_project()
    result = validate(project, overlay_dir)
    return json.dumps({"ok": result.ok, "messages": result.messages}, indent=2)
