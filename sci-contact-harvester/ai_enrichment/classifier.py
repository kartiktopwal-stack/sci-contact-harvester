"""AI classification module."""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from anthropic import Anthropic


LOGGER = logging.getLogger(__name__)
MODEL_NAME = "claude-haiku-4-5-20251001"
DOMAIN_CHOICES = [
    "Physics",
    "Chemistry",
    "Biology",
    "Computer Science",
    "Mathematics",
    "Engineering",
    "Medicine",
    "Environmental Science",
    "Social Science",
    "Economics",
    "Neuroscience",
    "Materials Science",
    "Other",
]


class AIEnricher:
    """Enrich researcher contacts using Anthropic's Claude API."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client: Anthropic | None = Anthropic(api_key=api_key) if api_key else None
        if self.client is None:
            LOGGER.warning("Anthropic enrichment disabled because ANTHROPIC_API_KEY is not set.")

    def classify_domain(
        self,
        name: str | None,
        institution: str | None,
        research_interests: str | None,
        page_text_snippet: str,
    ) -> str:
        """Classify the researcher's primary scientific domain."""
        prompt = (
            "Given this researcher's information, classify their primary scientific domain into ONE of: "
            "Physics, Chemistry, Biology, Computer Science, Mathematics, Engineering, Medicine, "
            "Environmental Science, Social Science, Economics, Neuroscience, Materials Science, Other.\n"
            f"Researcher: {name}, Institution: {institution}, Research interests: {research_interests}\n"
            "Respond with ONLY the domain name, nothing else."
        )

        response_text = self._call_claude(prompt, max_tokens=32)
        if not response_text:
            return self._fallback_domain(research_interests, page_text_snippet)

        normalized = response_text.strip()
        for domain in DOMAIN_CHOICES:
            if normalized.lower() == domain.lower():
                return domain
        return self._fallback_domain(research_interests, page_text_snippet)

    def extract_keywords(self, page_text_snippet: str) -> str:
        """Extract a compact list of research keywords from page content."""
        snippet = page_text_snippet[:500]
        prompt = (
            "Extract 5 research keywords from this text. Respond with ONLY a comma-separated list, "
            f"nothing else: {snippet}"
        )
        response_text = self._call_claude(prompt, max_tokens=64)
        return response_text.strip() if response_text else self._fallback_keywords(snippet)

    def enrich_contact(self, contact_dict: dict[str, Any], page_text_snippet: str) -> dict[str, Any]:
        """Return an enriched contact dictionary."""
        enriched = dict(contact_dict)
        enriched["scientific_domain"] = self.classify_domain(
            enriched.get("full_name"),
            enriched.get("institution"),
            enriched.get("research_interests"),
            page_text_snippet,
        )

        keywords = self.extract_keywords(page_text_snippet)
        if keywords:
            existing = enriched.get("research_interests")
            enriched["research_interests"] = existing or keywords

        return enriched

    def _call_claude(self, prompt: str, max_tokens: int) -> str | None:
        if self.client is None:
            return None

        try:
            response = self.client.messages.create(
                model=MODEL_NAME,
                max_tokens=max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._extract_text(response)
        except Exception as exc:  # pragma: no cover - external API behaviour depends on runtime
            LOGGER.error("Anthropic API call failed: %s", exc)
            return None

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts: list[str] = []
        for block in getattr(response, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    def _fallback_domain(self, research_interests: str | None, page_text_snippet: str) -> str:
        haystack = " ".join(part for part in (research_interests, page_text_snippet) if part).lower()
        fallback_map = {
            "Computer Science": ("machine learning", "computer", "software", "ai"),
            "Physics": ("physics", "quantum", "particle"),
            "Biology": ("biology", "genetics", "cell", "organism"),
            "Chemistry": ("chemistry", "chemical", "molecule"),
            "Mathematics": ("mathematics", "algebra", "geometry"),
            "Engineering": ("engineering", "robotics", "mechanical", "electrical"),
            "Medicine": ("medicine", "clinical", "patient", "medical"),
            "Environmental Science": ("climate", "environment", "ecology", "sustainability"),
            "Neuroscience": ("brain", "neural", "neuroscience"),
            "Materials Science": ("materials", "polymer", "nanomaterial"),
            "Economics": ("economics", "finance", "market"),
            "Social Science": ("sociology", "psychology", "policy", "society"),
        }
        for domain, keywords in fallback_map.items():
            if any(keyword in haystack for keyword in keywords):
                return domain
        return "Other"

    def _fallback_keywords(self, text: str) -> str:
        tokens = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text.lower())
        stopwords = {
            "research",
            "university",
            "department",
            "professor",
            "faculty",
            "student",
            "science",
            "school",
            "their",
            "with",
            "from",
            "that",
            "this",
            "have",
        }
        candidates = [token for token in tokens if token not in stopwords]
        common = [word for word, _ in Counter(candidates).most_common(5)]
        return ", ".join(common)
