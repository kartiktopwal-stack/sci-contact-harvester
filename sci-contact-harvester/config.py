"""Configuration loader for sci-contact-harvester."""

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

# Load environment variables from the project-local .env file if present.
load_dotenv(ENV_FILE)


def _get_str(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value if value is not None else default


def _get_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default

    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float.") from exc


GITHUB_TOKEN: str = _get_str("GITHUB_TOKEN")
GITHUB_REPO_NAME: str = _get_str("GITHUB_REPO_NAME")
GITHUB_BRANCH: str = _get_str("GITHUB_BRANCH", "main")
SERPAPI_KEY: str = _get_str("SERPAPI_KEY")
ANTHROPIC_API_KEY: str = _get_str("ANTHROPIC_API_KEY")
DB_PATH: str = _get_str("DB_PATH", "sci_contacts.db")
SCRAPE_DELAY: float = _get_float("SCRAPE_DELAY", 2.0)


__all__ = [
    "GITHUB_TOKEN",
    "GITHUB_REPO_NAME",
    "GITHUB_BRANCH",
    "SERPAPI_KEY",
    "ANTHROPIC_API_KEY",
    "DB_PATH",
    "SCRAPE_DELAY",
]
