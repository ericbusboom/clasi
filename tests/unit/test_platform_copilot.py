"""
tests/unit/test_platform_copilot.py

Minimal tests for clasi/platforms/copilot.py.

Expanded by tickets 007-010 as each stub is implemented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clasi.platforms import copilot
from clasi.platforms._markers import MARKER_END, MARKER_START
import yaml

from clasi.platforms._rules import (
    CLASI_ARTIFACTS_BODY,
    GIT_COMMITS_BODY,
    MCP_REQUIRED_BODY,
    SOURCE_CODE_BODY,
    TODO_DIR_BODY,
)


# ---------------------------------------------------------------------------
# install() — smoke test and .github/skills/ alias
# ---------------------------------------------------------------------------


def test_install_runs_without_error(tmp_path: Path) -> None:
    """install() must complete without raising an exception."""
    copilot.install(tmp_path, mcp_config={})


def test_install_creates_github_skills_symlink(tmp_path: Path) -> None:
    """install() must create .github/skills/ as a symlink to .agents/skills/."""
    copilot.install(tmp_path, mcp_config={})

    github_skills = tmp_path / ".github" / "skills"
    assert github_skills.is_symlink(), ".github/skills/ should be a symlink"
    assert github_skills.resolve() == (tmp_path / ".agents" / "skills").resolve()


def test_install_creates_agents_skills_canonical(tmp_path: Path) -> None:
    """install() must write canonical skill files under .agents/skills/."""
    copilot.install(tmp_path, mcp_config={})

    agents_skills = tmp_path / ".agents" / "skills"
    assert agents_skills.is_dir(), ".agents/skills/ should be a directory"


def test_install_github_skills_is_directory_via_symlink(tmp_path: Path) -> None:
    """The .github/skills/ symlink must resolve to an actual directory."""
    copilot.install(tmp_path, mcp_config={})

    github_skills = tmp_path / ".github" / "skills"
    assert github_skills.is_dir(), ".github/skills/ should resolve to a directory"


def test_install_copy_mode_creates_directory_not_symlink(tmp_path: Path) -> None:
    """With copy=True, .github/skills/ should be a real directory, not a symlink."""
    copilot.install(tmp_path, mcp_config={}, copy=True)

    github_skills = tmp_path / ".github" / "skills"
    assert github_skills.exists(), ".github/skills/ should exist"
    assert not github_skills.is_symlink(), (
        "With copy=True, .github/skills/ should not be a symlink"
    )
    assert github_skills.is_dir(), ".github/skills/ should be a directory"


def test_install_idempotent_symlink(tmp_path: Path) -> None:
    """Calling install() twice must not raise an error (idempotent)."""
    copilot.install(tmp_path, mcp_config={})
    copilot.install(tmp_path, mcp_config={})  # second call should be fine

    github_skills = tmp_path / ".github" / "skills"
    assert github_skills.is_symlink()


# ---------------------------------------------------------------------------
# uninstall() — smoke test and alias removal
# ---------------------------------------------------------------------------


def test_uninstall_runs_without_error(tmp_path: Path) -> None:
    """uninstall() must complete without raising an exception."""
    copilot.install(tmp_path, mcp_config={})
    copilot.uninstall(tmp_path)


def test_uninstall_removes_github_skills_alias(tmp_path: Path) -> None:
    """uninstall() must remove the .github/skills/ alias."""
    copilot.install(tmp_path, mcp_config={})
    copilot.uninstall(tmp_path)

    github_skills = tmp_path / ".github" / "skills"
    assert not github_skills.exists() and not github_skills.is_symlink(), (
        ".github/skills/ should be removed after uninstall"
    )


def test_uninstall_preserves_agents_skills_canonical(tmp_path: Path) -> None:
    """uninstall() must NOT remove the canonical .agents/skills/ directory."""
    copilot.install(tmp_path, mcp_config={})
    copilot.uninstall(tmp_path)

    agents_skills = tmp_path / ".agents" / "skills"
    assert agents_skills.exists(), (
        ".agents/skills/ (canonical) should be preserved after uninstall"
    )


def test_uninstall_without_prior_install(tmp_path: Path) -> None:
    """uninstall() on a fresh directory must not raise."""
    copilot.uninstall(tmp_path)


# ---------------------------------------------------------------------------
# _install_global_instructions — ticket 007
# ---------------------------------------------------------------------------


def test_install_global_instructions_creates_file(tmp_path: Path) -> None:
    """_install_global_instructions must create .github/copilot-instructions.md."""
    copilot._install_global_instructions(tmp_path)
    path = tmp_path / ".github" / "copilot-instructions.md"
    assert path.exists(), ".github/copilot-instructions.md must be created"


def test_install_global_instructions_contains_marker_block(tmp_path: Path) -> None:
    """The file must contain the CLASI marker block."""
    copilot._install_global_instructions(tmp_path)
    content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert MARKER_START in content
    assert MARKER_END in content


def test_install_global_instructions_entry_point(tmp_path: Path) -> None:
    """The CLASI block must reference .github/agents/team-lead.agent.md."""
    copilot._install_global_instructions(tmp_path)
    content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert ".github/agents/team-lead.agent.md" in content


def test_install_global_instructions_mcp_required_body(tmp_path: Path) -> None:
    """The CLASI block must contain the MCP_REQUIRED_BODY content."""
    copilot._install_global_instructions(tmp_path)
    content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    # Check a representative fragment from MCP_REQUIRED_BODY
    assert "`get_version()` to verify the MCP server is running" in content


def test_install_global_instructions_git_commits_body(tmp_path: Path) -> None:
    """The CLASI block must contain the GIT_COMMITS_BODY content."""
    copilot._install_global_instructions(tmp_path)
    content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    # Check a representative fragment from GIT_COMMITS_BODY
    assert "dotconfig version bump" in content


def test_install_global_instructions_idempotent_preserves_user_content(tmp_path: Path) -> None:
    """Re-running _install_global_instructions must preserve user content outside the marker block."""
    path = tmp_path / ".github" / "copilot-instructions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    user_content = "# My Custom Header\n\nSome project-specific instructions.\n"
    path.write_text(user_content, encoding="utf-8")

    # First install appends the CLASI block
    copilot._install_global_instructions(tmp_path)
    content_after_first = path.read_text(encoding="utf-8")
    assert user_content.strip() in content_after_first
    assert MARKER_START in content_after_first

    # Second install replaces the CLASI block in place
    copilot._install_global_instructions(tmp_path)
    content_after_second = path.read_text(encoding="utf-8")
    assert user_content.strip() in content_after_second
    assert MARKER_START in content_after_second


def test_install_global_instructions_idempotent_single_block(tmp_path: Path) -> None:
    """Re-running _install_global_instructions must not create duplicate marker blocks."""
    copilot._install_global_instructions(tmp_path)
    copilot._install_global_instructions(tmp_path)
    content = (tmp_path / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert content.count(MARKER_START) == 1, "Only one CLASI block should exist"
    assert content.count(MARKER_END) == 1, "Only one CLASI block should exist"


# ---------------------------------------------------------------------------
# _uninstall_global_instructions — ticket 007
# ---------------------------------------------------------------------------


def test_uninstall_global_instructions_strips_block(tmp_path: Path) -> None:
    """_uninstall_global_instructions must remove the CLASI marker block."""
    copilot._install_global_instructions(tmp_path)
    copilot._uninstall_global_instructions(tmp_path)
    path = tmp_path / ".github" / "copilot-instructions.md"
    # File may be deleted if it only contained the CLASI block
    if path.exists():
        content = path.read_text(encoding="utf-8")
        assert MARKER_START not in content
        assert MARKER_END not in content


def test_uninstall_global_instructions_preserves_user_content(tmp_path: Path) -> None:
    """_uninstall_global_instructions must preserve user content outside the marker block."""
    path = tmp_path / ".github" / "copilot-instructions.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    user_content = "# My Custom Header\n\nSome project-specific instructions.\n"
    path.write_text(user_content, encoding="utf-8")

    copilot._install_global_instructions(tmp_path)
    assert MARKER_START in path.read_text(encoding="utf-8")

    copilot._uninstall_global_instructions(tmp_path)
    assert path.exists(), "File should remain because it has user content"
    content = path.read_text(encoding="utf-8")
    assert MARKER_START not in content
    assert "My Custom Header" in content


def test_uninstall_global_instructions_no_file(tmp_path: Path) -> None:
    """_uninstall_global_instructions must not raise if the file does not exist."""
    copilot._uninstall_global_instructions(tmp_path)  # no file, must not raise


# ---------------------------------------------------------------------------
# _print_cloud_mcp_notice — ticket 007
# ---------------------------------------------------------------------------


def test_print_cloud_mcp_notice_header(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """_print_cloud_mcp_notice must print the header line."""
    copilot._print_cloud_mcp_notice(mcp_config={"command": "clasi", "args": ["mcp"]})
    captured = capsys.readouterr()
    assert "Copilot Cloud Coding Agent MCP (manual step required):" in captured.out


def test_print_cloud_mcp_notice_settings_url(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """_print_cloud_mcp_notice must print a GitHub Settings URL pattern."""
    copilot._print_cloud_mcp_notice(mcp_config={"command": "clasi", "args": ["mcp"]})
    captured = capsys.readouterr()
    assert "github.com" in captured.out
    assert "settings" in captured.out


def test_print_cloud_mcp_notice_json_snippet(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """_print_cloud_mcp_notice must include valid JSON with the servers key."""
    mcp_config = {"command": "clasi", "args": ["mcp"]}
    copilot._print_cloud_mcp_notice(mcp_config=mcp_config)
    captured = capsys.readouterr()
    # Extract lines that look like JSON and try to parse the snippet
    assert '"servers"' in captured.out
    assert '"clasi"' in captured.out


def test_print_cloud_mcp_notice_includes_mcp_config(capsys: pytest.CaptureFixture) -> None:
    """The JSON snippet must include the mcp_config content."""
    mcp_config = {"command": "clasi", "args": ["mcp"]}
    copilot._print_cloud_mcp_notice(mcp_config=mcp_config)
    captured = capsys.readouterr()
    assert '"command"' in captured.out
    assert "clasi" in captured.out


def test_install_calls_print_cloud_mcp_notice(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """install() must call _print_cloud_mcp_notice at the end."""
    copilot.install(tmp_path, mcp_config={"command": "clasi", "args": ["mcp"]})
    captured = capsys.readouterr()
    assert "Copilot Cloud Coding Agent MCP (manual step required):" in captured.out


# ---------------------------------------------------------------------------
# _install_path_rules / _uninstall_path_rules — ticket 008
# ---------------------------------------------------------------------------

# Map of expected filename -> (applyTo glob, rule body constant)
_EXPECTED_PATH_RULES = [
    ("clasi-artifacts.instructions.md", ".clasi/**", CLASI_ARTIFACTS_BODY),
    ("todo-dir.instructions.md", ".clasi/issues/**", TODO_DIR_BODY),
    ("source-code.instructions.md", "clasi/**", SOURCE_CODE_BODY),
]


def test_install_path_rules_creates_instructions_dir(tmp_path: Path) -> None:
    """`_install_path_rules` must create .github/instructions/ if absent."""
    copilot._install_path_rules(tmp_path)
    assert (tmp_path / ".github" / "instructions").is_dir()


def test_install_path_rules_creates_all_files(tmp_path: Path) -> None:
    """`_install_path_rules` must write one file per CLASI path rule."""
    copilot._install_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    for fname, _apply_to, _body in _EXPECTED_PATH_RULES:
        assert (rules_dir / fname).exists(), f"Expected {fname} to exist"


def test_install_path_rules_valid_yaml_frontmatter(tmp_path: Path) -> None:
    """Each emitted file must have parseable YAML frontmatter."""
    copilot._install_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    for fname, _apply_to, _body in _EXPECTED_PATH_RULES:
        content = (rules_dir / fname).read_text(encoding="utf-8")
        # YAML frontmatter is between the first two "---" delimiters
        parts = content.split("---", maxsplit=2)
        assert len(parts) >= 3, f"{fname}: expected YAML frontmatter delimiters"
        fm = yaml.safe_load(parts[1])
        assert fm is not None, f"{fname}: frontmatter must not be empty"
        assert "applyTo" in fm, f"{fname}: frontmatter must contain 'applyTo' key"


def test_install_path_rules_apply_to_values(tmp_path: Path) -> None:
    """Each file's `applyTo` frontmatter value must match the expected glob."""
    copilot._install_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    for fname, apply_to, _body in _EXPECTED_PATH_RULES:
        content = (rules_dir / fname).read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        fm = yaml.safe_load(parts[1])
        assert fm["applyTo"] == apply_to, (
            f"{fname}: expected applyTo={apply_to!r}, got {fm['applyTo']!r}"
        )


