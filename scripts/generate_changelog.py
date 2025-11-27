import os
import subprocess
import sys
from collections import OrderedDict


def execute_git_log(from_tag: str, to_tag: str) -> str:
    """Executes git log and returns the output, or raises an exception on error."""
    # Use unit separator (ASCII 0x1f) as delimiter to avoid issues with commas/quotes
    delimiter = "\x1f"
    _format = f"%s{delimiter}%h{delimiter}%an{delimiter}%as"

    try:
        # Handle empty from_tag (first release)
        if not from_tag:
            # Get root commit
            root_proc = subprocess.run(
                ["git", "rev-list", "--max-parents=0", "HEAD"],
                stdout=subprocess.PIPE,
                text=True,
                check=True,
            )
            root_commit = root_proc.stdout.strip()
            git_range = root_commit if root_commit else "HEAD"
        else:
            git_range = f"{from_tag}...{to_tag}"

        # Use explicit argument list instead of shlex.split
        proc = subprocess.run(
            ["git", "log", f"--pretty=format:{_format}", git_range],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        )
        return proc.stdout
    except subprocess.CalledProcessError as ex:
        print(f"Error executing git log: {ex}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: git not found.  Please ensure git is installed and in your PATH.")
        sys.exit(1)


def parse_commit_line(line: str, delimiter: str = "\x1f") -> dict:
    """Parses a single delimiter-separated git log line."""
    try:
        parts = line.split(delimiter)
        if len(parts) != 4:
            print(f"Warning: Unexpected line format: {line}")
            return {}
        return {
            "title": parts[0],
            "commit": parts[1],
            "author": parts[2],
            "date": parts[3],
        }
    except Exception as ex:
        print(f"Error parsing line: {line} - {ex}")
        return {}


def categorize_commit(commit: dict, title_to_type_map: dict, default_category: str = "Other Changes:") -> str:
    """Categorizes a commit based on its title prefix."""
    if not commit or "title" not in commit:
        return default_category
    title = commit["title"]
    try:
        prefix = title.split(":", 1)[0].lower()  # Extract the prefix before the first colon
        return title_to_type_map.get(prefix, default_category)
    except IndexError:
        return default_category


def format_changelog_entry(change: dict, section: str) -> str:
    """Formats a single changelog entry."""
    title = change["title"].split(":", 1)[1] if section != "Other Changes:" else change["title"]
    return f"- {title} ({change['commit']}) by {change['author']} on {change['date']}\n"


def main(from_tag: str, to_tag: str) -> str:
    # Handle empty from_tag (first release)
    if not from_tag:
        return "## What's Changed\n\nInitial release\n"

    title_to_type_map: dict[str, str] = {
        "ci": "CI:",
        "docs": "Docs:",
        "feat": "New Feature:",
        "fix": "Bugfixes:",
        "refactor": "Refactor:",
        "test": "Tests:",
        "release": "New Release:",
        "cherrypicked": "Cherry Pick:",
        "merge": "Merge:",
    }
    changelog_dict: OrderedDict[str, list[dict[str, str]]] = OrderedDict([
        ("New Feature:", []),
        ("Bugfixes:", []),
        ("CI:", []),
        ("New Release:", []),
        ("Docs:", []),
        ("Refactor:", []),
        ("Tests:", []),
        ("Other Changes:", []),
        ("Cherry Pick:", []),
        ("Merge:", []),
    ])

    changelog: str = "## What's Changed\n"

    res = execute_git_log(from_tag=from_tag, to_tag=to_tag)

    for line in res.splitlines():
        commit = parse_commit_line(line=line)
        if commit:
            category = categorize_commit(commit=commit, title_to_type_map=title_to_type_map)
            # Use defensive get with fallback to "Other Changes:"
            changelog_dict.get(category, changelog_dict["Other Changes:"]).append(commit)

    for section, changes in changelog_dict.items():
        if not changes:
            continue

        changelog += f"#### {section}\n"
        for change in changes:
            changelog += format_changelog_entry(change, section)
        changelog += "\n"

    # Use GITHUB_REPOSITORY env var with fallback to myk-org/github-metrics
    repo = os.environ.get("GITHUB_REPOSITORY", "myk-org/github-metrics")
    changelog += f"**Full Changelog**: https://github.com/{repo}/compare/{from_tag}...{to_tag}"

    return changelog


if __name__ == "__main__":
    """
    Generate a changelog between two Git tags, formatted as markdown.

    This script parses Git commit logs between two specified tags and categorizes them
    by commit type (feat, fix, ci, etc.). It formats the output as a markdown document
    with sections for different types of changes, intended for use with release-it.

    Each commit is expected to follow the conventional commit format:
    <type>: <description>

    where <type> is one of: feat, fix, docs, style, refactor, test, chore, etc.
    Commits that don't follow this format are categorized under "Other Changes".

    Generate a changelog between two tags, output as markdown

    Usage: python generate_changelog.py <from_tag> <to_tag>
    Note: Use empty string "" for from_tag for first release
    """
    if len(sys.argv) != 3:
        print("Usage: python generate_changelog.py <from_tag> <to_tag>")
        print('Note: Use empty string "" for from_tag for first release')
        sys.exit(1)

    print(main(from_tag=sys.argv[1], to_tag=sys.argv[2]))
