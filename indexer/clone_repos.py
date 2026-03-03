"""
Clone or pull all repos returned by fetch_repos into data/repos/.
Never deletes existing repos — safe to re-run.
"""
import os
from pathlib import Path

from git import Repo, InvalidGitRepositoryError, GitCommandError

from indexer.fetch_repos import fetch_repos

REPOS_DIR = Path(__file__).resolve().parent.parent / "data" / "repos"


def clone_or_pull(repo_info: dict) -> Path:
    name = repo_info["name"]
    clone_url = repo_info["clone_url"]
    dest = REPOS_DIR / name

    if dest.exists():
        try:
            r = Repo(dest)
            print(f"Pulling {name}...")
            r.remotes.origin.pull()
        except InvalidGitRepositoryError:
            print(f"WARNING: {dest} exists but has a corrupt .git — skipping.")
        except GitCommandError as e:
            print(f"WARNING: git pull failed for {name}: {e}")
    else:
        print(f"Cloning {name}...")
        try:
            Repo.clone_from(clone_url, dest)
        except GitCommandError as e:
            print(f"WARNING: git clone failed for {name}: {e}")

    return dest


def clone_all() -> list[Path]:
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    repos = fetch_repos()
    paths = []
    for repo_info in repos:
        path = clone_or_pull(repo_info)
        paths.append(path)
    return paths


if __name__ == "__main__":
    clone_all()
