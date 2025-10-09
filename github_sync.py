"""Utility for uploading project artifacts to GitHub via the REST API.

This script is optional. It reads a GitHub token from the environment
and can upload one or more files (or all files within a directory) to a
remote repository. The intent is to provide a reproducible alternative
instead of pasting sensitive credentials into prompts.
"""

from __future__ import annotations

import argparse
import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import requests


GITHUB_API = "https://api.github.com"
TOKEN_ENV_VAR = "GITHUB_TOKEN"


@dataclass
class GitHubTarget:
    owner: str
    repo: str
    branch: str = "main"

    @property
    def base_url(self) -> str:
        return f"{GITHUB_API}/repos/{self.owner}/{self.repo}/contents"


def _read_token() -> str:
    token = os.getenv(TOKEN_ENV_VAR)
    if not token:
        raise RuntimeError(
            f"Environment variable {TOKEN_ENV_VAR} must be set with a GitHub Personal Access Token"
        )
    return token


def _gather_paths(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for candidate in sorted(path.rglob("*")):
        if candidate.is_file():
            yield candidate


def _relativize(path: Path, base: Path) -> str:
    rel = path.relative_to(base)
    return rel.as_posix()


def _get_sha(target: GitHubTarget, token: str, remote_path: str) -> Optional[str]:
    url = f"{target.base_url}/{remote_path}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        params={"ref": target.branch},
        timeout=30,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return payload.get("sha")
    return None


def _put_file(
    target: GitHubTarget,
    token: str,
    remote_path: str,
    content: bytes,
    message: str,
    sha: Optional[str],
) -> None:
    url = f"{target.base_url}/{remote_path}"
    encoded = base64.b64encode(content).decode("ascii")
    payload = {
        "message": message,
        "content": encoded,
        "branch": target.branch,
    }
    if sha:
        payload["sha"] = sha
    response = requests.put(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()


def upload(
    target: GitHubTarget,
    local: Path,
    remote_base: str,
    message: str,
) -> None:
    token = _read_token()
    base = local if local.is_dir() else local.parent
    paths = list(_gather_paths(local))
    if not paths:
        raise RuntimeError(f"No files found under {local}")

    for path in paths:
        remote_path = f"{remote_base}/{_relativize(path, base)}" if remote_base else _relativize(path, base)
        sha = _get_sha(target, token, remote_path)
        _put_file(target, token, remote_path, path.read_bytes(), message, sha)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload files to a GitHub repository via the contents API.")
    parser.add_argument("repository", help="Target repository in the form owner/name")
    parser.add_argument("path", help="File or directory to upload")
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch to update (default: main)",
    )
    parser.add_argument(
        "--remote-base",
        default="",
        help="Remote directory prefix (e.g., 'artifacts'). Defaults to repository root.",
    )
    parser.add_argument(
        "--message",
        default="Upload artifacts",
        help="Commit message to use for the upload",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    owner, repo = args.repository.split("/", maxsplit=1)
    target = GitHubTarget(owner=owner, repo=repo, branch=args.branch)
    upload(target, Path(args.path).resolve(), args.remote_base.strip("/"), args.message)


if __name__ == "__main__":
    main()
