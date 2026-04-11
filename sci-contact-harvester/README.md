# sci-contact-harvester

`sci-contact-harvester` discovers academic profile pages, extracts researcher contact details, enriches the results with AI-assisted scientific domain classification, stores everything in SQLite, and exports the collected data for GitHub syncing.

## What This Project Does

- Searches for faculty listings and researcher profile pages using SerpAPI.
- Scrapes likely academic profile pages and extracts contact details such as name, email, institution, department, position, and research interests.
- Enriches records with a scientific domain classification and keyword extraction using Anthropic's Claude API.
- Stores harvested contacts in a local SQLite database.
- Exports CSV and JSON summaries and pushes them to GitHub for remote tracking.

## Setup

1. Clone the repository.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the environment template and fill in your credentials:

```bash
copy .env.example .env
```

Populate `.env` with:

- `GITHUB_TOKEN`
- `GITHUB_REPO_NAME`
- `GITHUB_BRANCH` (optional, defaults to `main`)
- `SERPAPI_KEY`
- `ANTHROPIC_API_KEY`
- `DB_PATH` (optional, defaults to `sci_contacts.db`)
- `SCRAPE_DELAY` (optional, defaults to `2.0`)

## Run

Run the full scraping pipeline:

```bash
python main.py
```

## Test Mode

Run without spending SerpAPI or Anthropic credits:

```bash
python main.py --test
```

Test mode inserts 3 fake researcher contacts, exports them, and triggers GitHub sync so you can verify repository writes.

## What Gets Pushed to GitHub

When GitHub credentials are configured, the pipeline pushes:

- `exports/contacts.csv`: the full exported contact list.
- `exports/summary.json`: a compact summary containing `name`, `email`, `institution`, and `domain`.
- `logs/run_history.json`: appended run metadata including total contacts, newly inserted contacts, covered domains, and a timestamp.

Each run updates or creates these files automatically after export.
