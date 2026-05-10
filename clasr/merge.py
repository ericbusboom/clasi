"""
clasr/merge.py

JSON deep-merge helper for multi-provider passthrough file installation.

When two providers both ship a JSON passthrough file to the same target path,
the second install must merge its keys into the existing file rather than
overwriting or erroring.  This module owns that logic.

API:
    is_json_passthrough(path: Path) -> bool
        Returns True if path has a .json extension.

    merge_json_files(
        existing: Path,
        incoming: dict,
        provider: str,
        other_provider: str,
    ) -> tuple[dict, list[str]]
        Reads existing as JSON; deep-merges incoming into it; returns
        (merged_dict, list_of_top_level_keys_from_incoming).
        Raises FileNotFoundError if existing does not exist.
        Emits a WARNING to stderr for each top-level key conflict.

Private helpers (not part of the public API):

    _deep_merge(base, overlay) -> dict
        Deep-merges overlay into base; overlay wins on scalar/type conflicts.

    _deep_diff(base, overlay) -> dict
        Returns the sub-tree of overlay that contributes new or changed values
        relative to base.  Used to record exactly what a provider contributed
        so that its leaves can be removed precisely on uninstall.

    _reverse_diff(current, diff) -> dict
        Returns a copy of current with the leaves recorded in diff removed.
        Used on uninstall to strip only a single provider's contribution from
        a shared JSON file without touching another provider's keys.

No imports from clasi or any other clasr module.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def is_json_passthrough(path: Path) -> bool:
    """Return True iff *path* has a ``.json`` extension."""
    return path.suffix == ".json"


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Return a new dict that is *overlay* deep-merged into *base*.

    For dict-vs-dict values the merge recurses.  For all other types the
    overlay (incoming) value wins.
    """
    result = dict(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _deep_diff(base: dict, overlay: dict) -> dict:
    """Return the sub-tree of *overlay* that contributes new or changed values.

    Rules
    -----
    - Key absent from *base*: include the full value from *overlay*.
    - Both values are dicts: recurse; include only non-empty sub-diffs.
    - Scalar / list / type-mismatch: include *overlay* value only when it
      differs from the *base* value; omit entirely when equal.

    Neither input is mutated.
    """
    result: dict = {}
    for k, v in overlay.items():
        if k not in base:
            result[k] = v
        elif isinstance(base[k], dict) and isinstance(v, dict):
            sub = _deep_diff(base[k], v)
            if sub:
                result[k] = sub
        else:
            if v != base[k]:
                result[k] = v
    return result


def _reverse_diff(current: dict, diff: dict) -> dict:
    """Return a copy of *current* with the leaves recorded in *diff* removed.

    Rules
    -----
    - Both values are dicts: recurse; if recursion yields an empty dict,
      remove the key from the result entirely.
    - Otherwise: delete ``result[k]`` (no element-level list subtraction).
    - Keys absent from *current*: silently skip.

    Neither input is mutated.
    """
    result = dict(current)
    for k, v in diff.items():
        if k not in result:
            continue
        if isinstance(result[k], dict) and isinstance(v, dict):
            sub = _reverse_diff(result[k], v)
            if sub:
                result[k] = sub
            else:
                del result[k]
        else:
            del result[k]
    return result


def merge_json_files(
    existing: Path,
    incoming: dict,
    provider: str,
    other_provider: str,
) -> tuple[dict, list[str]]:
    """Read *existing* as JSON and deep-merge *incoming* into it.

    Parameters
    ----------
    existing:
        Path to the JSON file already on disk.  Raises ``FileNotFoundError``
        if the file does not exist.
    incoming:
        Dict of keys from the new provider being installed.
    provider:
        Name of the provider contributing *incoming* (wins on conflict).
    other_provider:
        Name of the provider that wrote the existing file.

    Returns
    -------
    tuple[dict, list[str]]
        ``(merged_dict, keys_contributed_by_incoming)`` where
        ``keys_contributed_by_incoming`` is ``list(incoming.keys())``.

    Side-effects
    ------------
    Prints a WARNING to ``sys.stderr`` for each top-level key present in both
    dicts, naming both providers and the conflicting key.
    """
    if not existing.exists():
        raise FileNotFoundError(f"clasr: merge target does not exist: {existing}")

    base: dict = json.loads(existing.read_text())

    # Warn for each top-level key conflict.
    for k in incoming:
        if k in base:
            print(
                f"WARNING: clasr: key '{k}' in {existing} is set by both"
                f" '{other_provider}' and '{provider}'; '{provider}' wins",
                file=sys.stderr,
            )

    merged = _deep_merge(base, incoming)
    return merged, list(incoming.keys())
