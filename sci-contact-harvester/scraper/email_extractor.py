"""Email extraction module."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
BLOCKED_PREFIXES = ("noreply@", "support@", "info@", "admin@", "webmaster@")
POSITION_KEYWORDS = [
    "Associate Professor",
    "Assistant Professor",
    "Professor",
    "Researcher",
    "Postdoc",
    "PhD Student",
    "Lecturer",
    "Scientist",
    "Fellow",
]
NAME_CLASSES = {
    "faculty-name",
    "researcher-name",
    "profile-name",
    "name",
    "author-name",
}
DOMAIN_KEYWORDS = {
    "Physics": ("physics", "quantum", "astrophysics", "particle"),
    "Chemistry": ("chemistry", "chemical", "organic", "inorganic"),
    "Biology": ("biology", "biological", "genetics", "microbiology", "ecology"),
    "Computer Science": ("computer science", "machine learning", "artificial intelligence", "software"),
    "Mathematics": ("mathematics", "algebra", "geometry", "statistics"),
    "Engineering": ("engineering", "robotics", "mechanical", "electrical", "civil"),
    "Medicine": ("medicine", "clinical", "medical", "healthcare"),
    "Environmental Science": ("environment", "climate", "sustainability", "earth science"),
    "Neuroscience": ("neuroscience", "brain", "neural", "cognition"),
    "Materials Science": ("materials", "nanomaterials", "polymer", "metallurgy"),
}
COUNTRY_BY_TLD = {
    "uk": "United Kingdom",
    "jp": "Japan",
    "au": "Australia",
    "ca": "Canada",
    "de": "Germany",
    "fr": "France",
    "ch": "Switzerland",
    "sg": "Singapore",
    "in": "India",
}


class ContactExtractor:
    """Extract structured researcher information from profile pages."""

    def extract_emails(self, text: str) -> list[str]:
        """Extract unique, non-generic email addresses from text."""
        emails = {
            email.lower()
            for email in EMAIL_PATTERN.findall(text or "")
            if not email.lower().startswith(BLOCKED_PREFIXES)
        }
        return sorted(emails)

    def extract_name_from_page(self, soup: BeautifulSoup, url: str) -> str | None:
        """Extract a researcher name from a profile page using several heuristics."""
        del url

        for heading in soup.find_all("h1"):
            candidate = self._clean_text(heading.get_text(" ", strip=True))
            if self._looks_like_name(candidate):
                return candidate

        for meta_name in ("og:title", "twitter:title"):
            meta_tag = soup.find("meta", attrs={"property": meta_name}) or soup.find(
                "meta", attrs={"name": meta_name}
            )
            if not meta_tag:
                continue
            candidate = self._clean_text(meta_tag.get("content", ""))
            candidate = self._split_title_candidate(candidate)
            if self._looks_like_name(candidate):
                return candidate

        for tag in soup.find_all(
            class_=lambda value: bool(value)
            and any(
                class_name in NAME_CLASSES
                for class_name in (value if isinstance(value, list) else str(value).split())
            )
        ):
            candidate = self._clean_text(tag.get_text(" ", strip=True))
            if self._looks_like_name(candidate):
                return candidate

        return None

    def extract_institution(self, soup: BeautifulSoup, url: str) -> str | None:
        """Extract the institution from page metadata or footer content."""
        if soup.title and soup.title.string:
            candidate = self._extract_institution_candidate(soup.title.string)
            if candidate:
                return candidate

        site_name = soup.find("meta", attrs={"property": "og:site_name"}) or soup.find(
            "meta", attrs={"name": "og:site_name"}
        )
        if site_name:
            candidate = self._clean_text(site_name.get("content", ""))
            if candidate:
                return candidate

        footer_text = " ".join(
            self._clean_text(footer.get_text(" ", strip=True)) for footer in soup.find_all("footer")
        )
        footer_match = re.search(
            r"((?:University|Institute|College|School|Laboratory|Centre|Center)[^|,.;]{0,120})",
            footer_text,
            re.IGNORECASE,
        )
        if footer_match:
            return self._clean_text(footer_match.group(1))

        hostname = urlparse(url).netloc.replace("www.", "")
        return hostname or None

    def extract_position(self, text: str) -> str | None:
        """Extract an academic position from free-form page text."""
        for keyword in POSITION_KEYWORDS:
            if re.search(rf"\b{re.escape(keyword)}\b", text or "", flags=re.IGNORECASE):
                return keyword
        return None

    def build_contact(self, url: str, soup: BeautifulSoup, raw_text: str) -> dict[str, Any]:
        """Build a contact record that is ready for insertion into the database."""
        emails = self.extract_emails(raw_text)
        institution = self.extract_institution(soup, url)
        department = self._extract_department(raw_text)
        research_interests = self._extract_research_interests(raw_text)
        social_links = self._extract_social_links(soup)
        scientific_domain = self._infer_domain(department, research_interests, raw_text)

        return {
            "full_name": self.extract_name_from_page(soup, url),
            "email": emails[0] if emails else None,
            "institution": institution,
            "department": department,
            "position": self.extract_position(raw_text),
            "research_interests": research_interests,
            "profile_url": url,
            "source_website": urlparse(url).netloc,
            "country": self._infer_country(url, institution),
            "scientific_domain": scientific_domain,
            "h_index_estimate": None,
            "social_links": social_links,
            "date_scraped": datetime.now(timezone.utc).isoformat(),
            "verified": 1 if emails else 0,
        }

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "")).strip()

    def _looks_like_name(self, value: str) -> bool:
        if not value:
            return False
        words = value.split()
        if not 2 <= len(words) <= 6:
            return False
        disallowed = {"university", "department", "faculty", "school", "home", "profile"}
        return not any(word.lower() in disallowed for word in words)

    def _split_title_candidate(self, title: str) -> str:
        for separator in ("|", "-", "•", ":"):
            if separator in title:
                for part in [self._clean_text(piece) for piece in title.split(separator)]:
                    if self._looks_like_name(part):
                        return part
        return title

    def _extract_institution_candidate(self, title: str) -> str | None:
        title = self._clean_text(title)
        parts = [title]
        for separator in ("|", "-", "•", ":"):
            expanded: list[str] = []
            for part in parts:
                expanded.extend(piece for piece in (self._clean_text(item) for item in part.split(separator)) if piece)
            parts = expanded
        institution_markers = (
            "university",
            "institute",
            "college",
            "school",
            "caltech",
            "mit",
            "epfl",
            "iit",
        )
        for part in parts:
            if any(marker in part.lower() for marker in institution_markers):
                return part
        return title if title else None

    def _extract_department(self, text: str) -> str | None:
        patterns = (
            r"(Department of [A-Za-z&,\- ]+)",
            r"(School of [A-Za-z&,\- ]+)",
            r"(Faculty of [A-Za-z&,\- ]+)",
            r"(Institute of [A-Za-z&,\- ]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text or "", flags=re.IGNORECASE)
            if match:
                return self._clean_text(match.group(1))
        return None

    def _extract_research_interests(self, text: str) -> str | None:
        lines = [self._clean_text(line) for line in (text or "").splitlines()]
        for index, line in enumerate(lines):
            if not line:
                continue
            lowered = line.lower()
            if lowered.startswith("research interests"):
                _, _, remainder = line.partition(":")
                candidate = remainder.strip() or (lines[index + 1] if index + 1 < len(lines) else "")
                return candidate[:300] if candidate else None

        keywords: list[str] = []
        lowered_text = text.lower() if text else ""
        for markers in DOMAIN_KEYWORDS.values():
            for marker in markers:
                if marker in lowered_text:
                    keywords.append(marker)
            if keywords:
                break
        return ", ".join(dict.fromkeys(keywords))[:300] if keywords else None

    def _extract_social_links(self, soup: BeautifulSoup) -> dict[str, str]:
        social_links: dict[str, str] = {}
        patterns = {
            "linkedin": "linkedin.com",
            "twitter": "twitter.com",
            "x": "x.com",
            "github": "github.com",
            "scholar": "scholar.google",
            "researchgate": "researchgate.net",
            "orcid": "orcid.org",
        }
        for link in soup.find_all("a", href=True):
            href = link["href"].strip()
            for key, marker in patterns.items():
                if marker in href and key not in social_links:
                    social_links[key] = href
        return social_links

    def _infer_domain(self, department: str | None, research_interests: str | None, text: str) -> str | None:
        haystack = " ".join(part for part in (department, research_interests, text[:2000]) if part).lower()
        for domain, markers in DOMAIN_KEYWORDS.items():
            if any(marker in haystack for marker in markers):
                return domain
        return None

    def _infer_country(self, url: str, institution: str | None) -> str | None:
        hostname = urlparse(url).netloc.lower()
        suffix = hostname.rsplit(".", maxsplit=1)[-1] if "." in hostname else ""
        if suffix in COUNTRY_BY_TLD:
            return COUNTRY_BY_TLD[suffix]
        if institution and "london" in institution.lower():
            return "United Kingdom"
        return None
