"""
clasr/platforms/detect.py

Compatibility wrapper — delegates to ``clasr.registry.detect()``.

The old ``detect(target) -> dict[str, list[str]]`` signature is preserved
for backward compatibility but is **deprecated**.  Callers should migrate to
``clasr.registry.detect(target) -> list[IntegrationBase]``.

Deprecation schedule: this wrapper will be removed in a future release.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import clasr.registry as registry


def detect(target: Path) -> dict[str, list[str]]:
    """Detect which clasr-managed providers are installed in *target*.

    .. deprecated::
        Use ``clasr.registry.detect(target)`` instead, which returns a
        ``list[IntegrationBase]``.  This wrapper converts that result back to
        the old ``dict[str, list[str]]`` format for compatibility.

    Parameters
    ----------
    target:
        The project root to inspect.

    Returns
    -------
    dict[str, list[str]]
        A dict mapping platform id to a sorted list of provider names found
        in ``<target_root>/.clasr-manifest/``.  Platforms not returned by
        ``registry.detect()`` map to an empty list.  Only the three original
        platforms (``"claude"``, ``"codex"``, ``"copilot"``) are included.

    Raises
    ------
    DeprecationWarning
        Always issued — migrate to ``clasr.registry.detect()``.
    """
    warnings.warn(
        "clasr.platforms.detect.detect() is deprecated. "
        "Use clasr.registry.detect() which returns list[IntegrationBase].",
        DeprecationWarning,
        stacklevel=2,
    )

    # The three original keys, all starting empty.
    _LEGACY_KEYS = {"claude", "codex", "copilot"}
    result: dict[str, list[str]] = {k: [] for k in _LEGACY_KEYS}

    for integration in registry.detect(target):
        platform_id = integration.id
        if platform_id not in _LEGACY_KEYS:
            # Platforms added after the old API (e.g. "cursor") are silently skipped.
            continue
        manifest_dir = target / integration.target_root / ".clasr-manifest"
        if manifest_dir.is_dir():
            providers = sorted(
                p.stem for p in manifest_dir.glob("*.json") if p.is_file()
            )
        else:
            providers = []
        result[platform_id] = providers

    return result
