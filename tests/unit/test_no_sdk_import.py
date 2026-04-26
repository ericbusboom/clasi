"""Guard tests: core CLASI modules must not import claude_agent_sdk."""

import importlib
import sys
from pathlib import Path

import pytest

MODULES_TO_CHECK = [
    "clasi.agent",
    "clasi.project",
    "clasi.tools.artifact_tools",
    "clasi.tools.process_tools",
]


@pytest.mark.parametrize("module_name", MODULES_TO_CHECK)
def test_module_does_not_import_sdk(module_name):
    sys.modules.pop("claude_agent_sdk", None)
    importlib.import_module(module_name)
    assert "claude_agent_sdk" not in sys.modules, (
        f"{module_name} transitively imported claude_agent_sdk"
    )


OLD_DELEGATION_NAMES = [
    "code-monkey", "sprint-executor", "ad-hoc-executor",
    "technical-lead", "project-manager", "code-reviewer",
]


def test_active_plugin_files_have_no_old_delegation_targets():
    plugin_agents = Path(__file__).parent.parent.parent / "clasi" / "plugin" / "agents"
    violations = []
    for path in plugin_agents.rglob("*"):
        if "old" in path.parts:
            continue
        if path.suffix not in {".md", ".yaml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for old_name in OLD_DELEGATION_NAMES:
            if old_name in text:
                violations.append(f"{path.name}: contains '{old_name}'")
    assert not violations, "Old agent names found in active plugin files:\n" + "\n".join(violations)
