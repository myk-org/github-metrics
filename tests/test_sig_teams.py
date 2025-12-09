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
