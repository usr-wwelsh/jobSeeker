"""
FastAPI dashboard for jobSeeker.

Start locally:
    uvicorn dashboard.app:app --reload --port 8080
"""
import os
from typing import Annotated

from dotenv import load_dotenv
load_dotenv()

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Cookie, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from dashboard.db import get_job, get_jobs, init_db, update_job_status
from prompt_builder.build_prompt import generate as build_prompt, generate_from_raw
from scraper.job_scraper import scrape_and_store

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="jobSeeker")
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")
SESSION_COOKIE = "js_session"
PER_PAGE = 25

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _check_auth(session: str | None) -> bool:
    if not DASHBOARD_PASSWORD:
        raise RuntimeError("DASHBOARD_PASSWORD env var is not set")
    return session == DASHBOARD_PASSWORD


def _auth_or_redirect(session: str | None) -> None:
    if not _check_auth(session):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


# ---------------------------------------------------------------------------
# Auth middleware (redirect unauthenticated requests)
# ---------------------------------------------------------------------------

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    public_paths = {"/login", "/favicon.ico"}
    if request.url.path in public_paths or request.url.path.startswith("/static"):
        return await call_next(request)

    session = request.cookies.get(SESSION_COOKIE)
    if not session or not _check_auth(session):
        return RedirectResponse("/login", status_code=302)

    return await call_next(request)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    init_db()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        scrape_and_store,
        trigger="cron",
        hour=14,
        minute=0,
        timezone="UTC",
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler


@app.on_event("shutdown")
def on_shutdown():
    if hasattr(app.state, "scheduler"):
        app.state.scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse("/jobs", status_code=302)


# --- Login ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": error}
    )


@app.post("/login")
async def login(password: Annotated[str, Form()], response: Response):
    if not DASHBOARD_PASSWORD:
        return RedirectResponse("/login?error=Server+not+configured", status_code=303)
    if password != DASHBOARD_PASSWORD:
        return RedirectResponse("/login?error=Invalid+password", status_code=303)
    resp = RedirectResponse("/jobs", status_code=303)
    resp.set_cookie(SESSION_COOKIE, password, httponly=True, samesite="lax")
    return resp


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


# --- Job list ---

@app.get("/jobs", response_class=HTMLResponse)
async def jobs_list(
    request: Request,
    status: str = "",
    page: int = 1,
):
    filter_status = status if status in {"new", "prompted", "applied", "rejected"} else None
    jobs, total = get_jobs(status=filter_status, page=page, per_page=PER_PAGE)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    # For HTMX partial swap, return only the inner content fragment
    template = "jobs.html"
    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "jobs": jobs,
            "current_status": status,
            "page": page,
            "total_pages": total_pages,
            "total": total,
        },
    )


# --- Job detail ---

@app.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: int):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return templates.TemplateResponse(
        "job.html", {"request": request, "job": job, "prompt": None}
    )


# --- Generate prompt (HTMX endpoint) ---

@app.get("/jobs/{job_id}/prompt", response_class=HTMLResponse)
async def job_prompt(request: Request, job_id: int):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        prompt_text = build_prompt(job_id=job_id)
        # Mark as prompted
        update_job_status(job_id, "prompted")
        job["status"] = "prompted"
    except Exception as e:
        prompt_text = f"Error generating prompt: {e}"

    return templates.TemplateResponse(
        "job.html", {"request": request, "job": job, "prompt": prompt_text}
    )


# --- Update status ---

@app.post("/jobs/{job_id}/status", response_class=HTMLResponse)
async def set_status(
    request: Request,
    job_id: int,
    status: Annotated[str, Form()],
):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    try:
        update_job_status(job_id, status)
        job["status"] = status
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # HTMX swap: return just the status badge snippet
    badge_html = _status_badge_html(job_id, status)
    return HTMLResponse(badge_html)


def _status_badge_html(job_id: int, status: str) -> str:
    colors = {
        "new": "bg-blue-100 text-blue-800",
        "prompted": "bg-yellow-100 text-yellow-800",
        "applied": "bg-green-100 text-green-800",
        "rejected": "bg-red-100 text-red-800",
    }
    cls = colors.get(status, "bg-gray-100 text-gray-800")
    return f'<span id="status-badge-{job_id}" class="px-2 py-1 rounded text-sm font-medium {cls}">{status}</span>'


# --- Manual prompt page ---

@app.get("/manual", response_class=HTMLResponse)
async def manual_page(request: Request):
    return templates.TemplateResponse("manual.html", {"request": request, "prompt": None, "error": None})


@app.post("/manual", response_class=HTMLResponse)
async def manual_generate(
    request: Request,
    description: Annotated[str, Form()],
    company: Annotated[str, Form()] = "",
    title: Annotated[str, Form()] = "",
    job_url: Annotated[str, Form()] = "",
):
    prompt = None
    error = None
    try:
        prompt = generate_from_raw(
            description=description,
            company=company,
            title=title,
            job_url=job_url,
        )
    except Exception as e:
        error = str(e)

    # HTMX posts get just the result fragment; full page loads get the whole template
    if "HX-Request" in request.headers:
        return templates.TemplateResponse(
            "manual_result.html", {"request": request, "prompt": prompt, "error": error}
        )
    return templates.TemplateResponse(
        "manual.html", {"request": request, "prompt": prompt, "error": error}
    )


# --- Manual scrape trigger ---

@app.post("/scrape", response_class=HTMLResponse)
async def manual_scrape():
    try:
        count = scrape_and_store()
        return HTMLResponse(f"<p class='text-green-700'>Scrape complete — {count} new jobs inserted.</p>")
    except Exception as e:
        return HTMLResponse(f"<p class='text-red-700'>Scrape failed: {e}</p>")
