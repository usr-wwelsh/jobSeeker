"""
Scrape job listings via JobSpy and store them in data/jobs.db.

Usage:
    python -m scraper.job_scraper
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from jobspy import scrape_jobs

from dashboard.db import get_db_path, init_db

SCRAPE_PASSES = [
    # Pass 1 — founding / early-stage roles
    dict(
        site_name=["linkedin", "indeed"],
        search_term='"founding engineer" OR "early engineer" OR "software engineer" startup',
        location="Remote",
        results_wanted=25,
        hours_old=24,
        is_remote=True,
        linkedin_fetch_description=True,
        description_format="markdown",
        country_indeed="USA",
    ),
    # Pass 2 — internships / new-grad safety net
    dict(
        site_name=["linkedin", "indeed"],
        search_term='"software engineer intern" OR "software engineering intern" OR "new grad software"',
        location="Remote",
        results_wanted=25,
        hours_old=24,
        is_remote=True,
        linkedin_fetch_description=True,
        description_format="markdown",
        country_indeed="USA",
    ),
]


def scrape_and_store() -> int:
    init_db()
    db_path = get_db_path()

    all_frames: list[pd.DataFrame] = []
    for i, kwargs in enumerate(SCRAPE_PASSES, 1):
        print(f"Scrape pass {i}/{len(SCRAPE_PASSES)}: {kwargs['search_term'][:60]}...")
        try:
            df = scrape_jobs(**kwargs)
            print(f"  → {len(df)} results")
            all_frames.append(df)
        except Exception as e:
            print(f"  WARNING: pass {i} failed: {e}")

    if not all_frames:
        print("No results from any scrape pass.")
        return 0

    combined = pd.concat(all_frames, ignore_index=True)

    # Deduplicate by job_url (keep first occurrence)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    combined = combined[combined["job_url"].notna()]

    scraped_at = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with sqlite3.connect(db_path) as conn:
        for _, row in combined.iterrows():
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO jobs
                        (site, title, company, location, job_url, description,
                         job_type, min_salary, max_salary, date_posted, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _str(row.get("site")),
                        _str(row.get("title")),
                        _str(row.get("company")),
                        _str(row.get("location")),
                        _str(row.get("job_url")),
                        _str(row.get("description")),
                        _str(row.get("job_type")),
                        _int(row.get("min_amount")),
                        _int(row.get("max_amount")),
                        _str(row.get("date_posted")),
                        scraped_at,
                    ),
                )
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            except Exception as e:
                print(f"  Row insert error: {e}")
        conn.commit()

    print(f"Inserted {inserted} new jobs (of {len(combined)} deduplicated).")
    return inserted


def _str(val) -> str | None:
    if val is None or (isinstance(val, float) and val != val):
        return None
    return str(val)


def _int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    scrape_and_store()
