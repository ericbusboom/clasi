"""Convert a Claude Code plan file to a CLASI TODO."""

import json
import os
from pathlib import Path
from typing import Optional

from clasi.templates import slugify
from clasi.todo_split import _unique_path


def plan_to_todo(
    plans_dir: Path,
    todo_dir: Path,
    hook_payload: Optional[dict] = None,
    plan_file: Optional[Path] = None,
) -> Optional[Path]:
    """Copy a plan file to the TODO directory.

    When plan_file is provided, use that file directly. Otherwise finds
    the newest .md in plans_dir. Adds ``status: pending`` frontmatter,
    writes it to todo_dir, and deletes the original.

    If hook_payload is provided (not None), a debug block with payload and
    environment context is appended to the TODO file.

    Returns the path of the created TODO file, or None if nothing
    was converted.
    """
    if plan_file is not None:
        if not plan_file.exists():
            return None
    else:
        if not plans_dir.is_dir():
            return None
        plan_files = sorted(plans_dir.glob("*.md"), key=lambda p: p.stat().st_mtime)
        if not plan_files:
            return None
        plan_file = plan_files[-1]

    content = plan_file.read_text(encoding="utf-8").strip()
    if not content:
        return None

    # Strip existing frontmatter if present
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()

    # Extract title from first # heading
    title = None
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    slug = slugify(title) if title else slugify(plan_file.stem)
    if not slug:
        slug = "untitled-plan"

    todo_dir.mkdir(parents=True, exist_ok=True)
    out_path = _unique_path(todo_dir, slug)

    debug_block = ""
    if hook_payload is not None:
        debug_info = {
            "hook_payload": hook_payload,
            "env": {
                k: os.environ.get(k, "")
                for k in [
                    "TOOL_INPUT", "TOOL_NAME", "SESSION_ID",
                    "CLASI_AGENT_TIER", "CLASI_AGENT_NAME",
                    "CLAUDE_PROJECT_DIR", "PWD", "CWD",
                ]
            },
            "plans_dir": str(plans_dir),
            "plan_file": str(plan_file),
            "cwd": os.getcwd(),
        }
        debug_block = (
            "\n\n---\n\n"
            "## Hook Debug Info\n\n"
            "```json\n"
            + json.dumps(debug_info, indent=2)
            + "\n```\n"
        )

    out_path.write_text(f"---\nstatus: pending\n---\n\n{body}\n{debug_block}", encoding="utf-8")

    plan_file.unlink()
    return out_path
