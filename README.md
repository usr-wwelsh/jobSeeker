# jobSeeker

A local-first job-hunting engine that indexes your GitHub portfolio into a vector database, scrapes daily job listings, and generates hyper-personalized, LLM-agnostic application prompts packed with real code snippets from your own work.

## How it works

1. **Indexer** — clones all your public GitHub repos and chunks them into a local ChromaDB vector store
2. **Scraper** — pulls fresh job listings daily via [JobSpy](https://github.com/speedyapply/JobSpy) (LinkedIn + Indeed)
3. **Matcher** — semantic search finds the code from your portfolio most relevant to each job description
4. **Prompt builder** — assembles a ready-to-copy prompt referencing your actual files and repos
5. **Dashboard** — private web UI to browse scraped jobs, generate prompts, track application status, and manually generate prompts from any job description you paste in

You copy the prompt into any chatbot (ChatGPT, Claude, Gemini, etc.) to produce the final pitch. No API keys required for the core workflow.

---

## Quick start

### 1. Clone and set up

```bash
git clone https://github.com/usr-wwelsh/jobSeeker
cd jobSeeker
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
YOUR_NAME=Jane Smith   # Your full name (required for prompt generation)
GITHUB_USERNAME=your-github-username
DASHBOARD_PASSWORD=pick-a-strong-password
GITHUB_TOKEN=ghp_...   # optional but recommended
```

`GITHUB_TOKEN` raises the GitHub API rate limit from 60 to 5,000 requests/hour. Generate one at https://github.com/settings/tokens (no scopes needed for public repos).

### 3. Index your portfolio

```bash
python -m indexer.build_index
```

This clones all your public repos into `data/repos/` and builds the ChromaDB index in `data/chroma_data/`. Re-run any time to pick up new commits (`git pull` is run automatically, repos are never deleted).

Options:
- `--incremental` — upsert only, skip wiping the collection
- `--skip-clone` — skip git operations, re-index from existing `data/repos/`

### 4. Scrape jobs

```bash
python -m scraper.job_scraper
```

Scrapes LinkedIn and Indeed for founding/early-stage roles and internships/new-grad roles posted in the last 24 hours. Results go into `data/jobs.db`.

### 5. Start the dashboard

```bash
uvicorn dashboard.app:app --reload --port 8080
```

Open http://localhost:8080 and log in with your `DASHBOARD_PASSWORD`.

- **Jobs** — browse scraped listings, click any job, hit **Generate Prompt** to build a personalized pitch
- **Manual Prompt** (nav bar) — paste any job description from anywhere to get a matched prompt instantly, no scraping needed
- **Run Scrape** (nav bar) — trigger a manual scrape on demand

The dashboard also runs a daily scrape automatically at 9am EST (14:00 UTC) via APScheduler.

---

## Project structure

```
jobSeeker/
├── indexer/
│   ├── fetch_repos.py      # GitHub API → repo list
│   ├── clone_repos.py      # git clone / git pull into data/repos/
│   └── build_index.py      # chunk repos → upsert ChromaDB
├── scraper/
│   └── job_scraper.py      # JobSpy → SQLite
├── matcher/
│   └── match.py            # semantic search against portfolio
├── prompt_builder/
│   └── build_prompt.py     # assemble copyable prompt
├── dashboard/
│   ├── app.py              # FastAPI app
│   ├── db.py               # SQLite helpers
│   └── templates/          # Jinja2 + Tailwind + HTMX
│       ├── base.html        # nav, shared layout
│       ├── login.html
│       ├── jobs.html        # scraped job list
│       ├── job.html         # job detail + prompt
│       ├── manual.html      # paste-in prompt generator
│       └── manual_result.html
├── data/                   # gitignored — generated locally
│   ├── repos/              # cloned repos (never auto-deleted)
│   ├── chroma_data/        # ChromaDB persistent store
│   └── jobs.db             # SQLite job listings
├── Dockerfile              # optional Railway deployment
├── .env.example
└── requirements.txt
```

---

## Customizing job searches

Edit the `SCRAPE_PASSES` list in `scraper/job_scraper.py` to change search terms, locations, sites, or how far back to look (`hours_old`).

## Deployment (optional)

A `Dockerfile` is included for Railway or any Docker host. Mount a persistent volume at `/app/data/` so the ChromaDB index and SQLite database survive redeploys. Set `GITHUB_USERNAME`, `DASHBOARD_PASSWORD`, and `GITHUB_TOKEN` as environment variables.

---

## License

MIT
