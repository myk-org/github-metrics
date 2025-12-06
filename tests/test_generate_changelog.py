"""Tests for changelog generation script.

Tests all functions in generate_changelog.py including:
- parse_commit_line: Parsing git log lines with delimiter
- categorize_commit: Categorizing commits by conventional commit type
- format_changelog_entry: Formatting changelog entries
- execute_git_log: Executing git log command with proper error handling
- main: End-to-end changelog generation
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scripts.generate_changelog import (
    categorize_commit,
    execute_git_log,
    format_changelog_entry,
    main,
    parse_commit_line,
)


class TestParseCommitLine:
    """Tests for parse_commit_line function."""

    def test_valid_commit_line(self) -> None:
        """Test parsing valid commit line with 4 parts."""
        delimiter = "\x1f"
        line = f"feat: add new feature{delimiter}abc123{delimiter}John Doe{delimiter}2024-01-15"
        result = parse_commit_line(line, delimiter)

        assert result == {
            "title": "feat: add new feature",
            "commit": "abc123",
            "author": "John Doe",
            "date": "2024-01-15",
        }

    def test_invalid_format_too_few_parts(self, capsys: pytest.CaptureFixture) -> None:
        """Test parsing line with too few parts returns empty dict and prints warning."""
        delimiter = "\x1f"
        line = f"feat: add new feature{delimiter}abc123{delimiter}John Doe"  # Only 3 parts
        result = parse_commit_line(line, delimiter)

        assert result == {}
        captured = capsys.readouterr()
        assert "Warning: Unexpected line format:" in captured.out

    def test_invalid_format_too_many_parts(self, capsys: pytest.CaptureFixture) -> None:
        """Test parsing line with too many parts returns empty dict and prints warning."""
        delimiter = "\x1f"
        line = f"feat: add{delimiter}abc123{delimiter}John{delimiter}2024-01-15{delimiter}extra"
        result = parse_commit_line(line, delimiter)

        assert result == {}
        captured = capsys.readouterr()
        assert "Warning: Unexpected line format:" in captured.out

    def test_empty_line(self, capsys: pytest.CaptureFixture) -> None:
        """Test parsing empty line returns empty dict and prints warning."""
        result = parse_commit_line("", "\x1f")

        assert result == {}
        captured = capsys.readouterr()
        assert "Warning: Unexpected line format:" in captured.out

    def test_custom_delimiter(self) -> None:
        """Test parsing with custom delimiter."""
        delimiter = "|"
        line = "fix: bug fix|def456|Jane Smith|2024-02-20"
        result = parse_commit_line(line, delimiter)

        assert result == {
            "title": "fix: bug fix",
            "commit": "def456",
            "author": "Jane Smith",
            "date": "2024-02-20",
        }


class TestCategorizeCommit:
    """Tests for categorize_commit function."""

    def test_empty_commit_returns_default(self) -> None:
        """Test empty commit dict returns default category."""
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit({}, title_to_type_map, "Other Changes:")

        assert result == "Other Changes:"

    def test_commit_without_title_returns_default(self) -> None:
        """Test commit without title key returns default category."""
        commit = {"commit": "abc123", "author": "John Doe"}
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit(commit, title_to_type_map, "Other Changes:")

        assert result == "Other Changes:"

    def test_known_prefix_feat(self) -> None:
        """Test commit with 'feat:' prefix returns correct category."""
        commit = {"title": "feat: add new dashboard"}
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit(commit, title_to_type_map, "Other Changes:")

        assert result == "New Feature:"

    def test_known_prefix_fix(self) -> None:
        """Test commit with 'fix:' prefix returns correct category."""
        commit = {"title": "fix: resolve database connection issue"}
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit(commit, title_to_type_map, "Other Changes:")

        assert result == "Bugfixes:"

    def test_known_prefix_case_insensitive(self) -> None:
        """Test prefix matching is case-insensitive."""
        commit = {"title": "FEAT: uppercase feature"}
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit(commit, title_to_type_map, "Other Changes:")

        assert result == "New Feature:"

    def test_unknown_prefix_returns_default(self) -> None:
        """Test commit with unknown prefix returns default category."""
        commit = {"title": "unknown: some change"}
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit(commit, title_to_type_map, "Other Changes:")

        assert result == "Other Changes:"

    def test_title_without_colon_returns_default(self) -> None:
        """Test commit title without colon returns default category."""
        commit = {"title": "just a regular commit message"}
        title_to_type_map = {"feat": "New Feature:", "fix": "Bugfixes:"}
        result = categorize_commit(commit, title_to_type_map, "Other Changes:")

        assert result == "Other Changes:"

    def test_all_conventional_commit_types(self) -> None:
        """Test all conventional commit types are categorized correctly."""
        title_to_type_map = {
            "ci": "CI:",
            "docs": "Docs:",
            "feat": "New Feature:",
            "fix": "Bugfixes:",
            "refactor": "Refactor:",
            "test": "Tests:",
        }

        test_cases = [
            ("ci: update pipeline", "CI:"),
            ("docs: update README", "Docs:"),
            ("feat: new API endpoint", "New Feature:"),
            ("fix: memory leak", "Bugfixes:"),
            ("refactor: simplify code", "Refactor:"),
            ("test: add unit tests", "Tests:"),
        ]

        for title, expected_category in test_cases:
            commit = {"title": title}
            result = categorize_commit(commit, title_to_type_map, "Other Changes:")
            assert result == expected_category


class TestFormatChangelogEntry:
    """Tests for format_changelog_entry function."""

    def test_entry_with_colon_non_other_section(self) -> None:
        """Test entry with colon in non-Other section extracts part after colon."""
        change = {
            "title": "feat: add new dashboard",
            "commit": "abc123",
            "author": "John Doe",
            "date": "2024-01-15",
        }
        result = format_changelog_entry(change, "New Feature:")

        assert result == "- add new dashboard (abc123) by John Doe on 2024-01-15\n"

    def test_entry_without_colon_non_other_section(self) -> None:
        """Test entry without colon in non-Other section uses full title as fallback."""
        change = {
            "title": "some change without prefix",
            "commit": "def456",
            "author": "Jane Smith",
            "date": "2024-02-20",
        }
        result = format_changelog_entry(change, "New Feature:")

        assert result == "- some change without prefix (def456) by Jane Smith on 2024-02-20\n"

    def test_entry_in_other_section(self) -> None:
        """Test entry in Other Changes section uses full title."""
        change = {
            "title": "random commit message",
            "commit": "ghi789",
            "author": "Bob Johnson",
            "date": "2024-03-10",
        }
        result = format_changelog_entry(change, "Other Changes:")

        assert result == "- random commit message (ghi789) by Bob Johnson on 2024-03-10\n"

    def test_entry_with_multiple_colons(self) -> None:
        """Test entry with multiple colons only splits on first colon."""
        change = {
            "title": "fix: resolve issue: database connection",
            "commit": "jkl012",
            "author": "Alice Brown",
            "date": "2024-04-05",
        }
        result = format_changelog_entry(change, "Bugfixes:")

        assert result == "- resolve issue: database connection (jkl012) by Alice Brown on 2024-04-05\n"

    def test_entry_with_whitespace_after_colon(self) -> None:
        """Test entry with extra whitespace after colon is trimmed."""
        change = {
            "title": "docs:    update documentation",
            "commit": "mno345",
            "author": "Charlie Davis",
            "date": "2024-05-15",
        }
        result = format_changelog_entry(change, "Docs:")

        assert result == "- update documentation (mno345) by Charlie Davis on 2024-05-15\n"


class TestExecuteGitLog:
    """Tests for execute_git_log function."""

    def test_successful_execution_with_tags(self) -> None:
        """Test successful git log execution with valid tags."""
        mock_proc = MagicMock()
        mock_proc.stdout = "feat: feature 1\x1fabc123\x1fJohn\x1f2024-01-15\n"

        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            result = execute_git_log("v1.0.0", "v1.1.0")

            assert result == "feat: feature 1\x1fabc123\x1fJohn\x1f2024-01-15\n"
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "git"
            assert call_args[1] == "log"
            assert "v1.0.0...v1.1.0" == call_args[3]

    def test_empty_from_tag_gets_root_commit(self) -> None:
        """Test empty from_tag case gets root commit."""
        mock_root_proc = MagicMock()
        mock_root_proc.stdout = "abc123def456\n"

        mock_log_proc = MagicMock()
        mock_log_proc.stdout = "feat: initial\x1fabc123\x1fJohn\x1f2024-01-01\n"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_root_proc, mock_log_proc]
            result = execute_git_log("", "v1.0.0")

            assert result == "feat: initial\x1fabc123\x1fJohn\x1f2024-01-01\n"
            assert mock_run.call_count == 2
            # First call should be git rev-list
            first_call = mock_run.call_args_list[0][0][0]
            assert first_call[0] == "git"
            assert first_call[1] == "rev-list"

    def test_called_process_error(self, capsys: pytest.CaptureFixture) -> None:
        """Test CalledProcessError handling exits with error message."""
        error = subprocess.CalledProcessError(1, "git log", stderr="fatal: error")

        with patch("subprocess.run", side_effect=error):
            with pytest.raises(SystemExit) as exc_info:
                execute_git_log("v1.0.0", "v1.1.0")

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Error executing git log:" in captured.out

    def test_file_not_found_error(self, capsys: pytest.CaptureFixture) -> None:
        """Test FileNotFoundError when git is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            with pytest.raises(SystemExit) as exc_info:
                execute_git_log("v1.0.0", "v1.1.0")

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Error: git not found" in captured.out
            assert "Please ensure git is installed" in captured.out

    def test_empty_root_commit_uses_head(self) -> None:
        """Test when root commit is empty, falls back to HEAD."""
        mock_root_proc = MagicMock()
        mock_root_proc.stdout = "  \n"  # Empty/whitespace only

        mock_log_proc = MagicMock()
        mock_log_proc.stdout = "feat: change\x1fdef456\x1fJane\x1f2024-02-01\n"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [mock_root_proc, mock_log_proc]
            result = execute_git_log("", "v1.0.0")

            assert result == "feat: change\x1fdef456\x1fJane\x1f2024-02-01\n"
            # Second call should use HEAD as fallback
            second_call = mock_run.call_args_list[1][0][0]
            assert "HEAD" == second_call[3]


