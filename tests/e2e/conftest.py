"""E2E test configuration.

Overrides the autouse ``_reset_project_singleton`` fixture from the root
conftest so it does not interfere with e2e tests (which do not use the
in-process Project singleton).
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_project_singleton():
    """No-op override — e2e tests don't use the Project singleton."""
    yield
