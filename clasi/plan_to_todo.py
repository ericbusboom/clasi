"""Convert a Claude Code plan file to a CLASI TODO."""

import hashlib
from pathlib import Path
from typing import Optional

from clasi.templates import slugify


def _content_hash(text: str) -> str:
    """Return the hex SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _unique_path(directory: Path, slug: str) -> Path:
    """Return a unique .md path in directory, appending a number if needed."""
    candidate = directory / f"{slug}.md"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = directory / f"{slug}-{n}.md"
        if not candidate.exists():
            return candidate
        n += 1


def plan_to_todo(
    plans_dir: Path,
    todo_dir: Path,
    plan_file: Optional[Path] = None,
) -> Optional[Path]:
    """Copy a plan file to the TODO directory.

    When plan_file is provided, use that file directly. Otherwise finds
    the newest .md in plans_dir. Adds ``status: pending`` frontmatter,
    writes it to todo_dir, and deletes the original.

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

    out_path.write_text(f"---\nstatus: pending\n---\n\n{body}\n", encoding="utf-8")

    plan_file.unlink()
    return out_path


def plan_to_todo_from_text(text: str, todo_dir: Path) -> Optional[Path]:
    """Write a pending TODO from raw plan *text* with content-hash deduplication.

    Adds ``source: codex-plan`` and ``source_hash`` to the frontmatter.
    Returns ``None`` if *text* is empty/blank or a duplicate already exists.
    Returns the path of the created file otherwise.
    """
    if not text or not text.strip():
        return None

    body = text.strip()
    h = _content_hash(body)

    # De-dupe: scan todo_dir (and todo_dir/in-progress) for matching source_hash.
    todo_dir.mkdir(parents=True, exist_ok=True)
    for search_dir in [todo_dir, todo_dir / "in-progress"]:
        if not search_dir.is_dir():
            continue
        for existing in search_dir.glob("*.md"):
            try:
                content = existing.read_text(encoding="utf-8")
                if f"source_hash: {h}" in content:
                    return None
            except OSError:
                continue

    # Extract title from first # heading.
    title = None
    for line in body.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    slug = slugify(title) if title else "untitled-plan"
    if not slug:
        slug = "untitled-plan"

    out_path = _unique_path(todo_dir, slug)
    frontmatter = f"---\nstatus: pending\nsource: codex-plan\nsource_hash: {h}\n---\n\n"
    out_path.write_text(frontmatter + body + "\n", encoding="utf-8")
    return out_path
