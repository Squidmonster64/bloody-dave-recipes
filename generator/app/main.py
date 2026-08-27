"""FastAPI entrypoint for Bloody Dave Recipe Studio."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import jobs as joblib
from .auth import (
    AuthSession,
    clear_session,
    issue_session,
    password_configured,
    read_session,
    require_csrf,
    verify_password,
)
from .config import settings
from .models import CreateJobRequest, PatchRecipeRequest

app = FastAPI(title="Bloody Dave Recipe Studio", version="1.0.0")
TEMPLATES = Path(__file__).parent / "templates"
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _rate_buckets[ip]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


@app.on_event("startup")
def _startup() -> None:
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    joblib.cleanup_old_jobs()


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "bd-recipe-studio", "version": settings.generator_version}


@app.get("/", response_class=HTMLResponse)
def studio_home(request: Request) -> HTMLResponse:
    session = read_session(request)
    html = (TEMPLATES / "studio.html").read_text(encoding="utf-8")
    authed = "true" if session else "false"
    html = html.replace("{{AUTHED}}", authed)
    html = html.replace("{{STUDIO_BASE}}", settings.studio_base_url)
    html = html.replace("{{PUBLIC_URL}}", settings.public_recipes_url)
    return HTMLResponse(html)


@app.post("/login")
def login(response: Response, password: str = Form(...)) -> RedirectResponse:
    if settings.auth_mode == "cloudflare_access":
        return RedirectResponse("/", status_code=303)
    if not verify_password(password):
        raise HTTPException(status_code=401, detail="Invalid password")
    redirect = RedirectResponse("/", status_code=303)
    issue_session(redirect)
    return redirect


@app.post("/logout")
def logout() -> RedirectResponse:
    redirect = RedirectResponse("/", status_code=303)
    clear_session(redirect)
    return redirect


@app.post("/api/v1/jobs")
async def create_job(
    payload: CreateJobRequest,
    request: Request,
    background: BackgroundTasks,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
    _limit: None = Depends(_rate_limit),
) -> dict:
    job = joblib.create_job(payload)
    background.add_task(joblib.run_pipeline, job.job_id)
    return {"job_id": job.job_id, "status": job.status.value}


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, _session: AuthSession) -> dict:
    try:
        job = joblib.load_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    return job.model_dump()


@app.patch("/api/v1/jobs/{job_id}/recipe")
async def patch_recipe(
    job_id: str,
    payload: PatchRecipeRequest,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
) -> dict:
    try:
        job = await joblib.patch_recipe(job_id, payload)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.model_dump()


@app.post("/api/v1/jobs/{job_id}/regenerate-image")
async def regenerate_image(
    job_id: str,
    background: BackgroundTasks,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
    _limit: None = Depends(_rate_limit),
) -> dict:
    background.add_task(joblib.regenerate_image, job_id)
    return {"job_id": job_id, "status": "GENERATING_IMAGE"}


@app.post("/api/v1/jobs/{job_id}/render")
async def render_job(
    job_id: str,
    background: BackgroundTasks,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
) -> dict:
    background.add_task(joblib.render_and_qa, job_id)
    return {"job_id": job_id, "status": "RENDERING_CARD"}


@app.post("/api/v1/jobs/{job_id}/qa")
async def qa_job(
    job_id: str,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
) -> dict:
    job = await joblib.render_and_qa(job_id)
    return job.model_dump()


@app.post("/api/v1/jobs/{job_id}/publish")
async def publish_job(
    job_id: str,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
    _limit: None = Depends(_rate_limit),
) -> dict:
    try:
        job = await joblib.publish_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job.status.value != "PUBLISHED":
        return JSONResponse(job.model_dump(), status_code=409)
    return {
        "status": "published",
        "id": job.published_id,
        "recipe_url": job.recipe_url,
        "card_url": job.card_url,
        "commit_sha": job.commit_sha,
        "repository": "published" if job.commit_sha and not str(job.commit_sha).startswith("local-") else "dry-run",
        "cloudflare": "deployment pending / live after Pages rebuild",
    }


@app.post("/api/v1/jobs/{job_id}/continue-pasted")
async def continue_pasted(
    job_id: str,
    request: Request,
    background: BackgroundTasks,
    _session: AuthSession,
    _csrf: None = Depends(require_csrf),
) -> dict:
    body = await request.json()
    pasted = str(body.get("pasted_source") or "")
    if not pasted.strip():
        raise HTTPException(status_code=400, detail="pasted_source required")
    try:
        job = joblib.load_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found") from None
    (joblib.job_dir(job_id) / "pasted_source.txt").write_text(pasted, encoding="utf-8")
    job.error = None
    joblib.save_job(job)
    background.add_task(joblib.run_pipeline, job_id)
    return {"job_id": job_id, "status": "EXTRACTING"}


def _preview_file(job_id: str, name: str) -> FileResponse:
    path = joblib.job_dir(job_id) / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Preview not ready")
    return FileResponse(path)


@app.get("/api/v1/jobs/{job_id}/preview/front.png")
async def preview_front(job_id: str, _session: AuthSession) -> FileResponse:
    return _preview_file(job_id, "front.png")


@app.get("/api/v1/jobs/{job_id}/preview/back.png")
async def preview_back(job_id: str, _session: AuthSession) -> FileResponse:
    return _preview_file(job_id, "back.png")


@app.get("/api/v1/jobs/{job_id}/preview/card.pdf")
async def preview_card(job_id: str, _session: AuthSession) -> FileResponse:
    work = joblib.job_dir(job_id)
    for name in ("card-working.pdf",):
        path = work / name
        if path.exists():
            return FileResponse(path, media_type="application/pdf")
    # published local name
    matches = list(work.glob("BD-*.pdf"))
    if matches:
        return FileResponse(matches[0], media_type="application/pdf")
    raise HTTPException(status_code=404, detail="Preview not ready")


@app.get("/api/v1/jobs/{job_id}/preview/hero.jpg")
async def preview_hero(job_id: str, _session: AuthSession) -> FileResponse:
    return _preview_file(job_id, "hero-working.jpg")
