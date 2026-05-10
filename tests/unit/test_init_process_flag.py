"""Tests for the --process flag on `clasi init` and get_active_schema_path().

Covers:
- clasi init --process solo writes process: solo to .clasi/config.yaml
- clasi init with no --process flag writes process: se
- Unknown --process value is rejected before touching any files
- clasi init --process solo followed by get_active_schema_path() returns solo schema
- get_active_schema_path() falls back to se when config is absent
- get_active_schema_path() falls back to se when process key is unrecognised
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from clasi.cli import cli
from clasi.init_command import run_init
from clasi.schemas import get_active_schema_path


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestProcessFlagCLI:
    def test_unknown_process_value_rejected(self, tmp_path: Path) -> None:
        """--process foo fails with a clear error before touching any files."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--process", "foo", str(tmp_path)])

        assert result.exit_code != 0
        # config.yaml must NOT have been written (reject before touching files)
        assert not (tmp_path / ".clasi" / "config.yaml").exists()

    def test_process_solo_writes_config(self, tmp_path: Path) -> None:
        """clasi init --process solo writes process: solo to .clasi/config.yaml."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--process", "solo", str(tmp_path)])

        assert result.exit_code == 0, result.output
        config_path = tmp_path / ".clasi" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "solo"

    def test_process_se_writes_config(self, tmp_path: Path) -> None:
        """clasi init --process se writes process: se to .clasi/config.yaml."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--process", "se", str(tmp_path)])

        assert result.exit_code == 0, result.output
        config_path = tmp_path / ".clasi" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "se"

    def test_no_process_flag_defaults_to_se(self, tmp_path: Path) -> None:
        """clasi init with no --process flag writes process: se."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(tmp_path)])

        assert result.exit_code == 0, result.output
        config_path = tmp_path / ".clasi" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "se"

    def test_error_message_mentions_valid_values(self, tmp_path: Path) -> None:
        """Error message for unknown --process value references valid choices."""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--process", "bad", str(tmp_path)])

        assert result.exit_code != 0
        # Click Choice produces output mentioning the invalid value
        assert "bad" in result.output or "invalid" in result.output.lower() or "choice" in result.output.lower()


# ---------------------------------------------------------------------------
# run_init() unit tests
# ---------------------------------------------------------------------------


class TestRunInitProcessArg:
    def test_solo_writes_solo(self, tmp_path: Path) -> None:
        """run_init(..., process='solo') writes process: solo to config.yaml."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target), process="solo")

        config_path = target / ".clasi" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "solo"

    def test_se_writes_se(self, tmp_path: Path) -> None:
        """run_init(..., process='se') writes process: se to config.yaml."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target), process="se")

        config_path = target / ".clasi" / "config.yaml"
        assert config_path.exists()
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "se"

    def test_default_process_is_se(self, tmp_path: Path) -> None:
        """run_init() with no process argument defaults to se."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target))

        config_path = target / ".clasi" / "config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "se"

    def test_idempotent_process_key(self, tmp_path: Path) -> None:
        """Running init twice preserves the process key (no duplication)."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target), process="solo")
        run_init(str(target), process="solo")

        config_path = target / ".clasi" / "config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "solo"

    def test_update_process_key(self, tmp_path: Path) -> None:
        """Re-running init with a different process overwrites the key."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target), process="se")
        run_init(str(target), process="solo")

        config_path = target / ".clasi" / "config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "solo"

    def test_preserves_other_config_keys(self, tmp_path: Path) -> None:
        """Existing keys in .clasi/config.yaml are preserved when process is updated."""
        target = tmp_path / "repo"
        target.mkdir()

        clasi_dir = target / ".clasi"
        clasi_dir.mkdir(parents=True, exist_ok=True)
        existing = {"process": "se", "custom_key": "custom_value"}
        (clasi_dir / "config.yaml").write_text(
            yaml.safe_dump(existing), encoding="utf-8"
        )

        run_init(str(target), process="solo")

        config_path = clasi_dir / "config.yaml"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["process"] == "solo"
        assert data["custom_key"] == "custom_value"


# ---------------------------------------------------------------------------
# get_active_schema_path() tests
# ---------------------------------------------------------------------------


class TestGetActiveSchemaPath:
    def test_returns_se_schema_when_no_config(self, tmp_path: Path) -> None:
        """get_active_schema_path() returns se schema when no config.yaml exists."""
        schema_path = get_active_schema_path(tmp_path)

        assert schema_path.exists()
        assert "se-process" in str(schema_path)
        assert schema_path.name == "schema.yaml"

    def test_returns_solo_schema_after_solo_init(self, tmp_path: Path) -> None:
        """get_active_schema_path() returns solo schema after clasi init --process solo."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target), process="solo")

        schema_path = get_active_schema_path(target)

        assert schema_path.exists()
        assert "solo-process" in str(schema_path)
        assert schema_path.name == "schema.yaml"

    def test_returns_se_schema_after_se_init(self, tmp_path: Path) -> None:
        """get_active_schema_path() returns se schema after clasi init --process se."""
        target = tmp_path / "repo"
        target.mkdir()

        run_init(str(target), process="se")

        schema_path = get_active_schema_path(target)

        assert schema_path.exists()
        assert "se-process" in str(schema_path)

    def test_falls_back_to_se_for_unknown_process(self, tmp_path: Path) -> None:
        """get_active_schema_path() falls back to se when process key is unrecognised."""
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()
        (clasi_dir / "config.yaml").write_text(
            "process: unknown_value\n", encoding="utf-8"
        )

        schema_path = get_active_schema_path(tmp_path)

        assert "se-process" in str(schema_path)

    def test_falls_back_to_se_for_absent_process_key(self, tmp_path: Path) -> None:
        """get_active_schema_path() falls back to se when process key absent from config."""
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()
        (clasi_dir / "config.yaml").write_text(
            "other_key: other_value\n", encoding="utf-8"
        )

        schema_path = get_active_schema_path(tmp_path)

        assert "se-process" in str(schema_path)

    def test_falls_back_to_se_when_project_root_is_none(self) -> None:
        """get_active_schema_path(None) returns se schema."""
        schema_path = get_active_schema_path(None)

        assert schema_path.exists()
        assert "se-process" in str(schema_path)

    def test_returned_schema_is_loadable(self, tmp_path: Path) -> None:
        """Schema path returned by get_active_schema_path() can be loaded."""
        from clasi.schemas import loader

        target = tmp_path / "repo"
        target.mkdir()
        run_init(str(target), process="solo")

        schema_path = get_active_schema_path(target)
        ws = loader.load(schema_path)
        assert ws is not None

    def test_falls_back_to_se_for_corrupt_config(self, tmp_path: Path) -> None:
        """get_active_schema_path() falls back to se when config.yaml is corrupt YAML."""
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir()
        (clasi_dir / "config.yaml").write_text(
            ":\n  - invalid: [unclosed\n", encoding="utf-8"
        )

        # Should not raise; falls back to se
        schema_path = get_active_schema_path(tmp_path)
        assert "se-process" in str(schema_path)
