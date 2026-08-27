"""Index and markdown helpers shared with scripts/."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from .config import settings
from .models import RecipeDraft


def _load_script(name: str):
    path = settings.repo_root / "scripts" / name
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def derive_search_ingredients(buy: list[str], pantry: list[str]) -> list[str]:
    mod = _load_script("search_ingredients.py")
    return mod.derive_search_ingredients(buy, pantry)


def rebuild_index_text(payload: dict[str, Any]) -> str:
    mod = _load_script("rebuild_recipe_index.py")
    return mod.rebuild_index(payload)


def build_markdown(recipe_id: str, recipe: RecipeDraft, *, source_method: str, source_hash: str, published_at: str) -> str:
    adaptations = recipe.requested_adaptations or ["None"]
    buy = "\n".join(f"- {item}" for item in recipe.buy) or "- None"
    pantry = "\n".join(f"- {item}" for item in recipe.pantry) or "- None"
    method_blocks = []
    for i, stage in enumerate(recipe.method, start=1):
        method_blocks.append(f"### {i}. {stage.heading}\n{stage.directions}\n")
    return f"""# {recipe_id} — {recipe.title}

## Status
- Library status: Generated
- QA status: Passed
- Published: {published_at}

## Source
- Publisher: {recipe.source}
- URL: {recipe.source_url}
- Source retrieval: {source_method}
- Source hash: {source_hash}

## Requested adaptations
{chr(10).join(f'- {item}' for item in adaptations)}

## Recipe
**Serves:** {recipe.serves}
**Prep:** {recipe.prep_time}
**Cook:** {recipe.cook_time}
**Total:** {recipe.total_time}
**Cuisine:** {recipe.cuisine}
**Protein/category:** {recipe.protein}

### Buy
{buy}

### Pantry
{pantry}

## Method

{chr(10).join(method_blocks)}
## Nutrition
{recipe.nutrition_display or recipe.nutrition}

## Allergens
{recipe.allergens}

## Source credit
{recipe.source_credit}

## Generation notes
- Generator: {settings.generator_version}
- Nutrition basis: {recipe.nutrition_basis}
- Image: original generated hero
- Card: cards/{recipe_id}.pdf
- Quote: {recipe.bloody_dave_quote}
"""


def to_published_record(recipe_id: str, recipe: RecipeDraft, *, source_method: str, source_hash: str, generated_at: str) -> dict[str, Any]:
    record = {
        "id": recipe_id,
        "title": recipe.title,
        "subtitle": recipe.subtitle,
        "source": recipe.source,
        "source_url": recipe.source_url,
        "serves": recipe.serves,
        "prep_time": recipe.prep_time,
        "cook_time": recipe.cook_time,
        "total_time": recipe.total_time,
        "cuisine": recipe.cuisine,
        "protein": recipe.protein,
        "difficulty": recipe.difficulty,
        "tags": recipe.tags,
        "favourite": True,
        "library_status": "generated",
        "reference_file": f"Recipes/{recipe_id}.md",
        "buy": recipe.buy,
        "pantry": recipe.pantry,
        "method": recipe.method_texts(),
        "allergens": recipe.allergens,
        "nutrition": recipe.nutrition,
        "nutrition_table": recipe.nutrition_table,
        "nutrition_display": recipe.nutrition_display,
        "hero_image_subject": recipe.hero_image_subject,
        "search_ingredients": derive_search_ingredients(recipe.buy, recipe.pantry),
        "source_credit": recipe.source_credit,
        "final_review_status": "GENERATED + QA PASSED",
        "generation": {
            "generator_version": settings.generator_version,
            "generated_at": generated_at,
            "source_fetch_method": source_method,
            "source_hash": source_hash,
            "requested_adaptations": recipe.requested_adaptations,
            "nutrition_basis": recipe.nutrition_basis,
            "card_version": settings.card_version,
            "bloody_dave_quote": recipe.bloody_dave_quote,
            "hook": recipe.hook,
        },
    }
    if recipe.variant_of:
        record["variant_of"] = recipe.variant_of
    return record
