"""GitHub push and sync module."""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from github import Github
from github.GithubException import GithubException


LOGGER = logging.getLogger(__name__)


class GitHubSyncer:
    """Push exports and run metadata back to a GitHub repository."""

    def __init__(self, token: str, repo_name: str, branch: str) -> None:
        self.token = token
        self.repo_name = repo_name
        self.branch = branch or "main"
        self.client: Github | None = None
        self.repo = None

        if not token or not repo_name:
            LOGGER.warning("GitHub sync disabled because token or repo name is missing.")
            return

        try:
            self.client = Github(token)
            self.repo = self.client.get_repo(repo_name)
        except Exception as exc:  # pragma: no cover - network/auth depends on runtime
            LOGGER.error("Failed to initialize GitHub sync for %s: %s", repo_name, exc)
            self.repo = None

    def push_csv(self, local_csv_path: str, github_path: str) -> str | None:
        """Push a CSV export to GitHub and return the resulting commit SHA."""
        csv_path = Path(local_csv_path)
        if not csv_path.exists():
            LOGGER.error("CSV export %s does not exist; nothing to push.", csv_path)
            return None

        content = csv_path.read_text(encoding="utf-8")
        row_count = sum(1 for _ in csv.DictReader(content.splitlines()))
        timestamp = self._timestamp()
        message = f"Auto-update: {timestamp} | {row_count} contacts"
        return self._upsert_file(github_path, content, message)

    def push_json_summary(self, contact_list: list[dict[str, Any]]) -> str | None:
        """Push a compact JSON summary of harvested contacts."""
        summary = [
            {
                "name": contact.get("full_name"),
                "email": contact.get("email"),
                "institution": contact.get("institution"),
                "domain": contact.get("scientific_domain"),
            }
            for contact in contact_list
        ]
        timestamp = self._timestamp()
        content = json.dumps(summary, indent=2, ensure_ascii=True)
        return self._upsert_file(
            "exports/summary.json",
            content + "\n",
            f"Auto-update: summary {timestamp}",
        )

    def log_run(self, stats_dict: dict[str, Any]) -> str | None:
        """Append run statistics to the GitHub-hosted run history log."""
        history_path = "logs/run_history.json"
        existing_history: list[dict[str, Any]] = []
        if self.repo is not None:
            try:
                contents = self.repo.get_contents(history_path, ref=self.branch)
                if not isinstance(contents, list):
                    decoded = contents.decoded_content.decode("utf-8")
                    loaded = json.loads(decoded)
                    if isinstance(loaded, list):
                        existing_history = loaded
            except GithubException as exc:
                if exc.status != 404:
                    LOGGER.error("Failed to read existing run history from GitHub: %s", exc)
            except Exception as exc:  # pragma: no cover - depends on GitHub response
                LOGGER.error("Unexpected error while reading run history: %s", exc)

        existing_history.append(stats_dict)
        content = json.dumps(existing_history, indent=2, ensure_ascii=True) + "\n"
        return self._upsert_file(history_path, content, f"Auto-update: run log {self._timestamp()}")

    def get_last_run_stats(self) -> dict[str, Any] | None:
        """Return the most recent run stats entry from GitHub, if available."""
        if self.repo is None:
            return None

        try:
            contents = self.repo.get_contents("logs/run_history.json", ref=self.branch)
            if isinstance(contents, list):
                return None
            payload = json.loads(contents.decoded_content.decode("utf-8"))
            return payload[-1] if isinstance(payload, list) and payload else None
        except GithubException as exc:
            if exc.status != 404:
                LOGGER.error("Failed to fetch run history from GitHub: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - external API behaviour depends on runtime
            LOGGER.error("Unexpected error while loading last run stats: %s", exc)
            return None

    def _upsert_file(self, github_path: str, content: str, message: str) -> str | None:
        if self.repo is None:
            LOGGER.warning("GitHub repo is unavailable; skipping push for %s.", github_path)
            return None

        try:
            existing = self.repo.get_contents(github_path, ref=self.branch)
            if isinstance(existing, list):
                LOGGER.error("%s points to a directory in GitHub; expected a file.", github_path)
                return None
            result = self.repo.update_file(
                path=github_path,
                message=message,
                content=content,
                sha=existing.sha,
                branch=self.branch,
            )
        except GithubException as exc:
            if exc.status != 404:
                LOGGER.error("GitHub update failed for %s: %s", github_path, exc)
                return None
            try:
                result = self.repo.create_file(
                    path=github_path,
                    message=message,
                    content=content,
                    branch=self.branch,
                )
            except Exception as create_exc:  # pragma: no cover - external API behaviour depends on runtime
                LOGGER.error("GitHub create failed for %s: %s", github_path, create_exc)
                return None
        except Exception as exc:  # pragma: no cover - external API behaviour depends on runtime
            LOGGER.error("Unexpected GitHub sync error for %s: %s", github_path, exc)
            return None

        commit = result.get("commit")
        return getattr(commit, "sha", None)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
