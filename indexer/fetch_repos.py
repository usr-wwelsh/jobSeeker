"""
Fetch all public repos for a GitHub user from the GitHub API.
Returns list of {name, clone_url, default_branch}.

Configure via GITHUB_USERNAME in .env (required) and GITHUB_TOKEN (optional).
"""
import os
import requests

from dotenv import load_dotenv
load_dotenv()

GITHUB_API = "https://api.github.com"


def fetch_repos() -> list[dict]:
    GITHUB_USER = os.environ.get("GITHUB_USERNAME", "").strip()
    if not GITHUB_USER:
        raise RuntimeError("GITHUB_USERNAME is not set. Add it to your .env file.")
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API}/users/{GITHUB_USER}/repos"
        resp = requests.get(
            url,
            headers=headers,
            params={"per_page": 100, "type": "public", "page": page},
            timeout=30,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            repos.append(
                {
                    "name": r["name"],
                    "clone_url": r["clone_url"],
                    "default_branch": r.get("default_branch", "main"),
                }
            )
        if len(batch) < 100:
            break
        page += 1

    print(f"Found {len(repos)} public repos for {GITHUB_USER}.")
    return repos


if __name__ == "__main__":
    for r in fetch_repos():
        print(r["name"], r["clone_url"])
