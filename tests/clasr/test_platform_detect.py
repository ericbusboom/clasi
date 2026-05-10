"""
tests/clasr/test_platform_detect.py

Tests for clasr.registry.detect() (new interface) and the backward-compatible
clasr.platforms.detect.detect() shim (old dict format).
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

import clasr.registry as registry
from clasr.integration import IntegrationBase
from clasr.platforms.claude import ClaudeIntegration
from clasr.platforms.codex import CodexIntegration
from clasr.platforms.copilot import CopilotIntegration
from clasr.platforms.detect import detect as legacy_detect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(target: Path, platform_dir: str, provider: str) -> None:
    """Create a minimal manifest JSON file for *provider* under *platform_dir*.

    For claude, codex, and copilot the manifest directory path is also the
    detect-file for registry.detect(), so this helper both "installs" a
    provider and satisfies the registry detection check.
    """
    manifest_dir = target / platform_dir / ".clasr-manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / f"{provider}.json").write_text(
        '{"version": 1, "provider": "' + provider + '", "entries": []}',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# registry.detect() — new interface tests
# ---------------------------------------------------------------------------


def test_registry_detect_empty(tmp_path: Path) -> None:
    """No detect-files present — registry.detect() returns an empty list."""
    result = registry.detect(tmp_path)
    assert result == []


def test_registry_detect_returns_integration_instances(tmp_path: Path) -> None:
    """registry.detect() returns IntegrationBase instances, not dicts."""
    _make_manifest(tmp_path, ".claude", "myprov")
    result = registry.detect(tmp_path)
    assert len(result) >= 1
    assert all(isinstance(r, IntegrationBase) for r in result)


def test_registry_detect_claude_present(tmp_path: Path) -> None:
    """registry.detect() includes ClaudeIntegration when .clasr-manifest exists."""
    _make_manifest(tmp_path, ".claude", "myprov")
    ids = [r.id for r in registry.detect(tmp_path)]
    assert "claude" in ids


def test_registry_detect_codex_present(tmp_path: Path) -> None:
    """registry.detect() includes CodexIntegration when .clasr-manifest exists."""
    _make_manifest(tmp_path, ".codex", "myprov")
    ids = [r.id for r in registry.detect(tmp_path)]
    assert "codex" in ids


def test_registry_detect_copilot_present(tmp_path: Path) -> None:
    """registry.detect() includes CopilotIntegration when .clasr-manifest exists."""
    _make_manifest(tmp_path, ".github", "myprov")
    ids = [r.id for r in registry.detect(tmp_path)]
    assert "copilot" in ids


def test_registry_detect_multiple_platforms(tmp_path: Path) -> None:
    """registry.detect() returns one instance per detected platform."""
    _make_manifest(tmp_path, ".claude", "myprov")
    _make_manifest(tmp_path, ".github", "myprov")

    ids = [r.id for r in registry.detect(tmp_path)]
    assert "claude" in ids
    assert "copilot" in ids


def test_registry_detect_no_duplicates(tmp_path: Path) -> None:
    """Each platform appears at most once even with multiple manifests."""
    _make_manifest(tmp_path, ".claude", "alpha")
    _make_manifest(tmp_path, ".claude", "beta")

    ids = [r.id for r in registry.detect(tmp_path)]
    assert ids.count("claude") == 1


# ---------------------------------------------------------------------------
# legacy detect() compatibility shim tests
# ---------------------------------------------------------------------------


def test_legacy_detect_issues_deprecation_warning(tmp_path: Path) -> None:
    """Calling detect() must emit a DeprecationWarning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        legacy_detect(tmp_path)
    categories = [w.category for w in caught]
    assert DeprecationWarning in categories


def test_legacy_detect_empty(tmp_path: Path) -> None:
    """No platforms installed — all three legacy lists must be empty."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = legacy_detect(tmp_path)
    assert result == {"claude": [], "codex": [], "copilot": []}


def test_legacy_detect_returns_dict_format(tmp_path: Path) -> None:
    """detect() still returns dict[str, list[str]] (old format)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = legacy_detect(tmp_path)
    assert isinstance(result, dict)
    assert set(result.keys()) == {"claude", "codex", "copilot"}
    for v in result.values():
        assert isinstance(v, list)


def test_legacy_detect_always_returns_all_keys(tmp_path: Path) -> None:
    """Result always contains all three legacy platform keys."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = legacy_detect(tmp_path)
    assert set(result.keys()) == {"claude", "codex", "copilot"}


def test_legacy_detect_claude_providers(tmp_path: Path) -> None:
    """Providers from .claude manifests appear in the claude list."""
    _make_manifest(tmp_path, ".claude", "myprov")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = legacy_detect(tmp_path)
    assert result["claude"] == ["myprov"]
    assert result["codex"] == []
    assert result["copilot"] == []


def test_legacy_detect_providers_sorted(tmp_path: Path) -> None:
    """Provider names are sorted within each platform list."""
    _make_manifest(tmp_path, ".claude", "beta")
    _make_manifest(tmp_path, ".claude", "alpha")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = legacy_detect(tmp_path)
    assert result["claude"] == ["alpha", "beta"]


def test_legacy_detect_mixed_platforms(tmp_path: Path) -> None:
    """Claude has one provider, copilot has two, codex has none."""
    _make_manifest(tmp_path, ".claude", "league")
    _make_manifest(tmp_path, ".github", "zoo")
    _make_manifest(tmp_path, ".github", "abc")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        result = legacy_detect(tmp_path)
    assert result["claude"] == ["league"]
    assert result["codex"] == []
    assert result["copilot"] == ["abc", "zoo"]
