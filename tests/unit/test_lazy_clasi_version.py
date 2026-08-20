"""Tests for clasi.__init__'s lazy __version__ resolution (sprint 026 / ticket 004).

A plain `import clasi` previously paid an eager
`importlib.metadata.version("clasi")` call (about 33ms) on every
import — including every `clasi hook <event>` CLI process, most of
which never read __version__ at all (role-guard, mcp-guard, and
status-inject's non-staleness paths never touch it; only
clasi.staleness.check_staleness, the sole current consumer of the real
version, needs it). __version__ is now resolved lazily via a module
__getattr__ (PEP 562) on first actual access, and cached in
clasi._cached_version for the rest of the process.
"""

import importlib
import importlib.metadata
from unittest.mock import patch

import pytest

import clasi


class TestLazyVersionResolution:
    def setup_method(self):
        # Force a clean re-import for each test so a prior test's (or
        # ordinary test-collection imports elsewhere in the suite)
        # already-cached clasi._cached_version can't leak in and make an
        # assertion here vacuously pass.
        importlib.reload(clasi)

    def test_plain_import_does_not_set_version_in_module_dict(self):
        """A fresh import must not populate __version__ in the module's
        own __dict__ — if it did, that would mean it was computed
        eagerly at import time (the old behavior), not lazily via
        __getattr__ on first access."""
        assert "__version__" not in vars(clasi)

    def test_plain_import_does_not_call_importlib_metadata_version(self):
        """Reloading the module (equivalent to a fresh import) must not
        call importlib.metadata.version at all."""
        with patch("importlib.metadata.version") as mock_version:
            importlib.reload(clasi)
            mock_version.assert_not_called()

    def test_accessing_dunder_version_resolves_the_real_value(self):
        real_version = importlib.metadata.version("clasi")
        assert clasi.__version__ == real_version

    def test_from_import_resolves_the_real_value(self):
        """The actual consumer idiom used throughout hook_handlers.py /
        mcp_server.py: `from clasi import __version__ as _running_version`
        inside a function body — must resolve correctly on demand."""
        from clasi import __version__ as running_version

        assert running_version == importlib.metadata.version("clasi")

    def test_second_access_does_not_recall_importlib_metadata_version(self):
        """The resolved value is cached after first access — a second
        access within the same process must not re-scan metadata."""
        _ = clasi.__version__  # prime the cache
        with patch("importlib.metadata.version") as mock_version:
            _ = clasi.__version__
            mock_version.assert_not_called()

    def test_resolution_failure_falls_back_to_unknown_sentinel(self):
        """Same fallback the previous eager form used: any resolution
        failure (e.g. no installed distribution record) must not raise
        out of attribute access."""
        with patch(
            "importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError("clasi"),
        ):
            assert clasi.__version__ == "0.0.0-unknown"

    def test_unrelated_attribute_still_raises_attribute_error(self):
        """__getattr__ must not swallow lookups for attributes that
        genuinely don't exist on the module."""
        with pytest.raises(AttributeError):
            clasi.not_a_real_attribute
