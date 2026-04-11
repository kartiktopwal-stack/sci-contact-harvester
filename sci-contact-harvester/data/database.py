"""Database access module."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


class ContactDatabase:
    """Manage persisted contacts in a SQLite database."""

    TABLE_NAME = "contacts"
    FIELD_NAMES = [
        "id",
        "full_name",
        "email",
        "institution",
        "department",
        "position",
        "research_interests",
        "profile_url",
        "source_website",
        "country",
        "scientific_domain",
        "h_index_estimate",
        "social_links",
        "date_scraped",
        "verified",
    ]
    INSERT_FIELDS = FIELD_NAMES[1:]

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self) -> None:
        """Create the contacts table if it does not already exist."""
        self.connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                email TEXT UNIQUE,
                institution TEXT,
                department TEXT,
                position TEXT,
                research_interests TEXT,
                profile_url TEXT,
                source_website TEXT,
                country TEXT,
                scientific_domain TEXT,
                h_index_estimate TEXT,
                social_links TEXT,
                date_scraped TEXT,
                verified INTEGER DEFAULT 0
            )
            """
        )
        self.connection.commit()

    def insert_contact(self, contact_dict: dict[str, Any]) -> None:
        """Insert a contact and ignore duplicates by email."""
        values: list[Any] = []
        for field in self.INSERT_FIELDS:
            value = contact_dict.get(field)
            if field == "social_links" and value is not None and not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=True)
            values.append(value)

        placeholders = ", ".join("?" for _ in self.INSERT_FIELDS)
        columns = ", ".join(self.INSERT_FIELDS)
        self.connection.execute(
            f"INSERT OR IGNORE INTO {self.TABLE_NAME} ({columns}) VALUES ({placeholders})",
            values,
        )
        self.connection.commit()

    def get_all_contacts(self) -> list[dict[str, Any]]:
        """Return all contacts as dictionaries."""
        cursor = self.connection.execute(
            f"SELECT {', '.join(self.FIELD_NAMES)} FROM {self.TABLE_NAME}"
        )
        return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(self, filepath: str | Path) -> None:
        """Export all contacts to a CSV file."""
        export_path = Path(filepath)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        contacts = self.get_all_contacts()

        with export_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=self.FIELD_NAMES)
            writer.writeheader()
            writer.writerows(contacts)

    def count(self) -> int:
        """Return the total number of stored contacts."""
        cursor = self.connection.execute(f"SELECT COUNT(*) FROM {self.TABLE_NAME}")
        return int(cursor.fetchone()[0])

    def search_by_domain(self, domain: str) -> list[dict[str, Any]]:
        """Return contacts filtered by scientific domain."""
        cursor = self.connection.execute(
            f"""
            SELECT {', '.join(self.FIELD_NAMES)}
            FROM {self.TABLE_NAME}
            WHERE scientific_domain = ?
            """,
            (domain,),
        )
        return [dict(row) for row in cursor.fetchall()]
