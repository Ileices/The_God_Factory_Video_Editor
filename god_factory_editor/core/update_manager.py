"""
Git-backed updater for source checkouts.

Safe behavior:
- Never pulls over local modifications.
- Uses fast-forward only.
- Manual clone can create a fresh checkout elsewhere.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Tuple

from god_factory_editor.config import APP_DIR, settings


class UpdateManager:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = Path(repo_root or APP_DIR)

    def git_available(self) -> bool:
        return shutil.which("git") is not None

    def is_git_repo(self) -> bool:
        return (self.repo_root / ".git").exists()

    def current_branch(self) -> str:
        ok, out = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return out.strip() if ok and out.strip() else "main"

    def has_remote(self, name: str = "origin") -> bool:
        ok, out = self._run_git(["remote"])
        return ok and name in {line.strip() for line in out.splitlines() if line.strip()}

    def remote_status(self) -> Tuple[bool, str]:
        """
        Return user-facing status like:
        - up to date
        - behind by N commits
        - ahead/diverged
        """
        if not self.git_available():
            return False, "Git is not installed or not on PATH."
        if not self.is_git_repo():
            return False, "This app folder is not a Git checkout."
        ok, msg = self.ensure_origin()
        if not ok:
            return False, msg

        branch = self.current_branch()
        ok, err = self._run_git(["fetch", "origin", branch])
        if not ok:
            return False, err.strip() or "Failed to fetch remote branch status."

        ok, out = self._run_git(["rev-list", "--left-right", "--count", f"origin/{branch}...{branch}"])
        if not ok:
            return False, out.strip() or "Could not compare local and remote history."
        parts = (out or "").strip().split()
        if len(parts) != 2:
            return False, "Unexpected Git status output while checking updates."
        behind = int(parts[0])
        ahead = int(parts[1])

        if behind == 0 and ahead == 0:
            return True, "Up to date with origin."
        if behind > 0 and ahead == 0:
            return True, f"Update available: behind origin/{branch} by {behind} commit(s)."
        if behind == 0 and ahead > 0:
            return True, f"Local branch is ahead of origin by {ahead} commit(s)."
        return True, f"Local and origin have diverged (behind {behind}, ahead {ahead})."

    def ensure_origin(self) -> Tuple[bool, str]:
        repo_url = settings.get("repo_url", "").strip()
        if not repo_url:
            return False, "Repository URL is empty."
        if not self.git_available():
            return False, "Git is not installed or not on PATH."
        if not self.is_git_repo():
            return False, "Current app folder is not a Git checkout."
        if self.has_remote("origin"):
            return True, "Origin remote already configured."
        ok, err = self._run_git(["remote", "add", "origin", repo_url])
        return (ok, "Origin remote added." if ok else err.strip() or "Failed to add origin remote.")

    def working_tree_clean(self) -> Tuple[bool, str]:
        ok, out = self._run_git(["status", "--porcelain"])
        if not ok:
            return False, "Could not read Git working tree state."
        dirty = [line for line in out.splitlines() if line.strip()]
        if dirty:
            return False, "Local changes detected. Commit or stash them before updating."
        return True, "Working tree clean."

    def pull_latest(self) -> Tuple[bool, str]:
        if not self.git_available():
            return False, "Git is not installed or not on PATH."
        if not self.is_git_repo():
            return False, "Current app folder is not a Git checkout. Manual clone is available instead."
        ok, msg = self.ensure_origin()
        if not ok:
            return False, msg
        clean, clean_msg = self.working_tree_clean()
        if not clean:
            return False, clean_msg

        branch = self.current_branch()
        ok, err = self._run_git(["fetch", "origin", branch])
        if not ok:
            return False, err.strip() or "Git fetch failed."
        ok, err = self._run_git(["pull", "--ff-only", "origin", branch], timeout=120)
        if not ok:
            return False, err.strip() or "Git pull failed."
        return True, f"Updated from origin/{branch}. Restart the app to pick up code changes."

    def clone_latest(self, target_parent: Path) -> Tuple[bool, str]:
        repo_url = settings.get("repo_url", "").strip()
        if not repo_url:
            return False, "Repository URL is empty."
        if not self.git_available():
            return False, "Git is not installed or not on PATH."

        target_parent = Path(target_parent)
        target_parent.mkdir(parents=True, exist_ok=True)
        target_dir = target_parent / "The_God_Factory_Video_Editor"
        if target_dir.exists():
            return False, f"Target folder already exists: {target_dir}"

        ok, err = self._run_git(["clone", repo_url, str(target_dir)], cwd=target_parent, timeout=300)
        return (ok, f"Cloned latest source to {target_dir}" if ok else err.strip() or "Git clone failed.")

    def _run_git(self, args: list[str], cwd: Path | None = None, timeout: int = 30) -> Tuple[bool, str]:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=str(cwd or self.repo_root),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)
        if proc.returncode == 0:
            return True, (proc.stdout or proc.stderr or "").strip()
        return False, (proc.stderr or proc.stdout or "").strip()
