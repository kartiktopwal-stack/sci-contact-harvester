"""Scraper package for search, page parsing, and email extraction."""

from scraper.email_extractor import ContactExtractor
from scraper.page_scraper import PageScraper
from scraper.search_engine import AcademicSearchEngine

__all__ = ["AcademicSearchEngine", "ContactExtractor", "PageScraper"]
