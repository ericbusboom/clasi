"""Slugification: derive canonical design-doc and README paths.

Pure path -> name logic for the persistent per-subsystem architecture doc
set (sprint 021). No file I/O, no git. Consumed by ``clasi.design.store``,
``clasi.design.validator``, and ``clasi.design.overlay``.

Naming rules (see the sprint 021 issue, "Naming convention"):

- **Single source root**: the filename is derived by slugifying the
  subsystem path *relative to that root*, with the root name omitted,
  e.g. ``src/clasi/tools/`` with source root ``src`` -> ``clasi-tools.md``.
- **Multiple source roots**: the filename is derived by slugifying the
  subsystem path *relative to the repo root*, with the root name
  included (it disambiguates which root the subsystem belongs to), e.g.
  ``tests/e2e/`` -> ``tests-e2e.md``.
- The system-level document is always named ``design.md``, independent of
  root count or path.
- **Collision fallback**: if a subsystem's single-root slug would be
  byte-identical to the reserved system-doc name (``design.md`` — e.g. a
  subsystem directory literally named ``design``, such as this repo's own
  ``src/clasi/design``), the slug falls back to that one subsystem's
  root-qualified (multi-root-style) form instead, e.g.
  ``src/clasi/design`` -> ``src-clasi-design.md``. This reuses the
  existing multi-root disambiguation rule rather than introducing a new
  naming concept, so every other subsystem's filename is unaffected and
  ``design.md`` stays reserved for the system document. If the
  root-qualified fallback itself still equals ``design.md``, or still
  collides with another subsystem's slug, ``design_doc_slug`` raises
  ``DesignPathError`` — deterministic and total, but fails loud on a
  residual pathological case rather than guessing further or silently
  colliding.
"""

from __future__ import annotations

from pathlib import Path

SYSTEM_DOC_NAME = "design.md"


class DesignPathError(ValueError):
    """Raised when a subsystem path cannot be mapped to a design-doc slug.

    Typically because the path is not located under any declared source
    root.
    """


def system_doc_name() -> str:
    """Return the filename of the top-level system design document.

    Always ``design.md``, independent of source-root count or any
    subsystem path — kept as a function (rather than requiring callers to
    reference the module constant directly) so callers have one uniform
    "ask for a name" interface across the system doc and subsystem docs.
    """
    return SYSTEM_DOC_NAME


def _find_containing_root(subsystem_path: Path, sources: list[Path]) -> Path:
    """Return the source root in *sources* that contains *subsystem_path*.

    Both *subsystem_path* and each entry in *sources* are expected to be
    resolved, absolute paths (as returned by ``Project.sources`` and
    intended to be produced by ``Path.resolve()`` on the caller's side).

    Raises:
        DesignPathError: If *subsystem_path* is not under any root in
            *sources*, or *sources* is empty.
    """
    for root in sources:
        try:
            subsystem_path.relative_to(root)
        except ValueError:
            continue
        return root

    raise DesignPathError(
        f"Subsystem path {subsystem_path!s} is not under any declared "
        f"source root: {[str(r) for r in sources]}"
    )


def _slugify(parts: tuple[str, ...]) -> str:
    """Join path segments with hyphens and lowercase the result.

    Each segment is expected to already be a plain directory name (no
    separators, no leading/trailing punctuation) — this is a small, fixed
    join-and-lowercase step, not a general-purpose slug library. Matches
    the issue's own worked examples (``clasi-tools``, ``tests-e2e``).
    """
    return "-".join(parts).lower()


def design_doc_slug(subsystem_path: Path, sources: list[Path]) -> str:
    """Derive the canonical design-doc filename for *subsystem_path*.

    *subsystem_path* and every entry in *sources* must be absolute,
    resolved paths (matching ``Project.sources``'s contract) so that
    ``Path.relative_to`` comparisons are unambiguous regardless of the
    caller's current working directory.

    - If exactly one source root is declared, the slug is derived from
      the path segments *between* that root and *subsystem_path*, with
      the root's own name omitted.
    - If multiple source roots are declared, the slug is derived from the
      path segments between the repo root (the common parent implied by
      *sources*) and *subsystem_path*, with the containing root's name
      included to disambiguate.

    Returns:
        A filename such as ``"clasi-tools.md"`` or ``"tests-e2e.md"``.

    Raises:
        DesignPathError: If *sources* is empty, *subsystem_path* is not
            located under any declared source root, or the computed slug
            (including, for a single-root collision, the root-qualified
            fallback — see the module docstring's "Collision fallback")
            still equals the reserved system-doc name.
    """
    if not sources:
        raise DesignPathError(
            f"Cannot derive a design-doc slug for {subsystem_path!s}: "
            "no source roots declared"
        )

    containing_root = _find_containing_root(subsystem_path, sources)
    rel_to_root = subsystem_path.relative_to(containing_root)

    if len(sources) == 1:
        # Single root: root name omitted.
        parts = rel_to_root.parts
        if not parts:
            # subsystem_path == the root itself: fall back to the root's
            # own name, since there is no relative path to slugify.
            parts = (containing_root.name,)

        slug = f"{_slugify(parts)}.md"
        if slug == SYSTEM_DOC_NAME:
            # Single-root slug collides with the reserved system-doc name
            # (e.g. a subsystem directory literally named "design"). Fall
            # back to the multi-root (root-qualified) form for this one
            # subsystem only — reuses the disambiguation rule below rather
            # than inventing a new naming concept.
            qualified_parts = (containing_root.name, *rel_to_root.parts)
            slug = f"{_slugify(qualified_parts)}.md"
            if slug == SYSTEM_DOC_NAME:
                raise DesignPathError(
                    f"Cannot derive a design-doc slug for {subsystem_path!s}: "
                    f"both the single-root slug and the root-qualified "
                    f"fallback collide with the reserved system-doc name "
                    f"({SYSTEM_DOC_NAME!r})."
                )
        return slug

    # Multiple roots: root name included to disambiguate.
    parts = (containing_root.name, *rel_to_root.parts)
    slug = f"{_slugify(parts)}.md"
    if slug == SYSTEM_DOC_NAME:
        raise DesignPathError(
            f"Cannot derive a design-doc slug for {subsystem_path!s}: "
            f"the root-qualified slug collides with the reserved "
            f"system-doc name ({SYSTEM_DOC_NAME!r})."
        )
    return slug


def readme_path_for(subsystem_path: Path) -> Path:
    """Return the path to the subsystem's own README.md.

    This is ``<subsystem_path>/README.md`` — the README lives in the
    subsystem's source directory itself, not in ``docs/design/`` (SUC-001's
    bootstrap and SUC-003's validator both need this pairing to check the
    bidirectional link between a design doc and its subsystem README).
    """
    return subsystem_path / "README.md"
