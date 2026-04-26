"""Tests for TOML compatibility shim (tomllib / tomli + tomli-w)."""

import tomli_w


def test_toml_shim_importable() -> None:
    """The conditional TOML reader shim imports without error."""
    try:
        import tomllib  # noqa: F401  (stdlib, Python 3.11+)
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]  # noqa: F401

    # If we reach here the import succeeded on this Python version.
    assert tomllib is not None


def test_toml_round_trip() -> None:
    """A dict written by tomli_w round-trips correctly through the shim reader."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    original = {"section": {"key": "value"}}
    toml_bytes = tomli_w.dumps(original).encode()
    result = tomllib.loads(toml_bytes.decode())
    assert result == original
