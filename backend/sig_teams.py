"""
SIG (Special Interest Group) team configuration management.

Handles loading and querying of team membership configurations from YAML files.
Used for tracking cross-team code review metrics.

YAML file structure:
    org/repo:
      sig-team-name:
        - username1
        - username2
      another-sig:
        - username3

Example:
    config = SigTeamsConfig()
    config.load_from_file(Path("teams.yaml"))
    team = config.get_user_team("myk-org/github-metrics", "user1")  # Returns "sig-team-name"
    is_cross = config.is_cross_team_review("myk-org/github-metrics", "user3", "sig-team-name")  # Returns True
"""

from pathlib import Path

import yaml
from simple_logger.logger import get_logger

LOGGER = get_logger(name="backend.sig_teams")


class SigTeamsConfig:
    """
    Manages SIG team configuration loaded from YAML files.

    Provides O(1) lookups for team membership and cross-team review detection.

    Architecture guarantees:
    - _user_to_team starts as empty dict (no config loaded yet) - defensive check acceptable
    - After load_from_file(), _user_to_team is populated - no defensive checks needed
    - File validation happens at load time (fail-fast) - runtime methods assume valid data
    """

    def __init__(self) -> None:
        """Initialize empty SIG teams configuration."""
        # Internal lookup structure: {repository: {username: team_name}}
        # Example: {"myk-org/repo": {"user1": "sig-network", "user2": "sig-storage"}}
        self._user_to_team: dict[str, dict[str, str]] = {}

    def load_from_file(self, path: Path) -> None:
        """
        Load SIG team configuration from YAML file.

        Expected YAML structure:
            org/repo:
              sig-team-name:
                - username1
                - username2
              another-sig:
                - username3

        Args:
            path: Path to YAML configuration file

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            TypeError: If YAML structure has invalid types
            ValueError: If YAML structure has invalid values (e.g., duplicate users)

        Example:
            config = SigTeamsConfig()
            config.load_from_file(Path("teams.yaml"))
        """
        LOGGER.info("Loading SIG teams configuration from: %s", path)

        if not path.exists():
            msg = f"SIG teams configuration file not found: {path}"
            LOGGER.error(msg)
            raise FileNotFoundError(msg)

        try:
            with path.open("r") as f:
                raw_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            msg = f"Failed to parse YAML configuration file: {path}"
            LOGGER.exception(msg)
            raise yaml.YAMLError(msg) from e

        # Empty file is valid - just means no team tracking
        if raw_config is None:
            LOGGER.warning("SIG teams configuration file is empty - no team tracking enabled")
            self._user_to_team = {}
            return

        # Validate structure and build internal lookup dict
        if not isinstance(raw_config, dict):
            msg = f"Invalid YAML structure: expected dict at root, got {type(raw_config).__name__}"
            LOGGER.error(msg)
            raise TypeError(msg)

        self._user_to_team = self._build_lookup_dict(raw_config)
        repo_count = len(self._user_to_team)
        mapping_count = sum(len(users) for users in self._user_to_team.values())
        LOGGER.info(
            "Successfully loaded SIG teams configuration: %s repositories, %s total user-team mappings",
            repo_count,
            mapping_count,
        )

    def _build_lookup_dict(self, raw_config: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, str]]:
        """
        Build internal lookup dictionary from raw YAML configuration.

        Transforms:
            {"org/repo": {"sig-network": ["user1", "user2"], "sig-storage": ["user3"]}}
        Into:
            {"org/repo": {"user1": "sig-network", "user2": "sig-network", "user3": "sig-storage"}}

        Args:
            raw_config: Raw YAML configuration loaded from file

        Returns:
            Lookup dictionary mapping repository -> username -> team_name

        Raises:
            TypeError: If configuration structure has invalid types
            ValueError: If configuration structure has invalid values (e.g., duplicate users)
        """
        lookup: dict[str, dict[str, str]] = {}

        for repository, teams in raw_config.items():
            if not isinstance(repository, str):
                msg = f"Invalid repository key type: expected str, got {type(repository).__name__}"
                LOGGER.error(msg)
                raise TypeError(msg)

            if not isinstance(teams, dict):
                msg = (
                    f"Invalid teams structure for repository '{repository}': expected dict, got {type(teams).__name__}"
                )
                LOGGER.error(msg)
                raise TypeError(msg)

            # Build user->team mapping for this repository
            repo_lookup: dict[str, str] = {}

            for team_name, users in teams.items():
                if not isinstance(team_name, str):
                    msg = f"Invalid team name type in '{repository}': expected str, got {type(team_name).__name__}"
                    LOGGER.error(msg)
                    raise TypeError(msg)

                if not isinstance(users, list):
                    msg = (
                        f"Invalid users list for team '{team_name}' in '{repository}': "
                        f"expected list, got {type(users).__name__}"
                    )
                    LOGGER.error(msg)
                    raise TypeError(msg)

                for user in users:
                    if not isinstance(user, str):
                        msg = (
                            f"Invalid username type in team '{team_name}' in '{repository}': "
                            f"expected str, got {type(user).__name__}"
                        )
                        LOGGER.error(msg)
                        raise TypeError(msg)

                    # Check for duplicate user assignments
                    if user in repo_lookup:
                        msg = (
                            f"Duplicate user assignment in '{repository}': "
                            f"'{user}' is already in team '{repo_lookup[user]}', "
                            f"cannot also be in '{team_name}'"
                        )
                        LOGGER.error(msg)
                        raise ValueError(msg)

                    repo_lookup[user] = team_name

            lookup[repository] = repo_lookup

        return lookup

    def get_user_team(self, repository: str, username: str) -> str | None:
        """
        Get the SIG team name for a user in a specific repository.

        Args:
            repository: Repository in "org/repo" format
            username: GitHub username

        Returns:
            Team name (e.g., "sig-network") if user is in a team, None otherwise

        Example:
            team = config.get_user_team("myk-org/github-metrics", "user1")
            # Returns "sig-network" if user1 is in sig-network team, None if not configured
        """
        repo_users = self._user_to_team.get(repository, {})
        return repo_users.get(username)

    def is_cross_team_review(self, repository: str, reviewer: str, pr_sig_label: str) -> bool | None:
        """
        Determine if a code review is cross-team (reviewer's team differs from PR's SIG label).

        Args:
            repository: Repository in "org/repo" format
            reviewer: GitHub username of the reviewer
            pr_sig_label: SIG label on the PR (e.g., "sig-network")

        Returns:
            True if reviewer's team differs from PR's SIG label (cross-team review)
            False if reviewer's team matches PR's SIG label (same-team review)
            None if reviewer's team cannot be determined (user not in configuration)

        Example:
            # Reviewer "user1" is in sig-network, PR has sig-storage label
            is_cross = config.is_cross_team_review("myk-org/repo", "user1", "sig-storage")
            # Returns True (cross-team review)

            # Reviewer "user2" is in sig-network, PR has sig-network label
            is_cross = config.is_cross_team_review("myk-org/repo", "user2", "sig-network")
            # Returns False (same-team review)

            # Reviewer "unknown" is not in configuration
            is_cross = config.is_cross_team_review("myk-org/repo", "unknown", "sig-network")
            # Returns None (cannot determine)
        """
        reviewer_team = self.get_user_team(repository, reviewer)

        if reviewer_team is None:
            # Cannot determine - reviewer not in configuration
            return None

        # Compare reviewer's team with PR's SIG label
        return reviewer_team != pr_sig_label

    @property
    def repositories(self) -> list[str]:
        """
        Get list of all configured repositories.

        Returns:
            List of repository names in "org/repo" format

        Example:
            repos = config.repositories
            # Returns ["myk-org/github-metrics", "another-org/repo"]
        """
        return list(self._user_to_team.keys())

    @property
    def is_loaded(self) -> bool:
        """
        Check if configuration has been loaded from a file.

        Returns:
            True if load_from_file() has been called and at least one repository is configured,
            False otherwise

        Note:
            An empty configuration file (or a file containing an empty dict) will result in
            is_loaded returning False. This property checks whether any repositories are
            configured, not just whether load_from_file() was called.

        Example:
            config = SigTeamsConfig()
            assert not config.is_loaded
            config.load_from_file(Path("teams.yaml"))  # Non-empty file
            assert config.is_loaded

            config2 = SigTeamsConfig()
            config2.load_from_file(Path("empty.yaml"))  # Empty file
            assert not config2.is_loaded  # Empty config considered "not loaded"
        """
        return bool(self._user_to_team)


# Singleton instance for global access
_sig_teams_config: SigTeamsConfig | None = None


def get_sig_teams_config() -> SigTeamsConfig:
    """
    Get or create the global SIG teams configuration instance.

    Returns:
        Global SigTeamsConfig instance

    Note:
        Configuration must be loaded via load_from_file() before use.
        This function only creates the instance - it doesn't load any data.

    Example:
        config = get_sig_teams_config()
        if not config.is_loaded:
            config.load_from_file(Path("teams.yaml"))
    """
    global _sig_teams_config
    if _sig_teams_config is None:
        _sig_teams_config = SigTeamsConfig()
    return _sig_teams_config


def _reset_sig_teams_config_for_testing() -> None:
    """Reset singleton instance for testing purposes only."""
    global _sig_teams_config
    _sig_teams_config = None
