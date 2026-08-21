"""Pure skill-body resolution — no MCP server dependency.

Provides ``resolve_skill_body``, used by both the MCP server's
``get_skill_definition`` tool (via ``clasi.tools.process_tools``, which
imports it back) and by the platform installer (``clasi.platforms.claude`` —
the only one in master as of sprint 032; Codex and Copilot were archived to
the archive/codex-copilot-adapters branch) that runs as part of `clasi init`.

This module deliberately imports nothing from ``clasi.mcp_server``. The
installers run in the ``clasi init`` CLI path, which must not pull in
``mcp.server.fastmcp`` merely to resolve a skill's ``Load from:`` directive
— see ``clasi/issues/mcp-2-breaks-every-fresh-install.md`` for the
crash this decoupling fixes.
"""

import re
from pathlib import Path

# Pattern for the Load from: directive.
# Matches lines like: Load from: `clasi/schemas/se-process/instructions/foo.md`
_LOAD_FROM_RE = re.compile(
    r"^Load from:\s*`([^`]+)`\s*$",
    re.MULTILINE,
)

# Root of the clasi package (the parent of the `clasi` package directory,
# i.e. the `src/` directory), used to resolve Load from: paths. This module
# lives at src/clasi/skill_resolve.py — one directory level shallower than
# the module it was moved from (src/clasi/tools/process_tools.py), so it
# needs one fewer `.parent` than that module's own `_PACKAGE_ROOT` did.
_PACKAGE_ROOT = Path(__file__).parent.parent


def resolve_skill_body(raw: str, base_path: Path | None = None) -> str:
    """Resolve a ``Load from:`` directive in a skill body.

    If *raw* contains a line of the form::

        Load from: `<relative-path>`

    the referenced file is read and its contents replace the entire body
    (everything below the YAML frontmatter).  The frontmatter itself is
    preserved verbatim.

    If no ``Load from:`` directive is present, *raw* is returned unchanged.

    *base_path* is the directory used to resolve the referenced path.
    When ``None``, it defaults to the clasi package root
    (``clasi/schemas/se-process/instructions/`` paths are relative to that).

    Raises :class:`FileNotFoundError` if the directive references a file that
    does not exist.
    """
    match = _LOAD_FROM_RE.search(raw)
    if match is None:
        return raw

    ref_path_str = match.group(1)
    root = base_path if base_path is not None else _PACKAGE_ROOT
    ref_path = root / ref_path_str

    if not ref_path.exists():
        raise FileNotFoundError(
            f"Skill 'Load from:' directive references non-existent file: {ref_path}"
        )

    # Split off YAML frontmatter (--- ... ---) if present, keep it.
    # Body is everything after the closing ---.
    fm_match = re.match(r"^(---\s*\n.*?\n---\s*\n)", raw, re.DOTALL)
    if fm_match:
        frontmatter = fm_match.group(1)
    else:
        frontmatter = ""

    included_body = ref_path.read_text(encoding="utf-8")
    return frontmatter + included_body
