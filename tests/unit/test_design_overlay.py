"""Tests for clasi.design.overlay — git-anchored overlay copy/diff/apply lifecycle."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from clasi.design.overlay import (
    OverlayApplyError,
    apply,
    commit_edits,
    generate_diffs,
    seed_and_commit,
)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return result


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["init"], repo)
    _run(["config", "user.email", "test@example.com"], repo)
    _run(["config", "user.name", "Test"], repo)
    return repo


def _make_canonical_doc(repo: Path, name: str, content: str) -> Path:
    design_dir = repo / "docs" / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    path = design_dir / name
    path.write_text(content, encoding="utf-8")
    _run(["add", str(path)], repo)
    _run(["commit", "-m", f"add {name}"], repo)
    return path


def _commit_count(repo: Path) -> int:
    result = _run(["rev-list", "--count", "HEAD"], repo)
    return int(result.stdout.strip())


def _last_commit_message(repo: Path) -> str:
    result = _run(["log", "-1", "--format=%s"], repo)
    return result.stdout.strip()


class TestSeedAndCommit:
    def test_copies_verbatim_and_commits(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"

        before_commits = _commit_count(repo)
        seeded = seed_and_commit([canonical], sprint_design_dir, repo_root=repo)

        assert len(seeded) == 1
        seeded_path = seeded[0]
        assert seeded_path == sprint_design_dir / "clasi-tools.md"
        assert seeded_path.read_text(encoding="utf-8") == canonical.read_text(
            encoding="utf-8"
        )

        after_commits = _commit_count(repo)
        assert after_commits == before_commits + 1

        status = _run(["status", "--porcelain"], repo)
        assert status.stdout.strip() == ""

    def test_seeds_multiple_files_in_single_commit(self, tmp_path):
        repo = _init_repo(tmp_path)
        doc1 = _make_canonical_doc(repo, "a.md", "A\n")
        doc2 = _make_canonical_doc(repo, "b.md", "B\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"

        before_commits = _commit_count(repo)
        seed_and_commit([doc1, doc2], sprint_design_dir, repo_root=repo)

        assert _commit_count(repo) == before_commits + 1
        assert (sprint_design_dir / "a.md").exists()
        assert (sprint_design_dir / "b.md").exists()

    def test_empty_list_is_a_noop(self, tmp_path):
        repo = _init_repo(tmp_path)
        _make_canonical_doc(repo, "a.md", "A\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"

        before_commits = _commit_count(repo)
        seeded = seed_and_commit([], sprint_design_dir, repo_root=repo)

        assert seeded == []
        assert _commit_count(repo) == before_commits


class TestGenerateDiffs:
    def _seeded_repo(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"
        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)
        return repo, sprint_design_dir

    def test_no_diff_written_when_unedited(self, tmp_path):
        repo, sprint_design_dir = self._seeded_repo(tmp_path)
        written = generate_diffs(sprint_design_dir, repo_root=repo)
        assert written == []
        assert not (sprint_design_dir / "clasi-tools.diff.md").exists()

    def test_writes_human_readable_diff_for_edited_file(self, tmp_path):
        repo, sprint_design_dir = self._seeded_repo(tmp_path)
        overlay_file = sprint_design_dir / "clasi-tools.md"
        overlay_file.write_text("# Tools\n\nEdited.\n", encoding="utf-8")

        written = generate_diffs(sprint_design_dir, repo_root=repo)

        assert len(written) == 1
        diff_path = written[0]
        assert diff_path == sprint_design_dir / "clasi-tools.diff.md"
        assert diff_path.exists()

        text = diff_path.read_text(encoding="utf-8")
        assert "```diff" in text
        assert "Original." in text
        assert "Edited." in text
        # Not raw patch(1) syntax as the sole content — must be wrapped/fenced.
        assert "# Diff:" in text

    def test_diff_frontmatter_has_source_hash_matching_validator_hash(self, tmp_path):
        import hashlib

        repo, sprint_design_dir = self._seeded_repo(tmp_path)
        overlay_file = sprint_design_dir / "clasi-tools.md"
        edited_content = "# Tools\n\nEdited.\n"
        overlay_file.write_text(edited_content, encoding="utf-8")

        written = generate_diffs(sprint_design_dir, repo_root=repo)
        diff_path = written[0]

        from clasi.artifact import Artifact

        fm = Artifact(diff_path).frontmatter
        expected_hash = hashlib.sha256(edited_content.encode("utf-8")).hexdigest()
        assert fm["source_hash"] == expected_hash

    def test_idempotent_regeneration_produces_same_content(self, tmp_path):
        repo, sprint_design_dir = self._seeded_repo(tmp_path)
        overlay_file = sprint_design_dir / "clasi-tools.md"
        overlay_file.write_text("# Tools\n\nEdited.\n", encoding="utf-8")

        generate_diffs(sprint_design_dir, repo_root=repo)
        first_text = (sprint_design_dir / "clasi-tools.diff.md").read_text(
            encoding="utf-8"
        )

        generate_diffs(sprint_design_dir, repo_root=repo)
        second_text = (sprint_design_dir / "clasi-tools.diff.md").read_text(
            encoding="utf-8"
        )

        assert first_text == second_text

    def test_diff_compares_against_original_seed_not_first_edit(self, tmp_path):
        repo, sprint_design_dir = self._seeded_repo(tmp_path)
        overlay_file = sprint_design_dir / "clasi-tools.md"

        # First edit + commit (simulating a mid-sprint commit_edits call).
        overlay_file.write_text("# Tools\n\nFirst edit.\n", encoding="utf-8")
        generate_diffs(sprint_design_dir, repo_root=repo)
        commit_edits(sprint_design_dir, repo_root=repo)

        # Second edit — diff should still compare against the ORIGINAL
        # seed content ("Original."), not the first edit's content.
        overlay_file.write_text("# Tools\n\nSecond edit.\n", encoding="utf-8")
        written = generate_diffs(sprint_design_dir, repo_root=repo)

        diff_text = written[0].read_text(encoding="utf-8")
        assert "Original." in diff_text
        assert "Second edit." in diff_text


class TestCommitEdits:
    def _seeded_repo_with_unrelated_dirt(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"
        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)

        # Unrelated dirty file elsewhere in the working tree.
        unrelated = repo / "unrelated.txt"
        unrelated.write_text("dirty\n", encoding="utf-8")

        return repo, sprint_design_dir, unrelated

    def test_commits_only_design_dir_changes(self, tmp_path):
        repo, sprint_design_dir, unrelated = self._seeded_repo_with_unrelated_dirt(
            tmp_path
        )
        (sprint_design_dir / "clasi-tools.md").write_text(
            "# Tools\n\nEdited.\n", encoding="utf-8"
        )

        before_commits = _commit_count(repo)
        committed = commit_edits(sprint_design_dir, repo_root=repo)

        assert committed is True
        assert _commit_count(repo) == before_commits + 1

        # design/ dir is now clean...
        design_status = _run(
            ["status", "--porcelain", "--", str(sprint_design_dir)], repo
        )
        assert design_status.stdout.strip() == ""

        # ...but the unrelated file is still dirty (untouched).
        full_status = _run(["status", "--porcelain"], repo)
        assert "unrelated.txt" in full_status.stdout

    def test_returns_false_when_nothing_to_commit(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"
        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)

        before_commits = _commit_count(repo)
        committed = commit_edits(sprint_design_dir, repo_root=repo)

        assert committed is False
        assert _commit_count(repo) == before_commits


class TestApply:
    def test_copies_overlay_over_canonical(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"
        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)

        overlay_file = sprint_design_dir / "clasi-tools.md"
        overlay_file.write_text("# Tools\n\nFinal.\n", encoding="utf-8")

        applied = apply(sprint_design_dir, repo / "docs" / "design")

        assert applied == [canonical]
        assert canonical.read_text(encoding="utf-8") == overlay_file.read_text(
            encoding="utf-8"
        )

    def test_excludes_diff_md_files(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"
        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)

        (sprint_design_dir / "clasi-tools.md").write_text(
            "# Tools\n\nFinal.\n", encoding="utf-8"
        )
        generate_diffs(sprint_design_dir, repo_root=repo)
        assert (sprint_design_dir / "clasi-tools.diff.md").exists()

        applied = apply(sprint_design_dir, repo / "docs" / "design")

        assert applied == [canonical]
        assert not (repo / "docs" / "design" / "clasi-tools.diff.md").exists()

    def test_raises_and_does_not_partially_apply_on_unresolvable_target(
        self, tmp_path
    ):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"
        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)
        (sprint_design_dir / "clasi-tools.md").write_text(
            "# Tools\n\nFinal.\n", encoding="utf-8"
        )

        # Nonexistent canonical design dir -> target cannot be determined.
        missing_canonical_dir = repo / "docs" / "nonexistent"
        original_canonical_content = canonical.read_text(encoding="utf-8")

        with pytest.raises(OverlayApplyError):
            apply(sprint_design_dir, missing_canonical_dir)

        # Original canonical doc must be untouched (no partial apply).
        assert canonical.read_text(encoding="utf-8") == original_canonical_content


class TestFullLifecycle:
    def test_seed_diff_commit_apply_round_trip(self, tmp_path):
        repo = _init_repo(tmp_path)
        canonical = _make_canonical_doc(repo, "clasi-tools.md", "# Tools\n\nOriginal.\n")
        canonical_design_dir = repo / "docs" / "design"
        sprint_design_dir = repo / "clasi" / "sprints" / "001-x" / "design"

        seed_and_commit([canonical], sprint_design_dir, repo_root=repo)

        overlay_file = sprint_design_dir / "clasi-tools.md"
        overlay_file.write_text("# Tools\n\nUpdated during sprint.\n", encoding="utf-8")

        diffs = generate_diffs(sprint_design_dir, repo_root=repo)
        assert len(diffs) == 1

        committed = commit_edits(sprint_design_dir, repo_root=repo)
        assert committed is True

        status = _run(["status", "--porcelain"], repo)
        assert status.stdout.strip() == ""

        applied = apply(sprint_design_dir, canonical_design_dir)
        assert applied == [canonical]
        assert canonical.read_text(encoding="utf-8") == "# Tools\n\nUpdated during sprint.\n"
