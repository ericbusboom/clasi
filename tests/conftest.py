"""Shared test fixtures for CLASI tests."""

import pytest

from claude_agent_skills.mcp_server import reset_project


@pytest.fixture(autouse=True)
def _reset_project_singleton():
    """Reset the Project singleton after every test.

    This ensures that tests using set_project() or get_project() don't
    leak state between test cases.
    """
    yield
    reset_project()