def test_install_path_rules_body_content(tmp_path: Path) -> None:
    """Each file's body must match the corresponding _rules.py constant."""
    copilot._install_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    for fname, _apply_to, body in _EXPECTED_PATH_RULES:
        content = (rules_dir / fname).read_text(encoding="utf-8")
        # Body follows the closing "---" of frontmatter
        parts = content.split("---", maxsplit=2)
        file_body = parts[2].strip()
        assert file_body == body.strip(), (
            f"{fname}: body content does not match expected constant"
        )


def test_install_path_rules_idempotent(tmp_path: Path) -> None:
    """Calling `_install_path_rules` twice must produce the same files (no error)."""
    copilot._install_path_rules(tmp_path)
    copilot._install_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    for fname, _apply_to, _body in _EXPECTED_PATH_RULES:
        assert (rules_dir / fname).exists()


def test_uninstall_path_rules_removes_clasi_files(tmp_path: Path) -> None:
    """`_uninstall_path_rules` must remove all CLASI-written instruction files."""
    copilot._install_path_rules(tmp_path)
    copilot._uninstall_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    for fname, _apply_to, _body in _EXPECTED_PATH_RULES:
        assert not (rules_dir / fname).exists(), f"{fname} should be removed after uninstall"


def test_uninstall_path_rules_preserves_user_files(tmp_path: Path) -> None:
    """`_uninstall_path_rules` must not remove user-created files."""
    copilot._install_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    user_file = rules_dir / "my-custom.instructions.md"
    user_file.write_text("# User content\n", encoding="utf-8")

    copilot._uninstall_path_rules(tmp_path)

    assert user_file.exists(), "User-created file must not be removed by uninstall"


