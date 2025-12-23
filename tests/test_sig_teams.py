"""Tests for SIG teams configuration management.

Tests the SigTeamsConfig class including:
- Loading valid and invalid YAML configurations
- User team lookups
- Cross-team review detection
- Error handling for missing files and malformed YAML
"""

from pathlib import Path

import pytest
import yaml

from backend.sig_teams import SigTeamsConfig, _reset_sig_teams_config_for_testing, get_sig_teams_config


class TestSigTeamsConfig:
    """Tests for SigTeamsConfig class."""

    def test_load_valid_yaml_file(self, tmp_path: Path) -> None:
        """Test loading a valid YAML configuration file."""
        # Create test YAML file
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1", "user2"],
                "sig-storage": ["user3"],
            },
            "org/repo2": {
                "sig-compute": ["user4", "user5"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        # Load configuration
        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Verify configuration loaded successfully
        assert config.is_loaded
        assert len(config.repositories) == 2
        assert "org/repo1" in config.repositories
        assert "org/repo2" in config.repositories

    def test_load_missing_file_raises_error(self, tmp_path: Path) -> None:
        """Test FileNotFoundError is raised for missing configuration file."""
        missing_file = tmp_path / "nonexistent.yaml"

        config = SigTeamsConfig()

        with pytest.raises(FileNotFoundError, match="SIG teams configuration file not found"):
            config.load_from_file(missing_file)

    def test_load_malformed_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test yaml.YAMLError is raised for invalid YAML syntax."""
        # Create file with invalid YAML syntax
        config_file = tmp_path / "malformed.yaml"
        with config_file.open("w") as f:
            f.write('invalid:\n  - yaml\n  missing: quote"')

        config = SigTeamsConfig()

        with pytest.raises(yaml.YAMLError, match="Failed to parse YAML configuration file"):
            config.load_from_file(config_file)

    def test_get_user_team_returns_correct_team(self, tmp_path: Path) -> None:
        """Test get_user_team returns the correct team name for a known user."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1", "user2"],
                "sig-storage": ["user3"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Test lookups for known users
        assert config.get_user_team("org/repo1", "user1") == "sig-network"
        assert config.get_user_team("org/repo1", "user2") == "sig-network"
        assert config.get_user_team("org/repo1", "user3") == "sig-storage"

    def test_get_user_team_returns_none_for_unknown_user(self, tmp_path: Path) -> None:
        """Test get_user_team returns None for unknown user."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Unknown user should return None
        assert config.get_user_team("org/repo1", "unknown_user") is None

    def test_get_user_team_returns_none_for_unknown_repo(self, tmp_path: Path) -> None:
        """Test get_user_team returns None for unknown repository."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Unknown repository should return None
        assert config.get_user_team("org/unknown-repo", "user1") is None

    def test_is_cross_team_review_returns_true(self, tmp_path: Path) -> None:
        """Test is_cross_team_review returns True when teams differ."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
                "sig-storage": ["user2"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # user1 is in sig-network, PR has sig-storage label = cross-team
        assert config.is_cross_team_review("org/repo1", "user1", "sig-storage") is True

    def test_is_cross_team_review_returns_false(self, tmp_path: Path) -> None:
        """Test is_cross_team_review returns False when teams match."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
                "sig-storage": ["user2"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # user1 is in sig-network, PR has sig-network label = same team
        assert config.is_cross_team_review("org/repo1", "user1", "sig-network") is False

    def test_is_cross_team_review_returns_none_when_user_not_found(self, tmp_path: Path) -> None:
        """Test is_cross_team_review returns None when user is not in configuration."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # unknown_user is not in configuration = cannot determine
        assert config.is_cross_team_review("org/repo1", "unknown_user", "sig-network") is None

    def test_empty_config_file_is_valid(self, tmp_path: Path) -> None:
        """Test empty YAML file doesn't error and loads as empty configuration."""
        config_file = tmp_path / "empty.yaml"
        config_file.touch()  # Create empty file

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Empty file should load successfully but not be marked as loaded
        assert not config.is_loaded
        assert len(config.repositories) == 0

    def test_load_invalid_yaml_structure_root_not_dict(self, tmp_path: Path) -> None:
        """Test TypeError is raised when YAML root is not a dict."""
        # Create YAML with list at root instead of dict
        config_file = tmp_path / "invalid_root.yaml"
        with config_file.open("w") as f:
            yaml.dump(["item1", "item2"], f)

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid YAML structure: expected dict at root"):
            config.load_from_file(config_file)

    def test_load_invalid_yaml_structure_teams_not_dict(self, tmp_path: Path) -> None:
        """Test TypeError is raised when teams value is not a dict."""
        yaml_content = {
            "org/repo1": "not-a-dict",  # Should be dict of teams
        }

        config_file = tmp_path / "invalid_teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid teams structure"):
            config.load_from_file(config_file)

    def test_load_invalid_yaml_structure_users_not_list(self, tmp_path: Path) -> None:
        """Test TypeError is raised when users value is not a list."""
        yaml_content = {
            "org/repo1": {
                "sig-network": "not-a-list",  # Should be list of users
            },
        }

        config_file = tmp_path / "invalid_users.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid users list"):
            config.load_from_file(config_file)

    def test_load_duplicate_user_assignment_raises_error(self, tmp_path: Path) -> None:
        """Test ValueError is raised when a user is assigned to multiple teams."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
                "sig-storage": ["user1"],  # Duplicate assignment
            },
        }

        config_file = tmp_path / "duplicate_user.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()

        with pytest.raises(ValueError, match="Duplicate user assignment"):
            config.load_from_file(config_file)

    def test_repositories_property_returns_list(self, tmp_path: Path) -> None:
        """Test repositories property returns list of repository names."""
        yaml_content = {
            "org/repo1": {"sig-network": ["user1"]},
            "org/repo2": {"sig-storage": ["user2"]},
            "org/repo3": {"sig-compute": ["user3"]},
        }

        config_file = tmp_path / "repos.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        repos = config.repositories
        assert isinstance(repos, list)
        assert len(repos) == 3
        assert "org/repo1" in repos
        assert "org/repo2" in repos
        assert "org/repo3" in repos

    def test_is_loaded_property_before_and_after_load(self, tmp_path: Path) -> None:
        """Test is_loaded property before and after loading configuration."""
        yaml_content = {
            "org/repo1": {"sig-network": ["user1"]},
        }

        config_file = tmp_path / "teams.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()

        # Before loading
        assert not config.is_loaded

        # After loading
        config.load_from_file(config_file)
        assert config.is_loaded

    def test_multiple_repositories_with_same_users_in_different_teams(self, tmp_path: Path) -> None:
        """Test user can be in different teams across different repositories."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
            },
            "org/repo2": {
                "sig-storage": ["user1"],  # Same user, different repo, different team = OK
            },
        }

        config_file = tmp_path / "multi_repo.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Verify user is in different teams in different repos
        assert config.get_user_team("org/repo1", "user1") == "sig-network"
        assert config.get_user_team("org/repo2", "user1") == "sig-storage"

    def test_load_complex_yaml_configuration(self, tmp_path: Path) -> None:
        """Test loading a complex YAML configuration with multiple repos and teams."""
        yaml_content = {
            "kubernetes/kubernetes": {
                "sig-network": ["alice", "bob", "charlie"],
                "sig-storage": ["dave", "eve"],
                "sig-apps": ["frank"],
            },
            "kubernetes/ingress-nginx": {
                "sig-network": ["alice", "george"],
            },
            "kubernetes/csi-driver": {
                "sig-storage": ["dave", "henry"],
            },
        }

        config_file = tmp_path / "complex.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Verify all lookups work correctly
        assert config.get_user_team("kubernetes/kubernetes", "alice") == "sig-network"
        assert config.get_user_team("kubernetes/kubernetes", "dave") == "sig-storage"
        assert config.get_user_team("kubernetes/kubernetes", "frank") == "sig-apps"
        assert config.get_user_team("kubernetes/ingress-nginx", "alice") == "sig-network"
        assert config.get_user_team("kubernetes/csi-driver", "dave") == "sig-storage"

        # Verify cross-team review detection
        assert config.is_cross_team_review("kubernetes/kubernetes", "alice", "sig-storage") is True  # Different team
        assert config.is_cross_team_review("kubernetes/kubernetes", "dave", "sig-storage") is False  # Same team
        assert config.is_cross_team_review("kubernetes/kubernetes", "unknown", "sig-network") is None  # User not found

    def test_load_invalid_repository_key_type(self, tmp_path: Path) -> None:
        """Test TypeError is raised when repository key is not a string."""
        # YAML with integer as repository key
        config_file = tmp_path / "invalid_repo_key.yaml"
        with config_file.open("w") as f:
            # Write raw YAML with numeric key
            f.write("123:\n  sig-network:\n    - user1\n")

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid repository key type"):
            config.load_from_file(config_file)

    def test_load_invalid_team_name_type(self, tmp_path: Path) -> None:
        """Test TypeError is raised when team name is not a string."""
        # YAML with integer as team name
        config_file = tmp_path / "invalid_team_name.yaml"
        with config_file.open("w") as f:
            # Write raw YAML with numeric team name
            f.write("org/repo:\n  123:\n    - user1\n")

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid team name type"):
            config.load_from_file(config_file)

    def test_load_invalid_username_type(self, tmp_path: Path) -> None:
        """Test TypeError is raised when username is not a string."""
        # YAML with integer as username
        config_file = tmp_path / "invalid_username.yaml"
        with config_file.open("w") as f:
            # Write raw YAML with numeric username
            f.write("org/repo:\n  sig-network:\n    - 123\n")

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid username type"):
            config.load_from_file(config_file)

    def test_get_sig_teams_config_singleton(self) -> None:
        """Test get_sig_teams_config returns singleton instance."""
        # Reset singleton for clean test
        _reset_sig_teams_config_for_testing()

        # Get instance twice - should be same object
        config1 = get_sig_teams_config()
        config2 = get_sig_teams_config()

        assert config1 is config2

        # Reset again for clean state
        _reset_sig_teams_config_for_testing()

    def test_reset_sig_teams_config_for_testing(self) -> None:
        """Test _reset_sig_teams_config_for_testing resets singleton."""
        # Get instance
        config1 = get_sig_teams_config()

        # Reset
        _reset_sig_teams_config_for_testing()

        # Get new instance - should be different object
        config2 = get_sig_teams_config()

        assert config1 is not config2

        # Clean up
        _reset_sig_teams_config_for_testing()

    def test_get_maintainers_returns_list(self, tmp_path: Path) -> None:
        """Test get_maintainers returns correct list of maintainers."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["maintainer1", "maintainer2"],
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "maintainers.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Test get_maintainers returns correct list
        maintainers = config.get_maintainers("org/repo1")
        assert isinstance(maintainers, list)
        assert len(maintainers) == 2
        assert "maintainer1" in maintainers
        assert "maintainer2" in maintainers

    def test_get_maintainers_empty_for_no_maintainers(self, tmp_path: Path) -> None:
        """Test empty list when repository has no maintainers key."""
        yaml_content = {
            "org/repo1": {
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "no_maintainers.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Repository with no maintainers should return empty list
        maintainers = config.get_maintainers("org/repo1")
        assert isinstance(maintainers, list)
        assert len(maintainers) == 0

        # Unknown repository should also return empty list
        maintainers = config.get_maintainers("org/unknown-repo")
        assert isinstance(maintainers, list)
        assert len(maintainers) == 0

    def test_is_maintainer_returns_true(self, tmp_path: Path) -> None:
        """Test is_maintainer returns True for users in maintainers list."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["maintainer1", "maintainer2"],
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "is_maintainer.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Test is_maintainer returns True for maintainers
        assert config.is_maintainer("org/repo1", "maintainer1") is True
        assert config.is_maintainer("org/repo1", "maintainer2") is True

    def test_is_maintainer_returns_false(self, tmp_path: Path) -> None:
        """Test is_maintainer returns False for users not in maintainers list."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["maintainer1"],
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "not_maintainer.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Test is_maintainer returns False for non-maintainers
        assert config.is_maintainer("org/repo1", "user1") is False
        assert config.is_maintainer("org/repo1", "unknown_user") is False

        # Unknown repository should return False
        assert config.is_maintainer("org/unknown-repo", "maintainer1") is False

    def test_get_all_maintainers_deduplicates(self, tmp_path: Path) -> None:
        """Test get_all_maintainers returns sorted deduplicated list across all repos."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["maintainer1", "maintainer2"],
                "sig-network": ["user1"],
            },
            "org/repo2": {
                "maintainers": ["maintainer2", "maintainer3"],
                "sig-storage": ["user2"],
            },
            "org/repo3": {
                "sig-compute": ["user3"],
            },
        }

        config_file = tmp_path / "all_maintainers.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Test get_all_maintainers returns deduplicated sorted list
        all_maintainers = config.get_all_maintainers()
        assert isinstance(all_maintainers, list)
        assert len(all_maintainers) == 3
        assert all_maintainers == ["maintainer1", "maintainer2", "maintainer3"]  # Sorted

    def test_maintainers_not_added_to_team_lookup(self, tmp_path: Path) -> None:
        """Test maintainers are NOT included in user_to_team mapping."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["maintainer1", "maintainer2"],
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "maintainer_team_lookup.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Maintainers should NOT be in team lookup
        assert config.get_user_team("org/repo1", "maintainer1") is None
        assert config.get_user_team("org/repo1", "maintainer2") is None

        # Regular team member should be in team lookup
        assert config.get_user_team("org/repo1", "user1") == "sig-network"

    def test_user_can_be_both_maintainer_and_team_member(self, tmp_path: Path) -> None:
        """Test a user can be both maintainer and belong to a team."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["user1"],
                "sig-network": ["user1"],
            },
        }

        config_file = tmp_path / "dual_role.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # user1 should be both maintainer and team member
        assert config.is_maintainer("org/repo1", "user1") is True
        assert config.get_user_team("org/repo1", "user1") == "sig-network"

    def test_dual_role_user_appears_in_both_lists_independently(self, tmp_path: Path) -> None:
        """Test that a user who is both maintainer and team member appears in both lists."""
        yaml_content = {
            "org/repo1": {
                "maintainers": ["shared_user", "only_maintainer"],
                "sig-network": ["shared_user", "only_team_member"],
            },
        }

        config_file = tmp_path / "dual_role_isolation.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        config.load_from_file(config_file)

        # Verify shared_user appears in maintainers
        maintainers = config.get_maintainers("org/repo1")
        assert "shared_user" in maintainers
        assert "only_maintainer" in maintainers
        assert "only_team_member" not in maintainers

        # Verify shared_user appears in team lookup
        assert config.get_user_team("org/repo1", "shared_user") == "sig-network"
        assert config.get_user_team("org/repo1", "only_team_member") == "sig-network"
        assert config.get_user_team("org/repo1", "only_maintainer") is None

        # Verify all_maintainers includes shared_user
        all_maintainers = config.get_all_maintainers()
        assert "shared_user" in all_maintainers
        assert "only_maintainer" in all_maintainers

    def test_invalid_maintainer_username_type(self, tmp_path: Path) -> None:
        """Test TypeError for non-string username in maintainers list."""
        # YAML with integer as maintainer username
        config_file = tmp_path / "invalid_maintainer_username.yaml"
        with config_file.open("w") as f:
            # Write raw YAML with numeric maintainer username
            f.write("org/repo:\n  maintainers:\n    - 123\n")

        config = SigTeamsConfig()

        with pytest.raises(TypeError, match="Invalid username type in maintainers list"):
            config.load_from_file(config_file)

    def test_user_in_team_then_maintainers_dict_order(self, tmp_path: Path) -> None:
        """Test user can be in team first, then maintainers (dict iteration order).

        This test verifies the fix for the bug where users could not be both
        maintainers AND team members when the YAML dict is iterated with
        team appearing before maintainers.

        Regression test for:
        ValueError: Duplicate user assignment in 'RedHatQE/openshift-virtualization-tests':
        'vsibirsk' is already in team 'sig-virt', cannot also be in 'maintainers'
        """
        # YAML with team defined before maintainers to test dict iteration order
        yaml_content = {
            "RedHatQE/openshift-virtualization-tests": {
                "sig-virt": ["vsibirsk"],
                "maintainers": ["vsibirsk"],
            },
        }

        config_file = tmp_path / "team_then_maintainers.yaml"
        with config_file.open("w") as f:
            yaml.dump(yaml_content, f)

        config = SigTeamsConfig()
        # Should NOT raise ValueError about duplicate user assignment
        config.load_from_file(config_file)

        # User should be both maintainer AND team member
        assert config.is_maintainer("RedHatQE/openshift-virtualization-tests", "vsibirsk") is True
        assert config.get_user_team("RedHatQE/openshift-virtualization-tests", "vsibirsk") == "sig-virt"
