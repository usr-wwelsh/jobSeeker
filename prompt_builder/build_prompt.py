"""
Assemble a copyable, LLM-agnostic prompt for a given job.

Usage:
    python -c "from prompt_builder.build_prompt import generate; print(generate(job_id=1))"
"""
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from dashboard.db import get_db_path
from matcher.match import find_relevant_chunks

load_dotenv()

RESUME_PATH = Path(__file__).resolve().parent.parent / "data" / "resume.txt"

PROMPT_TEMPLATE = """\
You are helping craft a hyper-personalized job application for {name}.

## About {name}
{resume}

## Target Role
Company: {company}
Title: {title}
Posted: {date_posted}
URL: {job_url}

## Job Description
{description}

## Relevant Code From {name}'s Portfolio
(These are real code snippets automatically matched to this job description)

{code_sections}

## Referenced GitHub Links
The following are the direct GitHub URLs to the matched files above. Use these verbatim in your output — do not paraphrase or shorten them:

{github_links}

## Your Task
Write a concise cover letter / pitch (3–4 paragraphs) that:
1. Opens by naming a specific technical challenge in the job description
2. References the exact code above as proof {name} has already solved similar problems
3. Includes the direct GitHub links above so the reader can view the code immediately — paste them as-is
4. Closes with a direct ask for a call or interview
5. Tone: direct, builder-to-builder, no corporate fluff
"""


def _load_resume() -> str:
    if not RESUME_PATH.exists():
        print(f"WARNING: No resume found at {RESUME_PATH}. Add your resume as data/resume.txt.")
        return "(No resume provided)"
    text = RESUME_PATH.read_text(encoding="utf-8").strip()
    return text if text else "(resume file is empty)"


CODE_SECTION_TEMPLATE = """\
### [{repo}] {file}
Source: {full_url}
---
{content}
---
"""


def _build(name: str, company: str, title: str, date_posted: str,
           job_url: str, description: str, n_results: int = 6) -> str:
    """Core builder — shared by generate() and generate_from_raw()."""
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

    seen: set[str] = set()
    github_links_list: list[str] = []
    for c in chunks:
        url = c["full_url"]
        if url and url not in seen:
            seen.add(url)
            github_links_list.append(f"- [{c['repo']} / {c['file']}]({url})")
    github_links = "\n".join(github_links_list) if github_links_list else "(none)"

    return PROMPT_TEMPLATE.format(
        name=name,
        resume=_load_resume(),
        company=company,
        title=title,
        date_posted=date_posted,
        job_url=job_url,
        description=description,
        code_sections=code_sections if code_sections else "(No portfolio matches found)",
        github_links=github_links,
    )


def generate(job_id: int, n_results: int = 6) -> str:
    """Build and return the copyable prompt string for the given job ID."""
    name = os.environ.get("YOUR_NAME", "").strip()
    if not name:
        raise RuntimeError("YOUR_NAME is not set. Add it to your .env file.")
    db_path = get_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"No job found with id={job_id}")

    return _build(
        name=name,
        company=row["company"] or "Unknown Company",
        title=row["title"] or "Unknown Title",
        date_posted=row["date_posted"] or "Unknown",
        job_url=row["job_url"] or "",
        description=row["description"] or "",
        n_results=n_results,
    )


def generate_from_raw(
    description: str,
    company: str = "",
    title: str = "",
    job_url: str = "",
    n_results: int = 6,
) -> str:
    """Build a prompt from a manually pasted job description (no DB entry needed)."""
    name = os.environ.get("YOUR_NAME", "").strip()
    if not name:
        raise RuntimeError("YOUR_NAME is not set. Add it to your .env file.")

    return _build(
        name=name,
        company=company or "Unknown Company",
        title=title or "Manual Entry",
        date_posted="—",
        job_url=job_url,
        description=description,
        n_results=n_results,
    )