def test_uninstall_path_rules_does_not_rmdir(tmp_path: Path) -> None:
    """`_uninstall_path_rules` must NOT remove .github/instructions/ even if empty."""
    copilot._install_path_rules(tmp_path)
    copilot._uninstall_path_rules(tmp_path)
    rules_dir = tmp_path / ".github" / "instructions"
    assert rules_dir.exists(), ".github/instructions/ must remain after uninstall"


def test_uninstall_path_rules_no_install(tmp_path: Path) -> None:
    """`_uninstall_path_rules` on a fresh directory must not raise."""
    copilot._uninstall_path_rules(tmp_path)  # no prior install, must not raise


# ---------------------------------------------------------------------------
# _install_agents / _uninstall_agents — ticket 009
# ---------------------------------------------------------------------------

_CLASI_AGENT_NAMES = ["team-lead", "sprint-planner", "programmer"]


def test_install_agents_creates_agents_dir(tmp_path: Path) -> None:
    """`_install_agents` must create .github/agents/ if absent."""
    copilot._install_agents(tmp_path)
    assert (tmp_path / ".github" / "agents").is_dir()


def test_install_agents_creates_all_agent_files(tmp_path: Path) -> None:
    """`_install_agents` must write one .agent.md file per CLASI agent."""
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        assert (agents_dir / f"{name}.agent.md").exists(), (
            f"Expected {name}.agent.md to be created"
        )


