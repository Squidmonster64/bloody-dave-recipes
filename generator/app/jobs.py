"""Job storage and pipeline orchestration."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .card_renderer import CardRenderError, render_card
from .config import settings
from .github_publish import (
    PublishError,
    allocate_from_github,
    find_duplicate_local,
    load_local_snapshot,
    publish_atomic,
)
from .id_allocator import allocate_id
from .image_generation import generate_hero_image
from .index_builder import build_markdown, to_published_record
from .models import CreateJobRequest, JobRecord, JobStatus, PatchRecipeRequest, QAResult
from .normalize import ai_normalise, apply_patch
from .qa import render_previews, run_qa
from .source_extract import extract_from_html, extract_from_pasted
from .source_fetch import SourceFetchError, fetch_source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_dir(job_id: str) -> Path:
    path = settings.work_dir / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_job(job: JobRecord) -> None:
    path = job_dir(job.job_id) / "job.json"
    path.write_text(job.model_dump_json(indent=2), encoding="utf-8")


def load_job(job_id: str) -> JobRecord:
    path = job_dir(job_id) / "job.json"
    if not path.exists():
        raise FileNotFoundError(job_id)
    return JobRecord.model_validate_json(path.read_text(encoding="utf-8"))


def cleanup_old_jobs() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.job_retention_days)
    removed = 0
    for path in settings.work_dir.iterdir():
        if not path.is_dir():
            continue
        job_file = path / "job.json"
        if not job_file.exists():
            continue
        try:
            job = JobRecord.model_validate_json(job_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if job.status == JobStatus.PUBLISHED:
            continue
        created = datetime.fromisoformat(job.created_at.replace("Z", "+00:00"))
        if created < cutoff:
            shutil.rmtree(path, ignore_errors=True)
            removed += 1
    return removed


def create_job(payload: CreateJobRequest) -> JobRecord:
    job = JobRecord(
        job_id=str(uuid.uuid4()),
        status=JobStatus.QUEUED,
        created_at=_now(),
        updated_at=_now(),
        url=payload.url.strip(),
        instructions=payload.instructions.strip(),
        create_variant=payload.create_variant,
        progress="Queued",
    )
    save_job(job)
    if payload.pasted_source.strip():
        (job_dir(job.job_id) / "pasted_source.txt").write_text(payload.pasted_source, encoding="utf-8")
    return job


async def run_pipeline(job_id: str) -> JobRecord:
    job = load_job(job_id)
    work = job_dir(job_id)
    pasted = ""
    pasted_path = work / "pasted_source.txt"
    if pasted_path.exists():
        pasted = pasted_path.read_text(encoding="utf-8")

    try:
        # Duplicate check against local/canonical catalogue early.
        snap = load_local_snapshot()
        candidate_id = allocate_id(
            [str(r.get("id")) for r in snap.recipes_payload.get("recipes", [])],
            filesystem_ids=snap.markdown_ids | snap.card_ids | snap.hero_ids,
        )
        job.candidate_id = candidate_id

        if not pasted:
            job.touch(JobStatus.FETCHING_SOURCE, "Fetching source page")
            save_job(job)
            try:
                fetched = await fetch_source(job.url)
            except SourceFetchError as exc:
                job.touch(JobStatus.NEEDS_PASTED_SOURCE, str(exc))
                job.error = (
                    "We couldn't reliably read this recipe page. Paste the recipe text below to continue."
                )
                save_job(job)
                return job
            (work / "source.html").write_bytes(fetched.content)
            job.touch(JobStatus.EXTRACTING, "Extracting recipe facts")
            save_job(job)
            source = extract_from_html(fetched, pasted_fallback="")
            if not (source.ingredients and source.instructions) and source.extraction_method in {"page_text", "none"}:
                job.source = source
                job.touch(JobStatus.NEEDS_PASTED_SOURCE, "Source page lacked a reliable recipe structure")
                job.error = (
                    "We couldn't reliably read this recipe page. Paste the recipe text below to continue."
                )
                save_job(job)
                return job
        else:
            job.touch(JobStatus.EXTRACTING, "Using pasted recipe text")
            save_job(job)
            source = extract_from_pasted(job.url, pasted)

        (work / "source.json").write_text(source.model_dump_json(indent=2), encoding="utf-8")
        job.source = source

        dup = find_duplicate_local(
            snap.recipes_payload,
            source.resolved_url or job.url,
            title=source.title,
            source=source.publisher,
        )
        if dup and not job.create_variant:
            job.duplicate_of = dup
            job.touch(JobStatus.FAILED, f"Already in library: {dup}")
            job.error = f"This source is already in the library as {dup}."
            save_job(job)
            return job
        if dup and job.create_variant:
            # Continue as intentional variant.
            pass

        job.touch(JobStatus.NORMALISING, "Normalising and adapting recipe")
        save_job(job)
        recipe = ai_normalise(source, job.instructions)
        if job.create_variant and dup:
            recipe.variant_of = dup
            if recipe.title == source.title:
                recipe.title = f"{recipe.title} (variant)"
        job.recipe = recipe

        job.touch(JobStatus.GENERATING_IMAGE, "Generating hero image")
        save_job(job)
        hero_path = generate_hero_image(recipe, work / "hero-working.jpg")

        job.touch(JobStatus.RENDERING_CARD, "Rendering printable card")
        save_job(job)
        logo = settings.repo_root / "assets" / "bloody_dave_logo.png"
        overflows: list[str] = []
        try:
            render_card(
                recipe,
                recipe_id=candidate_id,
                hero_path=hero_path,
                logo_path=logo,
                dest=work / "card-working.pdf",
            )
        except CardRenderError as exc:
            overflows = exc.overflows
            # Keep PDF for review even when overflow QA will fail.
            if not (work / "card-working.pdf").exists():
                raise

        job.touch(JobStatus.QA, "Running card QA")
        save_job(job)
        front = work / "front.png"
        back = work / "back.png"
        try:
            render_previews(work / "card-working.pdf", front, back)
        except Exception as exc:
            job.qa = QAResult(passed=False, errors=[f"preview_render: {exc}"])
            job.touch(JobStatus.FAILED, "Preview render failed")
            job.error = str(exc)
            save_job(job)
            return job

        qa = run_qa(
            recipe=recipe,
            recipe_id=candidate_id,
            pdf_path=work / "card-working.pdf",
            overflows=overflows,
            front_png=front,
            back_png=back,
        )
        (work / "qa.json").write_text(qa.model_dump_json(indent=2), encoding="utf-8")
        job.qa = qa
        if not qa.passed:
            job.touch(JobStatus.FAILED, "QA failed")
            job.error = "; ".join(qa.errors) or "Card layout failed QA."
            save_job(job)
            return job

        job.touch(JobStatus.READY_FOR_REVIEW, "Ready for review")
        job.error = None
        save_job(job)
        return job
    except Exception as exc:
        job.touch(JobStatus.FAILED, "Pipeline failed")
        job.error = str(exc)
        save_job(job)
        return job


async def patch_recipe(job_id: str, patch: PatchRecipeRequest) -> JobRecord:
    job = load_job(job_id)
    if not job.recipe:
        raise ValueError("No recipe draft to patch")
    job.recipe = apply_patch(job.recipe, patch.model_dump(exclude_unset=True))
    job.touch(progress="Recipe edited — re-run render/QA before publish")
    save_job(job)
    return job


async def regenerate_image(job_id: str) -> JobRecord:
    job = load_job(job_id)
    if not job.recipe:
        raise ValueError("No recipe draft")
    job.touch(JobStatus.GENERATING_IMAGE, "Regenerating hero image")
    save_job(job)
    generate_hero_image(job.recipe, job_dir(job_id) / "hero-working.jpg")
    return await render_and_qa(job_id)


async def render_and_qa(job_id: str) -> JobRecord:
    job = load_job(job_id)
    if not job.recipe:
        raise ValueError("No recipe draft")
    work = job_dir(job_id)
    candidate = job.candidate_id or "BD-TEST"
    job.touch(JobStatus.RENDERING_CARD, "Rendering printable card")
    save_job(job)
    overflows: list[str] = []
    try:
        render_card(
            job.recipe,
            recipe_id=candidate,
            hero_path=work / "hero-working.jpg",
            logo_path=settings.repo_root / "assets" / "bloody_dave_logo.png",
            dest=work / "card-working.pdf",
        )
    except CardRenderError as exc:
        overflows = exc.overflows
    job.touch(JobStatus.QA, "Running card QA")
    save_job(job)
    front = work / "front.png"
    back = work / "back.png"
    render_previews(work / "card-working.pdf", front, back)
    qa = run_qa(
        recipe=job.recipe,
        recipe_id=candidate,
        pdf_path=work / "card-working.pdf",
        overflows=overflows,
        front_png=front,
        back_png=back,
    )
    job.qa = qa
    if qa.passed:
        job.touch(JobStatus.READY_FOR_REVIEW, "Ready for review")
        job.error = None
    else:
        job.touch(JobStatus.FAILED, "QA failed")
        job.error = "; ".join(qa.errors)
    save_job(job)
    return job


async def publish_job(job_id: str) -> JobRecord:
    job = load_job(job_id)
    if not job.recipe or not job.source:
        raise ValueError("Job is incomplete")
    if not job.qa or not job.qa.passed:
        raise ValueError("QA must pass before publish")

    job.touch(JobStatus.PUBLISHING, "Allocating ID and publishing")
    save_job(job)
    work = job_dir(job_id)

    recipe_id, snap = await allocate_from_github()
    # Re-check duplicate at publish time.
    dup = find_duplicate_local(
        snap.recipes_payload,
        job.recipe.source_url,
        title=job.recipe.title,
        source=job.recipe.source,
    )
    if dup and not job.create_variant and not job.recipe.variant_of:
        job.touch(JobStatus.FAILED, f"Already in library: {dup}")
        job.error = f"This source is already in the library as {dup}."
        save_job(job)
        return job
    if job.create_variant and dup:
        job.recipe.variant_of = dup

    # Finalise artifacts with permanent ID.
    generate_hero_image(job.recipe, work / f"{recipe_id}.jpg")  # ensure jpg exists; prefer working hero
    hero_working = work / "hero-working.jpg"
    hero_final = work / f"{recipe_id}.jpg"
    if hero_working.exists():
        hero_final.write_bytes(hero_working.read_bytes())

    overflows: list[str] = []
    try:
        render_card(
            job.recipe,
            recipe_id=recipe_id,
            hero_path=hero_final,
            logo_path=settings.repo_root / "assets" / "bloody_dave_logo.png",
            dest=work / f"{recipe_id}.pdf",
        )
    except CardRenderError as exc:
        overflows = exc.overflows
        job.touch(JobStatus.FAILED, "Final card overflow")
        job.error = "Card layout failed QA. Edit the flagged section or regenerate. No library changes were made."
        job.qa = QAResult(passed=False, errors=overflows)
        save_job(job)
        return job

    render_previews(work / f"{recipe_id}.pdf", work / "front.png", work / "back.png")
    qa = run_qa(
        recipe=job.recipe,
        recipe_id=recipe_id,
        pdf_path=work / f"{recipe_id}.pdf",
        overflows=overflows,
        front_png=work / "front.png",
        back_png=work / "back.png",
    )
    job.qa = qa
    if not qa.passed:
        job.touch(JobStatus.FAILED, "Final QA failed")
        job.error = "; ".join(qa.errors)
        save_job(job)
        return job

    generated_at = _now()
    record = to_published_record(
        recipe_id,
        job.recipe,
        source_method=job.source.extraction_method,
        source_hash=job.source.source_hash,
        generated_at=generated_at,
    )
    markdown = build_markdown(
        recipe_id,
        job.recipe,
        source_method=job.source.extraction_method,
        source_hash=job.source.source_hash,
        published_at=generated_at,
    )
    try:
        commit = await publish_atomic(
            recipe_id=recipe_id,
            recipe_record=record,
            markdown=markdown,
            hero_bytes=hero_final.read_bytes(),
            pdf_bytes=(work / f"{recipe_id}.pdf").read_bytes(),
            expected_parent_sha=snap.commit_sha if snap.commit_sha != "local" else None,
        )
    except PublishError as exc:
        job.touch(JobStatus.FAILED, "Publish failed")
        job.error = str(exc)
        save_job(job)
        return job

    job.published_id = recipe_id
    job.commit_sha = commit
    job.recipe_url = f"{settings.public_recipes_url}#recipe/{recipe_id}"
    job.card_url = f"{settings.public_recipes_url}/cards/{recipe_id}.pdf"
    job.touch(JobStatus.PUBLISHED, f"Published {recipe_id}")
    save_job(job)
    return job
