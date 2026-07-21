"""Tests for `clasi oop` CLI group and subcommands."""

from click.testing import CliRunner

from clasi.cli import cli
from clasi.state_db import get_oop


class TestOopGroup:
    def test_oop_help_exits_zero(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["oop", "--help"])
        assert result.exit_code == 0

    def test_oop_help_lists_subcommands(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["oop", "--help"])
        assert "on" in result.output
        assert "off" in result.output
        assert "status" in result.output

    def test_oop_help_shows_docstring(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["oop", "--help"])
        assert "OOP" in result.output


class TestOopOn:
    def test_on_with_reason_sets_db_record(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            result = runner.invoke(cli, ["oop", "on", "--reason", "testing things"])
            assert result.exit_code == 0

            from pathlib import Path

            db_path = Path(cwd) / ".clasi" / ".clasi.db"
            record = get_oop(str(db_path))
            assert record is not None
            assert record["reason"] == "testing things"

    def test_on_prints_confirmation_with_reason_and_expiry(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["oop", "on", "--reason", "testing things"])
            assert result.exit_code == 0
            assert "testing things" in result.output
            assert "expires" in result.output

    def test_on_default_ttl_is_eight_hours(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            result = runner.invoke(cli, ["oop", "on", "--reason", "testing things"])
            assert result.exit_code == 0

            from datetime import datetime, timezone
            from pathlib import Path

            db_path = Path(cwd) / ".clasi" / ".clasi.db"
            record = get_oop(str(db_path))
            set_at = datetime.fromisoformat(record["set_at"])
            expires_at = datetime.fromisoformat(record["expires_at"])
            delta_hours = (expires_at - set_at).total_seconds() / 3600
            assert abs(delta_hours - 8.0) < 0.01
            assert set_at.tzinfo is not None or expires_at.tzinfo is not None

    def test_on_custom_ttl_hours(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            result = runner.invoke(
                cli, ["oop", "on", "--reason", "quick fix", "--ttl-hours", "1.0"]
            )
            assert result.exit_code == 0

            from datetime import datetime
            from pathlib import Path

            db_path = Path(cwd) / ".clasi" / ".clasi.db"
            record = get_oop(str(db_path))
            set_at = datetime.fromisoformat(record["set_at"])
            expires_at = datetime.fromisoformat(record["expires_at"])
            delta_hours = (expires_at - set_at).total_seconds() / 3600
            assert abs(delta_hours - 1.0) < 0.01

    def test_on_without_reason_prompts_interactively(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            result = runner.invoke(cli, ["oop", "on"], input="prompted reason\n")
            assert result.exit_code == 0

            from pathlib import Path

            db_path = Path(cwd) / ".clasi" / ".clasi.db"
            record = get_oop(str(db_path))
            assert record is not None
            assert record["reason"] == "prompted reason"

    def test_on_without_reason_shows_prompt_text(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["oop", "on"], input="prompted reason\n")
            assert result.exit_code == 0
            assert "Reason" in result.output


class TestOopOff:
    def test_off_clears_db_record(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            runner.invoke(cli, ["oop", "on", "--reason", "testing things"])

            from pathlib import Path

            db_path = Path(cwd) / ".clasi" / ".clasi.db"
            assert get_oop(str(db_path)) is not None

            result = runner.invoke(cli, ["oop", "off"])
            assert result.exit_code == 0
            assert get_oop(str(db_path)) is None

    def test_off_removes_flag_file(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            from pathlib import Path

            clasi_dir = Path(cwd) / ".clasi"
            clasi_dir.mkdir(parents=True, exist_ok=True)
            flag_file = clasi_dir / "oop"
            flag_file.write_text("", encoding="utf-8")

            result = runner.invoke(cli, ["oop", "off"])
            assert result.exit_code == 0
            assert not flag_file.exists()

    def test_off_removes_legacy_flag_file(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            from pathlib import Path

            legacy_flag = Path(cwd) / ".clasi-oop"
            legacy_flag.write_text("", encoding="utf-8")

            result = runner.invoke(cli, ["oop", "off"])
            assert result.exit_code == 0
            assert not legacy_flag.exists()

    def test_off_prints_notice_naming_what_was_cleared(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            from pathlib import Path

            clasi_dir = Path(cwd) / ".clasi"
            clasi_dir.mkdir(parents=True, exist_ok=True)
            (clasi_dir / "oop").write_text("", encoding="utf-8")
            runner.invoke(cli, ["oop", "on", "--reason", "testing things"])

            result = runner.invoke(cli, ["oop", "off"])
            assert result.exit_code == 0
            assert "DB record cleared" in result.output
            assert "oop" in result.output.lower()

    def test_off_with_nothing_active_reports_no_op(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["oop", "off"])
            assert result.exit_code == 0
            assert "no DB record was active" in result.output
            assert "no flag files present" in result.output


class TestOopStatus:
    def test_status_when_inactive(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["oop", "status"])
            assert result.exit_code == 0
            assert "not active" in result.output

    def test_status_reports_db_source(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["oop", "on", "--reason", "testing things"])

            result = runner.invoke(cli, ["oop", "status"])
            assert result.exit_code == 0
            assert "db" in result.output.lower()
            assert "testing things" in result.output

    def test_status_reports_file_source(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            from pathlib import Path

            clasi_dir = Path(cwd) / ".clasi"
            clasi_dir.mkdir(parents=True, exist_ok=True)
            (clasi_dir / "oop").write_text("", encoding="utf-8")

            result = runner.invoke(cli, ["oop", "status"])
            assert result.exit_code == 0
            assert "file" in result.output.lower()
            assert "no audit record" in result.output.lower()

    def test_status_reports_both_sources(self, tmp_path):
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
            from pathlib import Path

            clasi_dir = Path(cwd) / ".clasi"
            clasi_dir.mkdir(parents=True, exist_ok=True)
            (clasi_dir / "oop").write_text("", encoding="utf-8")
            runner.invoke(cli, ["oop", "on", "--reason", "testing things"])

            result = runner.invoke(cli, ["oop", "status"])
            assert result.exit_code == 0
            assert "both" in result.output.lower()
