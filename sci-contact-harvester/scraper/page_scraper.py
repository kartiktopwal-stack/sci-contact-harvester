"""Web page scraping module."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


LOGGER = logging.getLogger(__name__)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PROFILE_HINTS = ("faculty", "people", "profile", "staff", "researcher", "professor")


class PageScraper:
    """Fetch and parse listing and profile pages."""

    def __init__(self) -> None:
        self.timeout = 15
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    def fetch_page(self, url: str) -> tuple[str | None, BeautifulSoup | None]:
        """Fetch a page and return both raw HTML and a parsed soup object."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            html_text = response.text
            return html_text, BeautifulSoup(html_text, "lxml")
        except Exception as exc:  # pragma: no cover - network behaviour depends on runtime
            LOGGER.warning("Failed to fetch page %s: %s", url, exc)
            return None, None

    def scrape_faculty_listing(self, listing_url: str) -> list[str]:
        """Extract likely profile URLs from a listing page."""
        _, soup = self.fetch_page(listing_url)
        if soup is None:
            return []

        urls: list[str] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            href_lower = href.lower()
            if not any(keyword in href_lower for keyword in PROFILE_HINTS):
                continue
            absolute_url = urljoin(listing_url, href)
            if absolute_url not in seen:
                seen.add(absolute_url)
                urls.append(absolute_url)
        return urls

    def scrape_profile_page(self, profile_url: str) -> tuple[BeautifulSoup | None, str]:
        """Fetch and normalize a researcher profile page."""
        _, soup = self.fetch_page(profile_url)
        if soup is None:
            return None, ""

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        full_text = soup.get_text(separator="\n", strip=True)
        return soup, full_text

    def is_valid_profile_page(self, url: str, text: str) -> bool:
        """Heuristically determine if a page is a researcher profile."""
        del url
        lowered = (text or "").lower()
        return bool(
            EMAIL_PATTERN.search(text or "")
            or "research" in lowered
            or "publications" in lowered
            or "phd" in lowered
            or "professor" in lowered
        )
