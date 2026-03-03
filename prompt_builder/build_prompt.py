"""
Assemble a copyable, LLM-agnostic prompt for a given job.

Usage:
    python -c "from prompt_builder.build_prompt import generate; print(generate(job_id=1))"
"""
import sqlite3

from dashboard.db import get_db_path
from matcher.match import find_relevant_chunks

PROMPT_TEMPLATE = """\
You are helping craft a hyper-personalized job application for William Welsh.

## Target Role
Company: {company}
Title: {title}
Posted: {date_posted}
URL: {job_url}

## Job Description
{description}

## Relevant Code From William's Portfolio
(These are real code snippets automatically matched to this job)

{code_sections}

## Your Task
Write a concise cover letter / pitch (3–4 paragraphs) that:
1. Opens by naming a specific technical challenge in the job description
2. References the exact code above as proof William has already solved similar problems
3. Cites file names or repo names — be concrete, not generic
4. Closes with a direct ask for a call or interview
5. Tone: direct, builder-to-builder, no corporate fluff
"""

CODE_SECTION_TEMPLATE = """\
### [{repo}] {file}
Source: {full_url}
---
{content}
---
"""


def generate(job_id: int, n_results: int = 6) -> str:
    """Build and return the copyable prompt string for the given job ID."""
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    if row is None:
        raise ValueError(f"No job found with id={job_id}")

    description = row["description"] or ""
    chunks = find_relevant_chunks(description, n_results=n_results)

    code_sections = "\n".join(
        CODE_SECTION_TEMPLATE.format(
            repo=c["repo"],
            file=c["file"],
            full_url=c["full_url"],
            content=c["content"],
        )
        for c in chunks
    )

    return PROMPT_TEMPLATE.format(
        company=row["company"] or "Unknown Company",
        title=row["title"] or "Unknown Title",
        date_posted=row["date_posted"] or "Unknown",
        job_url=row["job_url"] or "",
        description=description,
        code_sections=code_sections if code_sections else "(No portfolio matches found)",
    )
