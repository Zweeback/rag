#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex-Action: Archivator nach GitHub exportieren
------------------------------------------------
Funktion:
- Erstellt (falls nötig) ein GitHub-Repo
- Initialisiert Git im Quellordner
- Optional: Git LFS aktivieren & Dateitypen tracken
- Commit & Push nach 'main'

Voraussetzungen:
- Python 3.9+
- 'git' (und optional 'git-lfs') ist installiert und im PATH
- Umgebungsvariable GITHUB_TOKEN mit 'repo' (und bei Org: 'read:org') Scope
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import urllib.request
import urllib.error

GITHUB_API = "https://api.github.com"


def sh(cmd: List[str], cwd: Optional[Path] = None, check=True) -> str:
    """Run shell command and return stdout."""
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, check=False)
    if check and p.returncode != 0:
        raise RuntimeError(f"CMD failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout}")
    return p.stdout.strip()


def gh_api(path: str, token: str, method="GET", payload: Optional[dict] = None) -> dict:
    url = f"{GITHUB_API}{path}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    else:
        data = None
    try:
        with urllib.request.urlopen(req, data=data) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8")
        raise RuntimeError(f"GitHub API error {e.code} {e.reason} at {url}:\n{msg}")


def ensure_repo(owner: str, repo: str, token: str, private: bool, description: str) -> None:
    """Check if repo exists, else create it."""
    # Check
    try:
        gh_api(f"/repos/{owner}/{repo}", token, "GET")
        return
    except RuntimeError as e:
        if "404" not in str(e):
            raise
    # Create
    payload = {
        "name": repo,
        "private": private,
        "description": description,
        "auto_init": False
    }
    # Create in user space
    gh_api("/user/repos", token, "POST", payload)


def detect_owner_from_token(token: str) -> str:
    me = gh_api("/user", token, "GET")
    return me["login"]


def write_if_missing(path: Path, content: str):
    if not path.exists():
        path.write_text(content, encoding="utf-8")


DEFAULT_GITIGNORE = """# --- Archivator / General ---
.DS_Store
Thumbs.db
*.tmp
*.log
__pycache__/
*.pyc
.env
.vscode/
.idea/

# --- Build / Exports caches ---
ARCHIVATOR_SNAPSHOTS/

# (Optional) Rohdaten auslassen, wenn zu groß – sonst auskommentieren:
# ARCHIVATOR_MASTER/01_RAW/attachments/
"""

DEFAULT_GITATTR = """# Git LFS für schwere/ binäre Formate
*.zip filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
*.jpeg filter=lfs diff=lfs merge=lfs -text
*.mp4 filter=lfs diff=lfs merge=lfs -text
*.wav filter=lfs diff=lfs merge=lfs -text
*.mp3 filter=lfs diff=lfs merge=lfs -text
"""


def ensure_git_repo(src: Path, branch: str = "main"):
    if not (src / ".git").exists():
        sh(["git", "init"], cwd=src)
        # Set default branch to main (for new repos)
        try:
            sh(["git", "checkout", "-b", branch], cwd=src)
        except RuntimeError:
            # Older git: set HEAD then create branch
            sh(["git", "symbolic-ref", "HEAD", f"refs/heads/{branch}"], cwd=src)


def ensure_lfs(src: Path, enable_lfs: bool):
    if not enable_lfs:
        return
    # Install LFS and write attributes if missing
    try:
        sh(["git", "lfs", "install"], cwd=src)
    except RuntimeError:
        print("Warnung: 'git lfs' nicht gefunden. Installiere Git LFS oder nutze --no-lfs.", file=sys.stderr)
        return
    gattr = src / ".gitattributes"
    write_if_missing(gattr, DEFAULT_GITATTR)
    # Track patterns explicitly (idempotent)
    patterns = [ "*.zip", "*.pdf", "*.png", "*.jpg", "*.jpeg", "*.mp4", "*.wav", "*.mp3" ]
    for pat in patterns:
        try:
            sh(["git", "lfs", "track", pat], cwd=src, check=False)
        except Exception:
            pass