def test_install_agents_valid_yaml_frontmatter(tmp_path: Path) -> None:
    """Each .agent.md must have parseable YAML frontmatter."""
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        content = (agents_dir / f"{name}.agent.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        assert len(parts) >= 3, f"{name}.agent.md: expected YAML frontmatter delimiters"
        fm = yaml.safe_load(parts[1])
        assert fm is not None, f"{name}.agent.md: frontmatter must not be empty"


def test_install_agents_description_present(tmp_path: Path) -> None:
    """Each .agent.md frontmatter must have a non-empty `description` field."""
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        content = (agents_dir / f"{name}.agent.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        fm = yaml.safe_load(parts[1])
        assert "description" in fm, f"{name}.agent.md: missing 'description' in frontmatter"
        assert fm["description"], f"{name}.agent.md: description must be non-empty"


def test_install_agents_description_from_source(tmp_path: Path) -> None:
    """Each .agent.md description must match the source plugin agent.md description."""
    from clasi.frontmatter import read_document
    from clasi.platforms.copilot import _PLUGIN_DIR

    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        source_md = _PLUGIN_DIR / "agents" / name / "agent.md"
        if not source_md.exists():
            continue
        source_fm, _ = read_document(source_md)
        expected_desc = source_fm.get("description", f"CLASI {name} agent")

        content = (agents_dir / f"{name}.agent.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        fm = yaml.safe_load(parts[1])
        assert fm["description"] == expected_desc, (
            f"{name}.agent.md: description mismatch"
        )


def test_install_agents_body_non_empty(tmp_path: Path) -> None:
    """Each .agent.md body (after frontmatter) must be non-empty."""
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        content = (agents_dir / f"{name}.agent.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        assert len(parts) >= 3, f"{name}.agent.md: expected frontmatter block"
        body = parts[2].strip()
        assert body, f"{name}.agent.md: body must be non-empty"


def test_install_agents_body_from_source(tmp_path: Path) -> None:
    """Each .agent.md body must match the source plugin agent.md body."""
    from clasi.frontmatter import read_document
    from clasi.platforms.copilot import _PLUGIN_DIR

    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        source_md = _PLUGIN_DIR / "agents" / name / "agent.md"
        if not source_md.exists():
            continue
        _, source_body = read_document(source_md)

        content = (agents_dir / f"{name}.agent.md").read_text(encoding="utf-8")
        parts = content.split("---", maxsplit=2)
        file_body = parts[2]
        # Source body is included verbatim (may have leading newline stripped)
        assert source_body.strip() in file_body, (
            f"{name}.agent.md: body does not match source"
        )


def test_install_agents_idempotent(tmp_path: Path) -> None:
    """`_install_agents` called twice must not raise and files remain consistent."""
    copilot._install_agents(tmp_path)
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        assert (agents_dir / f"{name}.agent.md").exists()


def test_uninstall_agents_removes_clasi_files(tmp_path: Path) -> None:
    """`_uninstall_agents` must remove all CLASI-written .agent.md files."""
    copilot._install_agents(tmp_path)
    copilot._uninstall_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    for name in _CLASI_AGENT_NAMES:
        assert not (agents_dir / f"{name}.agent.md").exists(), (
            f"{name}.agent.md should be removed after uninstall"
        )


def test_uninstall_agents_preserves_user_files(tmp_path: Path) -> None:
    """`_uninstall_agents` must not remove user-created files in .github/agents/."""
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    user_file = agents_dir / "my-custom-agent.md"
    user_file.write_text("# User agent\n", encoding="utf-8")

    copilot._uninstall_agents(tmp_path)

    assert user_file.exists(), "User-created file must not be removed by uninstall"


def test_uninstall_agents_removes_empty_dir(tmp_path: Path) -> None:
    """`_uninstall_agents` must remove .github/agents/ if it becomes empty."""
    copilot._install_agents(tmp_path)
    copilot._uninstall_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    assert not agents_dir.exists(), (
        ".github/agents/ should be removed when it is empty after uninstall"
    )


def test_uninstall_agents_preserves_nonempty_dir(tmp_path: Path) -> None:
    """`_uninstall_agents` must NOT remove .github/agents/ if user files remain."""
    copilot._install_agents(tmp_path)
    agents_dir = tmp_path / ".github" / "agents"
    (agents_dir / "user.agent.md").write_text("# user\n", encoding="utf-8")

    copilot._uninstall_agents(tmp_path)

    assert agents_dir.exists(), (
        ".github/agents/ must remain when user files are present"
    )


def test_uninstall_agents_no_install(tmp_path: Path) -> None:
    """`_uninstall_agents` on a fresh directory must not raise."""
    copilot._uninstall_agents(tmp_path)  # no prior install, must not raise


# ---------------------------------------------------------------------------
# _install_vscode_mcp / _uninstall_vscode_mcp — ticket 010
# ---------------------------------------------------------------------------

_MCP_CONFIG = {"command": "clasi", "args": ["mcp"]}


def test_install_vscode_mcp_fresh_creates_file(tmp_path: Path) -> None:
    """`_install_vscode_mcp` on a clean target creates .vscode/mcp.json."""
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    mcp_path = tmp_path / ".vscode" / "mcp.json"
    assert mcp_path.exists(), ".vscode/mcp.json must be created on fresh install"


def test_install_vscode_mcp_fresh_content(tmp_path: Path) -> None:
    """Fresh install must write servers.clasi equal to mcp_config."""
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    data = json.loads((tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert "servers" in data
    assert data["servers"]["clasi"] == _MCP_CONFIG


def test_install_vscode_mcp_creates_vscode_dir(tmp_path: Path) -> None:
    """`_install_vscode_mcp` must create .vscode/ if it does not exist."""
    assert not (tmp_path / ".vscode").exists()
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    assert (tmp_path / ".vscode").is_dir()


def test_install_vscode_mcp_merge_preserves_user_keys(tmp_path: Path) -> None:
    """Install into an existing file must preserve user-owned keys."""
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    existing = {
        "servers": {"my-server": {"command": "my-cmd", "args": []}},
        "inputs": [{"id": "my-input", "type": "promptString"}],
    }
    (vscode_dir / "mcp.json").write_text(json.dumps(existing), encoding="utf-8")

    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)

    data = json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
    # clasi entry added
    assert data["servers"]["clasi"] == _MCP_CONFIG
    # user server preserved
    assert "my-server" in data["servers"]
    assert data["servers"]["my-server"] == existing["servers"]["my-server"]
    # top-level user key preserved
    assert data["inputs"] == existing["inputs"]


def test_install_vscode_mcp_corrupt_json_skips(tmp_path: Path) -> None:
    """If .vscode/mcp.json is corrupt JSON, the file must not be modified."""
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    bad_content = "{not valid json"
    (vscode_dir / "mcp.json").write_text(bad_content, encoding="utf-8")

    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)

    # File must be unchanged
    assert (vscode_dir / "mcp.json").read_text(encoding="utf-8") == bad_content


def test_install_vscode_mcp_idempotent(tmp_path: Path) -> None:
    """Calling `_install_vscode_mcp` twice must produce the same file."""
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    first = (tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8")
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    second = (tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8")
    assert first == second


def test_uninstall_vscode_mcp_removes_clasi_key(tmp_path: Path) -> None:
    """`_uninstall_vscode_mcp` must remove servers.clasi from the file."""
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    copilot._uninstall_vscode_mcp(tmp_path)
    data = json.loads((tmp_path / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert "clasi" not in data.get("servers", {})


def test_uninstall_vscode_mcp_preserves_other_servers(tmp_path: Path) -> None:
    """`_uninstall_vscode_mcp` must preserve other entries in servers."""
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    existing = {
        "servers": {
            "my-server": {"command": "my-cmd"},
            "clasi": _MCP_CONFIG,
        }
    }
    (vscode_dir / "mcp.json").write_text(json.dumps(existing), encoding="utf-8")

    copilot._uninstall_vscode_mcp(tmp_path)

    data = json.loads((vscode_dir / "mcp.json").read_text(encoding="utf-8"))
    assert "clasi" not in data["servers"]
    assert "my-server" in data["servers"]


def test_uninstall_vscode_mcp_no_file_noop(tmp_path: Path) -> None:
    """`_uninstall_vscode_mcp` on a fresh directory must not raise."""
    copilot._uninstall_vscode_mcp(tmp_path)  # no file, must not raise


def test_uninstall_vscode_mcp_does_not_delete_vscode_dir(tmp_path: Path) -> None:
    """`_uninstall_vscode_mcp` must not delete the .vscode/ directory."""
    copilot._install_vscode_mcp(tmp_path, _MCP_CONFIG)
    copilot._uninstall_vscode_mcp(tmp_path)
    assert (tmp_path / ".vscode").is_dir(), ".vscode/ must remain after uninstall"


def test_uninstall_vscode_mcp_corrupt_json_skips(tmp_path: Path) -> None:
    """If .vscode/mcp.json is corrupt on uninstall, file must not be modified."""
    vscode_dir = tmp_path / ".vscode"
    vscode_dir.mkdir()
    bad_content = "{not valid json"
    (vscode_dir / "mcp.json").write_text(bad_content, encoding="utf-8")

    copilot._uninstall_vscode_mcp(tmp_path)

    assert (vscode_dir / "mcp.json").read_text(encoding="utf-8") == bad_content


# ---------------------------------------------------------------------------
# Version stamp — consolidated .clasi/clasi-version
# ---------------------------------------------------------------------------

_MCP_CONFIG = {"command": "clasi", "args": ["mcp"]}


def test_copilot_install_writes_clasi_clasi_version(tmp_path: Path) -> None:
    """install() writes .clasi/clasi-version; no per-platform stamp files."""
    copilot.install(tmp_path, mcp_config=_MCP_CONFIG)

    stamp = tmp_path / ".clasi" / "clasi-version"
    assert stamp.exists(), ".clasi/clasi-version must exist after copilot install"

    for stale_dir in [".github", ".agents"]:
        stale = tmp_path / stale_dir / ".clasi-version"
        assert not stale.exists(), (
            f"{stale_dir}/.clasi-version must not be written (old format)"
        )


def test_copilot_install_removes_stale_per_platform_stamps(tmp_path: Path) -> None:
    """install() removes pre-existing stale per-platform stamp files."""
    for stale_dir in [".github", ".agents"]:
        stale = tmp_path / stale_dir / ".clasi-version"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("0.old\n", encoding="utf-8")

    copilot.install(tmp_path, mcp_config=_MCP_CONFIG)

    for stale_dir in [".github", ".agents"]:
        stale = tmp_path / stale_dir / ".clasi-version"
        assert not stale.exists(), f"Stale {stale_dir}/.clasi-version must be removed"


def test_copilot_uninstall_removes_clasi_version_stamp(tmp_path: Path) -> None:
    """uninstall() removes .clasi/clasi-version."""
    copilot.install(tmp_path, mcp_config=_MCP_CONFIG)
    copilot.uninstall(tmp_path)
    assert not (tmp_path / ".clasi" / "clasi-version").exists(), (
        ".clasi/clasi-version must be removed by copilot uninstall"
    )
