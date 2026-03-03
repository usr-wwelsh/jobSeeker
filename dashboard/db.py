"""
SQLite helpers for the jobSeeker dashboard.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site        TEXT,
    title       TEXT,
    company     TEXT,
    location    TEXT,
    job_url     TEXT UNIQUE,
    description TEXT,
    job_type    TEXT,
    min_salary  INTEGER,
    max_salary  INTEGER,
    date_posted TEXT,
    scraped_at  TEXT DEFAULT (datetime('now')),
    status      TEXT DEFAULT 'new'
);
"""


def get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def init_db():
    path = get_db_path()
    with sqlite3.connect(path) as conn:
        conn.execute(CREATE_JOBS_TABLE)
        conn.commit()


def get_jobs(status: str | None = None, page: int = 1, per_page: int = 25) -> tuple[list[dict], int]:
    """Return (jobs_list, total_count) with optional status filter and pagination."""
    path = get_db_path()
    offset = (page - 1) * per_page
    where = "WHERE status = ?" if status else ""
    params_count = (status,) if status else ()
    params_list = (status, per_page, offset) if status else (per_page, offset)

    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        total = conn.execute(
            f"SELECT COUNT(*) FROM jobs {where}", params_count
        ).fetchone()[0]
        rows = conn.execute(
            f"""SELECT id, site, title, company, location, job_url,
                       job_type, min_salary, max_salary, date_posted,
                       scraped_at, status
                FROM jobs {where}
                ORDER BY scraped_at DESC
                LIMIT ? OFFSET ?""",
            params_list,
        ).fetchall()

    return [dict(r) for r in rows], total


def get_job(job_id: int) -> dict | None:
    path = get_db_path()
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def update_job_status(job_id: int, status: str):
    valid = {"new", "prompted", "applied", "rejected"}
    if status not in valid:
        raise ValueError(f"Invalid status: {status!r}. Must be one of {valid}")
    path = get_db_path()
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()
