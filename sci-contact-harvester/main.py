"""Application entry point for sci-contact-harvester."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_enrichment.classifier import AIEnricher
from config import (
    ANTHROPIC_API_KEY,
    DB_PATH,
    GITHUB_BRANCH,
    GITHUB_REPO_NAME,
    GITHUB_TOKEN,
    SCRAPE_DELAY,
    SERPAPI_KEY,
)
from data.database import ContactDatabase
from github_sync.pusher import GitHubSyncer
from scraper.email_extractor import ContactExtractor
from scraper.page_scraper import PageScraper
from scraper.search_engine import AcademicSearchEngine


LOGGER = logging.getLogger("sci_contact_harvester")
EXPORT_PATH = Path("exports") / "contacts.csv"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Harvest scientific researcher contact data.")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Insert 3 fake contacts and verify exports/GitHub sync without using external APIs.",
    )
    return parser.parse_args()


def run_scraping_pipeline(test_mode: bool = False) -> None:
    """Run the scraping workflow from discovery through export and sync."""
    database = ContactDatabase(DB_PATH)
    page_scraper = PageScraper()
    search_engine = AcademicSearchEngine(SERPAPI_KEY)
    extractor = ContactExtractor()
    enricher = AIEnricher(ANTHROPIC_API_KEY)
    github_syncer = GitHubSyncer(GITHUB_TOKEN, GITHUB_REPO_NAME, GITHUB_BRANCH)

    new_this_run = 0
    domains_covered: set[str] = set()

    if test_mode:
        LOGGER.info("Running in test mode; external search and AI enrichment are disabled.")
        for contact in _build_fake_contacts():
            before_count = database.count()
            database.insert_contact(contact)
            if database.count() > before_count:
                new_this_run += 1
            if contact.get("scientific_domain"):
                domains_covered.add(contact["scientific_domain"])
            print(f"✅ Found: {contact['full_name']} | {contact['email']} | {contact['institution']}")
        _finalize_run(database, github_syncer, new_this_run, domains_covered)
        return

    queries = search_engine.build_search_queries()[:5]
    LOGGER.info("Running %s search queries.", len(queries))

    for query in queries:
        LOGGER.info("Searching for candidate pages with query: %s", query)
        listing_urls = search_engine.search_query(query)
        if not listing_urls:
            LOGGER.info("No listing URLs returned for query: %s", query)
            continue

        for listing_url in listing_urls:
            LOGGER.info("Scanning listing URL: %s", listing_url)
            profile_urls = page_scraper.scrape_faculty_listing(listing_url)
            if not profile_urls:
                LOGGER.info("No profile links found on %s; treating it as a potential profile page.", listing_url)
                profile_urls = [listing_url]

            _sleep_between_requests()

            for profile_url in profile_urls[:10]:
                soup, full_text = page_scraper.scrape_profile_page(profile_url)
                _sleep_between_requests()
                if soup is None or not full_text:
                    continue

                if not page_scraper.is_valid_profile_page(profile_url, full_text):
                    LOGGER.info("Skipping non-profile page: %s", profile_url)
                    continue

                contact = extractor.build_contact(profile_url, soup, full_text)
                if not contact.get("email"):
                    LOGGER.info("Skipping %s because no usable email was found.", profile_url)
                    continue

                enriched_contact = enricher.enrich_contact(contact, full_text[:2000])
                before_count = database.count()
                database.insert_contact(enriched_contact)
                if database.count() > before_count:
                    new_this_run += 1
                if enriched_contact.get("scientific_domain"):
                    domains_covered.add(enriched_contact["scientific_domain"])

                print(
                    "✅ Found: "
                    f"{enriched_contact.get('full_name') or 'Unknown'} | "
                    f"{enriched_contact.get('email')} | "
                    f"{enriched_contact.get('institution') or 'Unknown institution'}"
                )

    _finalize_run(database, github_syncer, new_this_run, domains_covered)


def _finalize_run(
    database: ContactDatabase,
    github_syncer: GitHubSyncer,
    new_this_run: int,
    domains_covered: set[str],
) -> None:
    database.export_to_csv(EXPORT_PATH)
    LOGGER.info("Exported contacts to %s", EXPORT_PATH)

    contacts = database.get_all_contacts()
    csv_commit_sha = github_syncer.push_csv(str(EXPORT_PATH), "exports/contacts.csv")
    summary_commit_sha = github_syncer.push_json_summary(contacts)
    stats = {
        "total_contacts": database.count(),
        "new_this_run": new_this_run,
        "domains_covered": sorted(domains_covered),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    run_log_commit_sha = github_syncer.log_run(stats)

    LOGGER.info("GitHub CSV sync commit: %s", csv_commit_sha)
    LOGGER.info("GitHub summary sync commit: %s", summary_commit_sha)
    LOGGER.info("GitHub run log commit: %s", run_log_commit_sha)
    LOGGER.info("Pipeline finished with %s total contacts.", stats["total_contacts"])


def _sleep_between_requests() -> None:
    if SCRAPE_DELAY > 0:
        time.sleep(SCRAPE_DELAY)


def _build_fake_contacts() -> list[dict[str, Any]]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        {
            "full_name": "Dr. Ada Raman",
            "email": "ada.raman@example.edu",
            "institution": "Example Institute of Technology",
            "department": "Department of Computer Science",
            "position": "Professor",
            "research_interests": "machine learning, data systems, scientific computing",
            "profile_url": "https://example.edu/faculty/ada-raman",
            "source_website": "example.edu",
            "country": "India",
            "scientific_domain": "Computer Science",
            "h_index_estimate": None,
            "social_links": {"github": "https://github.com/adaraman"},
            "date_scraped": timestamp,
            "verified": 1,
        },
        {
            "full_name": "Dr. Leo Fischer",
            "email": "leo.fischer@example.edu",
            "institution": "Example Center for Quantum Research",
            "department": "Department of Physics",
            "position": "Researcher",
            "research_interests": "quantum optics, photonics, condensed matter",
            "profile_url": "https://example.edu/researchers/leo-fischer",
            "source_website": "example.edu",
            "country": "Germany",
            "scientific_domain": "Physics",
            "h_index_estimate": None,
            "social_links": {"scholar": "https://scholar.google.com/example-leo"},
            "date_scraped": timestamp,
            "verified": 1,
        },
        {
            "full_name": "Dr. Maya Chen",
            "email": "maya.chen@example.edu",
            "institution": "Example Biomedical University",
            "department": "Department of Neuroscience",
            "position": "Associate Professor",
            "research_interests": "cognitive neuroscience, neural imaging, biomarkers",
            "profile_url": "https://example.edu/people/maya-chen",
            "source_website": "example.edu",
            "country": "Singapore",
            "scientific_domain": "Neuroscience",
            "h_index_estimate": None,
            "social_links": {"linkedin": "https://www.linkedin.com/in/mayachen"},
            "date_scraped": timestamp,
            "verified": 1,
        },
    ]


if __name__ == "__main__":
    configure_logging()
    arguments = parse_args()
    try:
        run_scraping_pipeline(test_mode=arguments.test)
    except Exception:  # pragma: no cover - defensive top-level logging
        LOGGER.exception("Pipeline execution failed.")
        raise
