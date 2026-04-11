"""Search engine integration module."""

from __future__ import annotations

import logging
from typing import Any

try:
    from serpapi import GoogleSearch
except ImportError:  # pragma: no cover - depends on installed serpapi variant
    from serpapi.google_search import GoogleSearch  # type: ignore[no-redef]


LOGGER = logging.getLogger(__name__)


class AcademicSearchEngine:
    """Search for researcher listings and profile pages via SerpAPI."""

    RESEARCH_FIELDS = [
        "Physics",
        "Computer Science",
        "Biology",
        "Chemistry",
        "Mathematics",
        "Neuroscience",
        "Engineering",
        "Environmental Science",
    ]

    def __init__(self, serpapi_key: str) -> None:
        self.serpapi_key = serpapi_key

    def search_query(self, query: str) -> list[str]:
        """Execute a raw SerpAPI query and return result URLs."""
        if not self.serpapi_key:
            LOGGER.warning("SERPAPI_KEY is not configured; skipping query: %s", query)
            return []

        try:
            search = GoogleSearch(
                {
                    "engine": "google",
                    "q": query,
                    "api_key": self.serpapi_key,
                    "num": 10,
                }
            )
            response: dict[str, Any] = search.get_dict()
            organic_results = response.get("organic_results", [])
            urls: list[str] = []
            seen: set[str] = set()
            for result in organic_results:
                link = result.get("link")
                if link and link not in seen:
                    seen.add(link)
                    urls.append(link)
            return urls
        except Exception as exc:  # pragma: no cover - external API behaviour depends on runtime
            LOGGER.error("SerpAPI query failed for %r: %s", query, exc)
            return []

    def search_university_faculty_pages(self, university_name: str) -> list[str]:
        query = f'"{university_name}" faculty professors site:edu email'
        return self.search_query(query)

    def search_by_research_field(self, field: str) -> list[str]:
        query = f'"department of {field}" professor email contact site:edu'
        return self.search_query(query)

    def search_researcher_profiles(self, keywords: str) -> list[str]:
        query = f'"{keywords}" researcher professor email -linkedin'
        return self.search_query(query)

    def get_seed_university_list(self) -> list[str]:
        return [
            "MIT",
            "Stanford",
            "Harvard",
            "Oxford",
            "Cambridge",
            "ETH Zurich",
            "Caltech",
            "Princeton",
            "Yale",
            "Columbia",
            "UCL",
            "Imperial College London",
            "University of Tokyo",
            "NUS",
            "IIT Delhi",
            "EPFL",
            "TU Munich",
            "University of Toronto",
            "McGill",
            "ANU",
        ]

    def build_search_queries(self) -> list[str]:
        queries = [
            f'"{university}" faculty professors site:edu email'
            for university in self.get_seed_university_list()
        ]
        queries.extend(
            f'"department of {field}" professor email contact site:edu'
            for field in self.RESEARCH_FIELDS
        )
        return queries
