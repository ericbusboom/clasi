"""Tests for clasi.templates — the single-doc sprint.md template."""

from clasi.templates import SPRINT_TEMPLATE


class TestSprintTemplateSingleDocSections:
    """sprint.md folds in the former usecases.md/architecture-update.md

    content as sections, per the single-doc sprint model.
    """

    def test_contains_architecture_section(self):
        assert "## Architecture" in SPRINT_TEMPLATE

    def test_contains_use_cases_section(self):
        assert "## Use Cases" in SPRINT_TEMPLATE

    def test_architecture_section_notes_sizing_to_change(self):
        """The Architecture section notes it may be N/A for trivial changes."""
        idx = SPRINT_TEMPLATE.index("## Architecture")
        # Look at the section body (up to the next top-level heading)
        next_heading = SPRINT_TEMPLATE.index("## Use Cases")
        section = SPRINT_TEMPLATE[idx:next_heading]
        assert "sized to the change" in section
        assert "N/A" in section

    def test_use_cases_section_notes_sizing_to_change(self):
        """The Use Cases section notes it may be N/A for trivial changes."""
        idx = SPRINT_TEMPLATE.index("## Use Cases")
        next_heading = SPRINT_TEMPLATE.index("## GitHub Issues")
        section = SPRINT_TEMPLATE[idx:next_heading]
        assert "sized to the change" in section
        assert "N/A" in section

    def test_no_duplicate_architecture_headings(self):
        """Only one top-level '## Architecture' heading — no leftover

        duplicate section (e.g. from the old 'Architecture Notes' heading).
        """
        top_level_headings = [
            line for line in SPRINT_TEMPLATE.splitlines()
            if line.strip() == "## Architecture"
        ]
        assert len(top_level_headings) == 1
        assert "## Architecture Notes" not in SPRINT_TEMPLATE