class TestMain:
    """Tests for main function (end-to-end changelog generation)."""

    def test_empty_from_tag_returns_initial_release(self) -> None:
        """Test empty from_tag returns initial release message."""
        result = main("", "v1.0.0")

        assert result == "## What's Changed\n\nInitial release\n"

    def test_single_feature_commit(self) -> None:
        """Test changelog with single feature commit."""
        git_output = "feat: add dashboard\x1fabc123\x1fJohn Doe\x1f2024-01-15"

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            result = main("v1.0.0", "v1.1.0")

            assert "## What's Changed\n" in result
            assert "#### New Feature:\n" in result
            assert "- add dashboard (abc123) by John Doe on 2024-01-15\n" in result
            assert "**Full Changelog**: https://github.com/myk-org/github-metrics/compare/v1.0.0...v1.1.0" in result

    def test_multiple_commits_different_categories(self) -> None:
        """Test changelog with commits in different categories."""
        git_output = (
            "feat: add API endpoint\x1fabc123\x1fJohn\x1f2024-01-15\n"
            "fix: resolve bug\x1fdef456\x1fJane\x1f2024-01-16\n"
            "docs: update README\x1fghi789\x1fBob\x1f2024-01-17\n"
            "random commit\x1fjkl012\x1fAlice\x1f2024-01-18"
        )

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            result = main("v1.0.0", "v1.1.0")

            assert "#### New Feature:\n" in result
            assert "- add API endpoint (abc123) by John on 2024-01-15\n" in result
            assert "#### Bugfixes:\n" in result
            assert "- resolve bug (def456) by Jane on 2024-01-16\n" in result
            assert "#### Docs:\n" in result
            assert "- update README (ghi789) by Bob on 2024-01-17\n" in result
            assert "#### Other Changes:\n" in result
            assert "- random commit (jkl012) by Alice on 2024-01-18\n" in result

    def test_multiple_commits_same_category(self) -> None:
        """Test changelog with multiple commits in same category."""
        git_output = (
            "feat: feature 1\x1fabc123\x1fJohn\x1f2024-01-15\n"
            "feat: feature 2\x1fdef456\x1fJane\x1f2024-01-16\n"
            "feat: feature 3\x1fghi789\x1fBob\x1f2024-01-17"
        )

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            result = main("v1.0.0", "v1.1.0")

            assert "#### New Feature:\n" in result
            assert "- feature 1 (abc123) by John on 2024-01-15\n" in result
            assert "- feature 2 (def456) by Jane on 2024-01-16\n" in result
            assert "- feature 3 (ghi789) by Bob on 2024-01-17\n" in result

    def test_all_commit_types(self) -> None:
        """Test changelog with all supported commit types."""
        git_output = (
            "ci: update pipeline\x1faaa111\x1fUser1\x1f2024-01-01\n"
            "docs: add docs\x1fbbb222\x1fUser2\x1f2024-01-02\n"
            "feat: new feature\x1fccc333\x1fUser3\x1f2024-01-03\n"
            "fix: bug fix\x1fddd444\x1fUser4\x1f2024-01-04\n"
            "refactor: refactor code\x1feee555\x1fUser5\x1f2024-01-05\n"
            "test: add tests\x1ffff666\x1fUser6\x1f2024-01-06\n"
            "release: new release\x1fggg777\x1fUser7\x1f2024-01-07\n"
            "cherrypicked: cherry pick\x1fhhh888\x1fUser8\x1f2024-01-08\n"
            "merge: merge branch\x1fiii999\x1fUser9\x1f2024-01-09"
        )

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            result = main("v1.0.0", "v2.0.0")

            assert "#### CI:\n" in result
            assert "#### Docs:\n" in result
            assert "#### New Feature:\n" in result
            assert "#### Bugfixes:\n" in result
            assert "#### Refactor:\n" in result
            assert "#### Tests:\n" in result
            assert "#### New Release:\n" in result
            assert "#### Cherry Pick:\n" in result
            assert "#### Merge:\n" in result

    def test_empty_git_output(self) -> None:
        """Test changelog with no commits."""
        with patch("scripts.generate_changelog.execute_git_log", return_value=""):
            result = main("v1.0.0", "v1.0.1")

            assert "## What's Changed\n" in result
            assert "**Full Changelog**: https://github.com/myk-org/github-metrics/compare/v1.0.0...v1.0.1" in result
            # No sections should appear for empty output
            assert "####" not in result

    def test_invalid_commit_lines_are_skipped(self) -> None:
        """Test that invalid commit lines are skipped gracefully."""
        git_output = (
            "feat: valid commit\x1fabc123\x1fJohn\x1f2024-01-15\n"
            "invalid line with only two parts\x1fdef456\n"
            "fix: another valid\x1fghi789\x1fJane\x1f2024-01-16"
        )

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            result = main("v1.0.0", "v1.1.0")

            # Valid commits should appear
            assert "- valid commit (abc123) by John on 2024-01-15\n" in result
            assert "- another valid (ghi789) by Jane on 2024-01-16\n" in result
            # Invalid line should be skipped
            assert "def456" not in result

    def test_custom_github_repository_env_var(self) -> None:
        """Test changelog uses GITHUB_REPOSITORY env var if set."""
        git_output = "feat: feature\x1fabc123\x1fJohn\x1f2024-01-15"

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            with patch.dict("os.environ", {"GITHUB_REPOSITORY": "custom-org/custom-repo"}):
                result = main("v1.0.0", "v1.1.0")

                assert "**Full Changelog**: https://github.com/custom-org/custom-repo/compare/v1.0.0...v1.1.0" in result

    def test_fallback_to_default_repository(self) -> None:
        """Test changelog falls back to default repository when env var not set."""
        git_output = "feat: feature\x1fabc123\x1fJohn\x1f2024-01-15"

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            with patch.dict("os.environ", {}, clear=True):
                result = main("v1.0.0", "v1.1.0")

                assert "**Full Changelog**: https://github.com/myk-org/github-metrics/compare/v1.0.0...v1.1.0" in result

    def test_unknown_category_goes_to_other_changes(self) -> None:
        """Test commits with unknown prefixes go to Other Changes section."""
        git_output = (
            "unknown: some change\x1fabc123\x1fJohn\x1f2024-01-15\n"
            "random: another change\x1fdef456\x1fJane\x1f2024-01-16"
        )

        with patch("scripts.generate_changelog.execute_git_log", return_value=git_output):
            result = main("v1.0.0", "v1.1.0")

            assert "#### Other Changes:\n" in result
            assert "- unknown: some change (abc123) by John on 2024-01-15\n" in result
            assert "- random: another change (def456) by Jane on 2024-01-16\n" in result
