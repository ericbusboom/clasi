"""Unit tests for the skill stub loader — resolve_skill_body and get_skill_definition.

Covers:
- resolve_skill_body: passthrough when no Load from: directive present
- resolve_skill_body: resolves Load from: directive, replaces body
- resolve_skill_body: preserves YAML frontmatter
- resolve_skill_body: raises FileNotFoundError for missing reference
- get_skill_definition: returns full prose for each of the five stubbed skills
- _install_plugin_content: writes expanded content (not stub) to canonical path
"""
from __future__ import annotations

from pathlib import Path

import pytest

from clasi.tools.process_tools import resolve_skill_body, get_skill_definition
from clasi.platforms import claude as claude_mod
from clasi.platforms.claude import _PLUGIN_DIR


# ---------------------------------------------------------------------------
# resolve_skill_body — unit tests
# ---------------------------------------------------------------------------


class TestResolveSkillBodyPassthrough:
    def test_returns_raw_when_no_directive(self, tmp_path: Path) -> None:
        raw = "---\nname: foo\n---\n\n# Foo\n\nSome content.\n"
        assert resolve_skill_body(raw) == raw

    def test_no_frontmatter_no_directive_passthrough(self) -> None:
        raw = "# Just markdown, no directive.\n"
        assert resolve_skill_body(raw) == raw

    def test_comment_not_treated_as_directive(self) -> None:
        raw = "---\nname: bar\n---\n\n<!-- Load from: `something.md` -->\n# Bar\n"
        # Inside an HTML comment — should not match
        assert resolve_skill_body(raw) == raw