def set_remote(src: Path, owner: str, repo: str, token: str, remote_name: str = "origin"):
    # Prefer token in URL to avoid interactive auth. Token will land in .git/config.
    remote_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    # Remove existing remote if different
    remotes = sh(["git", "remote"], cwd=src, check=False).splitlines()
    if remote_name in remotes:
        # Update URL
        sh(["git", "remote", "set-url", remote_name, remote_url], cwd=src)
    else:
        sh(["git", "remote", "add", remote_name, remote_url], cwd=src)


def commit_and_push(src: Path, branch: str = "main", message: Optional[str] = None):
    # sensible defaults
    if message is None:
        timestamp = dt.datetime.now().isoformat(timespec="seconds")
        message = f"Archivator Export – {timestamp}"

    # Ensure minimal metadata
    try:
        sh(["git", "config", "user.name"], cwd=src)
    except RuntimeError:
        sh(["git", "config", "user.name", "Codex Exporter"], cwd=src)
    try:
        sh(["git", "config", "user.email"], cwd=src)
    except RuntimeError:
        sh(["git", "config", "user.email", "codex@example.local"], cwd=src)

    # Add defaults
    write_if_missing(src / ".gitignore", DEFAULT_GITIGNORE)

    # Add, commit, push
    sh(["git", "add", "-A"], cwd=src)
    # allow empty commit to initialize branch
    sh(["git", "commit", "-m", message], cwd=src, check=False)
    # Ensure branch exists
    try:
        sh(["git", "rev-parse", "--verify", branch], cwd=src)
    except RuntimeError:
        sh(["git", "checkout", "-b", branch], cwd=src)
    sh(["git", "push", "-u", "origin", branch], cwd=src)


def main():
    ap = argparse.ArgumentParser(description="Codex: Exportiere ARCHIVATOR nach GitHub")
    ap.add_argument("--source-dir", "-s", type=str, default="ARCHIVATOR_MASTER",
                    help="Quellordner (Wurzel deines Archivator-Datasets)")
    ap.add_argument("--repo", "-r", type=str, required=True,
                    help="Name des GitHub-Repos (z. B. 'archivator-export')")
    ap.add_argument("--owner", "-o", type=str, default=None,
                    help="GitHub-Owner/Org (Standard: Eigentümer gemäß Token)")
    ap.add_argument("--private", action="store_true", default=True,
                    help="Repo privat erstellen (Default: privat)")
    ap.add_argument("--public", action="store_true", default=False,
                    help="Repo öffentlich erstellen (überschreibt --private)")
    ap.add_argument("--no-lfs", action="store_true", help="Git LFS nicht verwenden")
    ap.add_argument("--branch", type=str, default="main", help="Branch-Name (Default: main)")
    ap.add_argument("--description", type=str, default="Archivator export (automated by Codex)",
                    help="Repo-Beschreibung")
    ap.add_argument("--commit-message", type=str, default=None, help="Commit-Message")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Fehler: Umgebungsvariable GITHUB_TOKEN fehlt (Scope: repo).", file=sys.stderr)
        sys.exit(1)

    src = Path(args.source_dir).resolve()
    if not src.exists():
        print(f"Fehler: Quellordner existiert nicht: {src}", file=sys.stderr)
        sys.exit(1)

    owner = args.owner or detect_owner_from_token(token)
    private = not args.public

    print(f"➡️  Owner: {owner}")
    print(f"➡️  Repo:  {args.repo} ({'private' if private else 'public'})")
    print(f"➡️  Src:   {src}")

    # 1) Repo sicherstellen
    ensure_repo(owner, args.repo, token, private, args.description)

    # 2) Git initialisieren
    ensure_git_repo(src, branch=args.branch)

    # 3) Optional: Git LFS
    ensure_lfs(src, enable_lfs=not args.no_lfs)

    # 4) Remote setzen
    set_remote(src, owner, args.repo, token)

    # 5) Commit & Push
    commit_and_push(src, branch=args.branch, message=args.commit_message)

    print(f"✅ Fertig. URL: https://github.com/{owner}/{args.repo}")


if __name__ == "__main__":
    main()
