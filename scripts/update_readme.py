#!/usr/bin/env python3
"""Update the 'Recently updated' block in README.md from public GitHub repos."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "Shk2005")
EXCLUDED_REPOS = {USERNAME, "ig-publish-assets"}
MAX_ITEMS = 5

START_MARKER = "<!-- recent-activity:start -->"
END_MARKER = "<!-- recent-activity:end -->"


def github_get(url: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USERNAME}-profile-updater",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_latest_commit_subject(owner: str, repo_name: str, default_branch: str) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo_name}/commits?sha={default_branch}&per_page=1"
    try:
        commits = github_get(url)
        if isinstance(commits, list) and commits:
            msg = commits[0].get("commit", {}).get("message", "")
            subject = msg.splitlines()[0].strip() if msg else ""
            if len(subject) > 64:
                trimmed = subject[:61].rsplit(" ", 1)[0].rstrip(".,;:- ")
                subject = (trimmed or subject[:61].rstrip()) + "..."
            return subject
    except urllib.error.URLError:
        pass
    return ""


def build_recent_lines() -> list[str]:
    repos_url = f"https://api.github.com/users/{USERNAME}/repos?type=owner&sort=pushed&per_page=30"
    repos = github_get(repos_url)
    if not isinstance(repos, list):
        raise RuntimeError("Unexpected GitHub API response when listing repositories.")

    lines: list[str] = []
    for repo in repos:
        name = repo.get("name", "")
        if (
            not name
            or name in EXCLUDED_REPOS
            or repo.get("private")
            or repo.get("fork")
            or repo.get("archived")
        ):
            continue

        pushed_at = (repo.get("pushed_at") or "")[:10]
        html_url = repo.get("html_url", f"https://github.com/{USERNAME}/{name}")
        default_branch = repo.get("default_branch", "main")
        subject = get_latest_commit_subject(USERNAME, name, default_branch)

        if subject:
            lines.append(f"- [{name}]({html_url}) ({pushed_at}): {subject}")
        else:
            lines.append(f"- [{name}]({html_url}) ({pushed_at})")

        if len(lines) >= MAX_ITEMS:
            break

    return lines


def update_readme(readme_path: Path) -> bool:
    original = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"({re.escape(START_MARKER)}\n)(.*?)(\n{re.escape(END_MARKER)})",
        re.DOTALL,
    )
    if not pattern.search(original):
        raise RuntimeError("Activity markers not found in README.md.")

    lines = build_recent_lines()
    if not lines:
        print("No public repositories matched filter; keeping existing README.")
        return False

    replacement = "\n".join(lines)
    updated = pattern.sub(rf"\g<1>{replacement}\g<3>", original, count=1)

    if updated == original:
        print("README.md is already up to date.")
        return False

    readme_path.write_text(updated, encoding="utf-8")
    print("Updated README.md with recent public repository activity.")
    return True


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "README.md"
    try:
        update_readme(target)
    except Exception as exc:
        print(f"Error updating README: {exc}", file=sys.stderr)
        sys.exit(1)
