"""Tests for SE overview template documentation completeness.

These tests assert that critical sections exist in the SE overview template
so they cannot silently drift out over time.
"""

from clasi.tools.process_tools import _SE_OVERVIEW_TEMPLATE_PATH


class TestExceptionProtocolSection:
    """Assert that the Exception protocol section exists in the SE overview template."""

    def test_exception_protocol_section_exists(self):
        """se-overview-template.md must contain an 'Exception protocol' heading."""
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Exception protocol" in content, (
            "se-overview-template.md is missing an 'Exception protocol' section. "
            "Add the section or update the heading text to include 'Exception protocol'."
        )

    def test_exception_protocol_covers_threshold(self):
        """The Exception protocol section must mention the three-attempt cap."""
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "three" in content.lower() or "3" in content, (
            "Exception protocol section should reference the three-attempt threshold."
        )

    def test_exception_protocol_mentions_thrown_by(self):
        """The section must mention the agents that can throw exceptions."""
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "thrown_by" in content or "programmer" in content, (
            "Exception protocol section should mention who can throw (thrown_by field)."
        )

    def test_exception_protocol_mentions_surface(self):
        """The section must mention the surface field or escalation visibility."""
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "surface" in content or "user-visible" in content, (
            "Exception protocol section should document the surface field."
        )

    def test_exception_protocol_mentions_team_lead_routing(self):
        """The section must describe team-lead routing or handling."""
        content = _SE_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "team-lead" in content or "routing" in content, (
            "Exception protocol section should describe team-lead routing."
        )
