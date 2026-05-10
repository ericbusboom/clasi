"""
tests/clasr/test_integration_contract.py

Parametrized contract test for IntegrationBase subclasses.

Every integration registered in _TEST_REGISTRY (or, once ticket 006 lands,
INTEGRATION_REGISTRY) must satisfy the install / uninstall contract:

1. install() writes a manifest file at
   target / integration.target_root / ".clasr-manifest" / "<provider>.json".
2. At least one file is installed inside ``target``.
3. uninstall() removes the manifest.

The parametrize source will be switched to::

    from clasr.registry import INTEGRATION_REGISTRY
    @pytest.mark.parametrize("integration_cls", list(INTEGRATION_REGISTRY.values()), ...)

once INTEGRATION_REGISTRY is available (ticket 006). Until then the local
placeholder ``_TEST_REGISTRY`` is used.  When it is empty the test is
collected but immediately skipped, producing exit code 0.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from clasr.integration import IntegrationBase

# ---------------------------------------------------------------------------
# Registry placeholder — replace with INTEGRATION_REGISTRY.values() in ticket 006
# ---------------------------------------------------------------------------

# _TEST_REGISTRY maps platform id → integration class.
# Ticket 006 populates INTEGRATION_REGISTRY; until then this dict is empty and
# the parametrize decorator below yields no test instances (no collection error).
_TEST_REGISTRY: dict[str, type] = {}

# Uncomment after ticket 006 lands:
# from clasr.registry import INTEGRATION_REGISTRY
# _TEST_REGISTRY = dict(INTEGRATION_REGISTRY)


# ---------------------------------------------------------------------------
# Minimal source fixture helper
# ---------------------------------------------------------------------------


def _build_minimal_source(base: Path) -> Path:
    """Create a minimal asr/ source directory under *base* and return its path.

    Layout:
        asr/AGENTS.md
        asr/skills/test-skill/SKILL.md
        asr/agents/agent.md
        asr/rules/rule.md

    This layout is valid for all platform types: each integration type
    (Markdown, Toml, Skills) has at least one relevant source file.
    """
    src = base / "asr"
    src.mkdir(parents=True, exist_ok=True)

    # Top-level AGENTS.md — written to companion_files by marker-block logic
    (src / "AGENTS.md").write_text(
        "Use clasr to manage multi-platform AI agent configurations.\n",
        encoding="utf-8",
    )

    # skills/test-skill/SKILL.md — consumed by SkillsIntegration.render_skill
    skill_dir = src / "skills" / "test-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "# test-skill\nDoes stuff for testing.\n",
        encoding="utf-8",
    )

    # agents/agent.md — consumed by MarkdownIntegration / TomlIntegration.render_agent
    agents_dir = src / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "agent.md").write_text(
        "---\n"
        "name: agent\n"
        "description: A test agent\n"
        "claude: {}\n"
        "codex: {}\n"
        "copilot: {}\n"
        "cursor: {}\n"
        "---\n\n"
        "This is a test agent.\n",
        encoding="utf-8",
    )

    # rules/rule.md — consumed by render_rule
    rules_dir = src / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "rule.md").write_text(
        "---\n"
        "description: A test rule\n"
        "claude: {}\n"
        "codex: {}\n"
        "copilot:\n"
        "  applyTo: '**'\n"
        "cursor: {}\n"
        "---\n\n"
        "Always write clean, readable code.\n",
        encoding="utf-8",
    )

    return src


# ---------------------------------------------------------------------------
# Contract test
# ---------------------------------------------------------------------------


def _ids_for(registry: dict[str, type]) -> list[str]:
    """Return parametrize ids from the registry keys."""
    return list(registry.keys()) if registry else []


@pytest.mark.parametrize(
    "integration_cls",
    list(_TEST_REGISTRY.values()),
    ids=_ids_for(_TEST_REGISTRY),
)
def test_contract_install_uninstall(
    integration_cls: "type[IntegrationBase]",
    tmp_path: Path,
) -> None:
    """Each integration must install then cleanly uninstall.

    Steps
    -----
    1. Build a minimal source tree.
    2. Instantiate the integration class and call ``install()``.
    3. Assert the manifest file exists at
       ``target / integration.target_root / ".clasr-manifest" / "test-provider.json"``.
    4. Assert at least one file was installed inside ``target``.
    5. Call ``uninstall()``.
    6. Assert the manifest file is gone.
    """
    provider = "test-provider"
    source = _build_minimal_source(tmp_path)
    target = tmp_path / "target"
    target.mkdir()

    integration: IntegrationBase = integration_cls()

    # --- install ---
    integration.install(source, target, provider=provider)

    manifest_file = target / integration.target_root / ".clasr-manifest" / f"{provider}.json"
    assert manifest_file.exists(), (
        f"{integration_cls.__name__}: manifest not found at {manifest_file}"
    )

    installed_files = [f for f in target.rglob("*") if f.is_file()]
    assert len(installed_files) >= 1, (
        f"{integration_cls.__name__}: no files installed under {target}"
    )

    # --- uninstall ---
    integration.uninstall(target, provider=provider)

    assert not manifest_file.exists(), (
        f"{integration_cls.__name__}: manifest still present after uninstall at {manifest_file}"
    )
