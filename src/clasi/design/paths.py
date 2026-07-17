"""Path resolution for co-located subsystem ``DESIGN.md`` files.

Pure path logic, no file I/O, no git. Consumed by ``clasi.design.store``,
``clasi.design.validator``, and ``clasi.design.overlay``.

A subsystem's design doc lives at ``<subsystem_path>/DESIGN.md`` — the
doc's location *is* its identity. There is no slugification, no
source-root disambiguation, and no collision handling: two subsystems
can never collide on a name the way two flat ``docs/design/<slug>.md``
files could, because each subsystem has its own directory.

The system-level document is a separate, unrelated concept: it is always
named ``design.md`` and resolved under ``project.design_dir``, independent
of subsystem count or any subsystem path. ``system_doc_name()`` exists
only to give callers one uniform "ask for a name" interface across the
system doc and subsystem docs.
"""

from __future__ import annotations

from pathlib import Path

SYSTEM_DOC_NAME = "design.md"
SUBSYSTEM_DOC_NAME = "DESIGN.md"


def system_doc_name() -> str:
    """Return the filename of the top-level system design document.

    Always ``design.md``, independent of source-root count or any
    subsystem path — kept as a function (rather than requiring callers to
    reference the module constant directly) so callers have one uniform
    "ask for a name" interface across the system doc and subsystem docs.
    """
    return SYSTEM_DOC_NAME


def design_doc_path_for(subsystem_path: Path) -> Path:
    """Return the path to *subsystem_path*'s co-located design doc.

    This is ``<subsystem_path>/DESIGN.md`` — the design doc lives directly
    in the subsystem's own source directory. No slugification, no source
    root, and no collision handling are needed: the path itself is the
    doc's identity, so two subsystems can never collide on a name.
    """
    return subsystem_path / SUBSYSTEM_DOC_NAME
