"""
clasr/registry.py

INTEGRATION_REGISTRY and helper functions for clasr platform integrations.

This module is the single source of truth for all registered platforms.
Use ``get()`` to obtain a fresh integration instance by id, or ``detect()``
to discover which integrations are present in a given project directory.

Exports
-------
INTEGRATION_REGISTRY : dict[str, type[IntegrationBase]]
    Maps platform id strings to their integration classes.
get(id) -> IntegrationBase
    Return a fresh instance for the given platform id. Raises ``KeyError``
    for unknown ids.
detect(target) -> list[IntegrationBase]
    Return instances of integrations whose ``detect_files`` are present
    in *target*.
"""

from __future__ import annotations

from pathlib import Path

from clasr.integration import IntegrationBase
from clasr.platforms.claude import ClaudeIntegration
from clasr.platforms.codex import CodexIntegration
from clasr.platforms.copilot import CopilotIntegration
from clasr.platforms.cursor import CursorIntegration

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

INTEGRATION_REGISTRY: dict[str, type[IntegrationBase]] = {
    "claude": ClaudeIntegration,
    "codex": CodexIntegration,
    "copilot": CopilotIntegration,
    "cursor": CursorIntegration,
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get(id: str) -> IntegrationBase:
    """Return a fresh integration instance for *id*.

    Parameters
    ----------
    id:
        Platform identifier, e.g. ``"claude"``, ``"codex"``, ``"copilot"``.

    Returns
    -------
    IntegrationBase
        A new instance of the integration class for *id*.

    Raises
    ------
    KeyError
        If *id* is not in :data:`INTEGRATION_REGISTRY`.
    """
    return INTEGRATION_REGISTRY[id]()


def detect(target: Path) -> list[IntegrationBase]:
    """Return instances of integrations whose ``detect_files`` are present in *target*.

    Parameters
    ----------
    target:
        Path to the project root to inspect.

    Returns
    -------
    list[IntegrationBase]
        A list of fresh integration instances whose ``detect_files`` marker
        files exist under *target*.  The list order follows
        :data:`INTEGRATION_REGISTRY` insertion order.
    """
    found: list[IntegrationBase] = []
    for cls in INTEGRATION_REGISTRY.values():
        instance = cls()
        if any((target / f).exists() for f in instance.detect_files):
            found.append(instance)
    return found