class TestResolveSkillBodyResolution:
    def test_replaces_body_with_referenced_file(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "my-instruction.md"
        instruction_file.write_text("# Full Prose\n\nDetailed instructions here.\n")

        raw = "---\nname: my-skill\ndescription: A skill\n---\n\nBrief description.\n\n## Instructions\n\nLoad from: `my-instruction.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert "# Full Prose" in result
        assert "Detailed instructions here." in result

    def test_preserves_frontmatter(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "body.md"
        instruction_file.write_text("# Body Content\n")

        raw = "---\nname: my-skill\ndescription: My description\n---\n\nLoad from: `body.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert result.startswith("---\nname: my-skill\ndescription: My description\n---\n")
        assert "# Body Content" in result

    def test_stub_body_not_in_result(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "full.md"
        instruction_file.write_text("# Full Instructions\n")

        raw = "---\nname: x\n---\n\nBrief stub text.\n\nLoad from: `full.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert "Brief stub text." not in result
        assert "# Full Instructions" in result

    def test_raises_file_not_found_for_missing_ref(self, tmp_path: Path) -> None:
        raw = "---\nname: y\n---\n\nLoad from: `nonexistent.md`\n"
        with pytest.raises(FileNotFoundError, match="nonexistent.md"):
            resolve_skill_body(raw, base_path=tmp_path)

    def test_no_frontmatter_still_resolves(self, tmp_path: Path) -> None:
        instruction_file = tmp_path / "no-fm.md"
        instruction_file.write_text("# No FM\nContent.\n")

        raw = "Load from: `no-fm.md`\n"
        result = resolve_skill_body(raw, base_path=tmp_path)

        assert "# No FM" in result


# ---------------------------------------------------------------------------
# Five stub SKILL.md files — verify structure
# ---------------------------------------------------------------------------

_STUB_SKILLS = [
    ("plan-sprint", "sprint-plan.md", "sprint-plan"),
    ("execute-sprint", "execution.md", "execution"),
    ("architecture-review", "architecture-update.md", "architecture-update"),
    ("sprint-review", "sprint-review.md", "sprint-review"),
    ("close-sprint", "close.md", "close"),
]


class TestStubSkillFiles:
    """Verify each stub SKILL.md has the right frontmatter and load directive."""

    @pytest.mark.parametrize("skill_name,instruction_file,_", _STUB_SKILLS)
    def test_stub_has_name_frontmatter(self, skill_name: str, instruction_file: str, _) -> None:
        skill_md = _PLUGIN_DIR / "skills" / skill_name / "SKILL.md"
        assert skill_md.exists(), f"SKILL.md missing for {skill_name}"
        content = skill_md.read_text(encoding="utf-8")
        assert f"name: {skill_name}" in content

    @pytest.mark.parametrize("skill_name,instruction_file,_", _STUB_SKILLS)
    def test_stub_has_description_frontmatter(self, skill_name: str, instruction_file: str, _) -> None:
        skill_md = _PLUGIN_DIR / "skills" / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert "description:" in content

    @pytest.mark.parametrize("skill_name,instruction_file,_", _STUB_SKILLS)
    def test_stub_has_load_from_directive(self, skill_name: str, instruction_file: str, _) -> None:
        skill_md = _PLUGIN_DIR / "skills" / skill_name / "SKILL.md"
        content = skill_md.read_text(encoding="utf-8")
        assert f"Load from: `clasi/schemas/se-process/instructions/{instruction_file}`" in content

    @pytest.mark.parametrize("skill_name,instruction_file,_", _STUB_SKILLS)
    def test_referenced_instruction_file_exists(self, skill_name: str, instruction_file: str, _) -> None:
        from clasi.skill_resolve import _PACKAGE_ROOT
        ref = _PACKAGE_ROOT / "clasi" / "schemas" / "se-process" / "instructions" / instruction_file
        assert ref.exists(), f"Instruction file missing: {ref}"


# ---------------------------------------------------------------------------
# get_skill_definition — resolves Load from: for stubbed skills
# ---------------------------------------------------------------------------


class TestGetSkillDefinitionResolvesStubs:
    """get_skill_definition must return the full instruction prose, not the stub."""

    @pytest.mark.parametrize("skill_name,instruction_file,heading_fragment", _STUB_SKILLS)
    def test_returns_full_prose(self, skill_name: str, instruction_file: str, heading_fragment: str) -> None:
        content = get_skill_definition(skill_name)
        # Must contain substantial prose (more than just the stub)
        assert len(content) > 200, f"{skill_name}: content too short, Load from: not resolved"

    @pytest.mark.parametrize("skill_name,instruction_file,heading_fragment", _STUB_SKILLS)
    def test_contains_frontmatter_fields(self, skill_name: str, instruction_file: str, heading_fragment: str) -> None:
        content = get_skill_definition(skill_name)
        assert f"name: {skill_name}" in content

    @pytest.mark.parametrize("skill_name,instruction_file,heading_fragment", _STUB_SKILLS)
    def test_stub_brief_description_not_in_result(self, skill_name: str, instruction_file: str, heading_fragment: str) -> None:
        """The stub's brief one-liner body should not appear in the resolved result."""
        content = get_skill_definition(skill_name)
        # The Load from: directive line itself should not appear in the resolved body
        assert "Load from:" not in content


# ---------------------------------------------------------------------------
# _install_plugin_content — writes expanded content to canonical
# ---------------------------------------------------------------------------


class TestInstallExpandsStubs:
    """install() must write expanded (not stub) content to .agents/skills/<n>/SKILL.md."""

    @pytest.mark.parametrize("skill_name,instruction_file,_", _STUB_SKILLS)
    def test_canonical_has_no_load_from_directive(
        self, tmp_path: Path, skill_name: str, instruction_file: str, _
    ) -> None:
        claude_mod.install(tmp_path, mcp_config={})
        canonical = tmp_path / ".agents" / "skills" / skill_name / "SKILL.md"
        assert canonical.exists()
        content = canonical.read_text(encoding="utf-8")
        assert "Load from:" not in content, (
            f"Canonical for {skill_name} still contains Load from: — not expanded"
        )

    @pytest.mark.parametrize("skill_name,instruction_file,_", _STUB_SKILLS)
    def test_canonical_has_full_prose(
        self, tmp_path: Path, skill_name: str, instruction_file: str, _
    ) -> None:
        claude_mod.install(tmp_path, mcp_config={})
        canonical = tmp_path / ".agents" / "skills" / skill_name / "SKILL.md"
        content = canonical.read_text(encoding="utf-8")
        assert len(content) > 200, (
            f"Canonical for {skill_name} is too short — instruction prose not included"
        )
