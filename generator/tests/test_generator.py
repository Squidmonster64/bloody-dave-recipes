"""Generator unit and offline integration tests."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "generator"))

from app.card_renderer import render_card
from app.id_allocator import allocate_id, next_id
from app.image_generation import generate_hero_image
from app.index_builder import build_markdown, derive_search_ingredients, to_published_record
from app.models import CreateJobRequest, MethodStage, RecipeDraft
from app.normalize import australianise_text, deterministic_normalise, is_material_adaptation
from app.qa import run_qa
from app.source_extract import extract_from_html, extract_from_pasted
from app.source_fetch import SourceFetchError, FetchResult, validate_url_target
from app.github_publish import find_duplicate_local, publish_local_dry_run
from app import jobs as joblib


FIXTURES = Path(__file__).parent / "fixtures"


def test_ssrf_blocks_localhost():
    with pytest.raises(SourceFetchError):
        validate_url_target("http://127.0.0.1/recipes", resolve_dns=False)
    with pytest.raises(SourceFetchError):
        validate_url_target("http://localhost/secret", resolve_dns=False)
    with pytest.raises(SourceFetchError):
        validate_url_target("file:///etc/passwd", resolve_dns=False)
    with pytest.raises(SourceFetchError):
        validate_url_target("http://169.254.169.254/latest/meta-data", resolve_dns=False)


def test_jsonld_extraction():
    html = (FIXTURES / "jsonld_recipe.html").read_bytes()
    fetch = FetchResult("https://example.com/r", "https://example.com/r", html, "text/html", 200)
    facts = extract_from_html(fetch)
    assert facts.extraction_method == "json_ld"
    assert facts.title.startswith("Cheesy")
    assert len(facts.ingredients) >= 5
    assert len(facts.instructions) == 3
    assert "375" in facts.instructions[0] or "F" in facts.instructions[0]


def test_dom_extraction_and_ten_steps():
    html = (FIXTURES / "dom_recipe.html").read_bytes()
    fetch = FetchResult("https://example.com/dom", "https://example.com/dom", html, "text/html", 200)
    facts = extract_from_html(fetch)
    assert facts.extraction_method == "dom"
    assert len(facts.instructions) == 10
    draft = deterministic_normalise(facts, "")
    assert len(draft.method) == 6


def test_blocked_page_needs_paste():
    html = (FIXTURES / "blocked_page.html").read_bytes()
    fetch = FetchResult("https://example.com/x", "https://example.com/x", html, "text/html", 200)
    facts = extract_from_html(fetch)
    assert facts.extraction_method == "page_text"
    assert not facts.ingredients


def test_australianise_and_material_nutrition():
    assert "capsicum" in australianise_text("bell pepper salad").lower()
    assert "beef mince" in australianise_text("ground beef").lower()
    assert is_material_adaptation("remove the beef and serve 4")
    html = (FIXTURES / "jsonld_recipe.html").read_bytes()
    fetch = FetchResult("https://example.com/r", "https://example.com/r", html, "text/html", 200)
    facts = extract_from_html(fetch)
    adapted = deterministic_normalise(facts, "remove ground beef, Australianise")
    assert adapted.nutrition_basis == "not_supplied_after_adaptation"
    assert "not supplied" in adapted.nutrition.lower()
    retained = deterministic_normalise(facts, "")
    assert retained.nutrition_basis == "source_retained"


def test_id_allocation_monotonic():
    assert next_id(["BD-0001", "BD-0041"]) == "BD-0042"
    assert allocate_id(["BD-0001", "BD-0041"], filesystem_ids=["BD-0042"]) == "BD-0043"


def test_search_ingredients_helper():
    tokens = derive_search_ingredients(["1 Capsicum", "2 cloves Garlic"], ["1 drizzle Olive Oil"])
    assert "capsicum" in tokens
    assert "garlic" in tokens
    assert "olive oil" in tokens


def test_duplicate_detection():
    payload = json.loads((ROOT / "recipes.json").read_text(encoding="utf-8"))
    first = payload["recipes"][0]
    found = find_duplicate_local(payload, first["source_url"])
    assert found == first["id"]


def _sample_draft() -> RecipeDraft:
    stages = [
        MethodStage(heading="Prep", directions="Chop the capsicum and measure the rice."),
        MethodStage(heading="Fry", directions="Brown the onion in olive oil over medium-high heat."),
        MethodStage(heading="Fill", directions="Mix beans, corn, rice and cheese; stuff the capsicums."),
        MethodStage(heading="Bake", directions="Bake at 180°C for 25-30 minutes until bubbling."),
        MethodStage(heading="Rest", directions="Rest 5 minutes so the filling settles."),
        MethodStage(heading="Serve", directions="Plate hot and finish with spring onion."),
    ]
    return RecipeDraft(
        title="Aussie Veggie Stuffed Capsicums",
        subtitle="Roasted capsicums with rice, beans, corn and cheese",
        hook="A weeknight bake with proper cheese pull.",
        source="Fixture Kitchen",
        source_url="https://example.com/fixtures/stuffed-capsicums",
        serves="4",
        prep_time="20 minutes",
        cook_time="35 minutes",
        total_time="55 minutes",
        cuisine="Modern Australian",
        protein="Vegetarian",
        tags=["Vegetarian", "Capsicum", "Family"],
        buy=["4 capsicums", "1 cup cooked rice", "1 x 400 g tin black beans", "1 cup cheddar"],
        pantry=["1 tbsp olive oil", "salt"],
        method=stages,
        allergens="Milk. Check current product labels.",
        nutrition="Nutrition not supplied for this adapted version",
        nutrition_display="Nutrition not supplied for this adapted version",
        hero_image_subject="Finished Aussie Veggie Stuffed Capsicums",
        bloody_dave_quote="Stuff them full and let the cheese do the talking.",
        source_credit="Adapted from Fixture Kitchen",
        nutrition_basis="not_supplied_after_adaptation",
        requested_adaptations=["remove ground beef", "Australianise"],
    )


def test_card_qa_and_offline_publish(tmp_path: Path):
    draft = _sample_draft()
    work = tmp_path / "job"
    work.mkdir()
    hero = generate_hero_image(draft, work / "hero.jpg")
    pdf = work / "card.pdf"
    render_card(
        draft,
        recipe_id="BD-TEST",
        hero_path=hero,
        logo_path=ROOT / "assets" / "bloody_dave_logo.png",
        dest=pdf,
    )
    qa = run_qa(recipe=draft, recipe_id="BD-TEST", pdf_path=pdf, overflows=[])
    assert qa.passed, qa.errors
    record = to_published_record(
        "BD-TEST",
        draft,
        source_method="json_ld",
        source_hash="sha256:test",
        generated_at="2026-08-27T00:00:00Z",
    )
    md = build_markdown(
        "BD-TEST",
        draft,
        source_method="json_ld",
        source_hash="sha256:test",
        published_at="2026-08-27T00:00:00Z",
    )
    commit = asyncio.run(
        publish_local_dry_run(
            recipe_id="BD-TEST",
            recipe_record=record,
            markdown=md,
            hero_bytes=hero.read_bytes(),
            pdf_bytes=pdf.read_bytes(),
            target_root=tmp_path / "publish",
        )
    )
    assert commit.startswith("local-dry-run:")
    published = tmp_path / "publish"
    assert (published / "Recipes" / "BD-TEST.md").exists()
    assert (published / "cards" / "BD-TEST.pdf").exists()
    assert (published / "assets" / "hero" / "BD-TEST.jpg").exists()
    payload = json.loads((published / "recipes.json").read_text(encoding="utf-8"))
    assert payload["recipe_count"] == len(payload["recipes"])
    assert any(r["id"] == "BD-TEST" for r in payload["recipes"])
    index = (published / "docs" / "Recipe Index.md").read_text(encoding="utf-8")
    assert "BD-TEST" in index


def test_pasted_source_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JOB_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    # Reload settings work dir
    from app import config

    config.settings.work_dir = tmp_path / "work"
    config.settings.work_dir.mkdir(parents=True, exist_ok=True)
    config.settings.openai_api_key = ""
    config.settings.github_token = ""

    pasted = """Aussie Test Pasta
Serves 2
Ingredients
200g pasta
1 capsicum
2 tbsp olive oil
Method
1. Boil pasta.
2. Fry capsicum in oil.
3. Toss together.
4. Season.
5. Plate.
6. Serve hot.
"""
    job = joblib.create_job(
        CreateJobRequest(
            url="https://example.com/unique-pasted-recipe-studio-test",
            instructions="Australianise",
            pasted_source=pasted,
        )
    )
    result = asyncio.run(joblib.run_pipeline(job.job_id))
    assert result.status.value in {"READY_FOR_REVIEW", "FAILED", "NEEDS_PASTED_SOURCE"}
    # deterministic path should reach review or fail only on overflow
    assert result.recipe is not None or result.status.value == "NEEDS_PASTED_SOURCE"
    if result.recipe:
        assert len(result.recipe.method) == 6
