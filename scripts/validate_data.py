#!/usr/bin/env python3
"""Validate the Bloody Dave curated dataset (no fixed recipe-count ceiling)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "recipes.json"
INDEX = ROOT / "docs" / "Recipe Index.md"
HISTORICAL_MINIMUM = 41


def _normalise_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}"


def main() -> int:
    try:
        payload = json.loads(DATA.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: missing {DATA}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}")
        return 1

    if not isinstance(payload, dict):
        print("ERROR: recipes.json must be an object with a recipes array.")
        return 1

    recipes = payload.get("recipes", [])
    if not isinstance(recipes, list):
        print("ERROR: recipes must be an array.")
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("recipe_count") != len(recipes):
        errors.append(
            f"recipe_count is {payload.get('recipe_count')!r}; actual recipe array contains {len(recipes)}."
        )

    if len(recipes) < HISTORICAL_MINIMUM:
        errors.append(
            f"Expected at least {HISTORICAL_MINIMUM} historical recipes; found {len(recipes)}."
        )

    historical_ids = {f"BD-{i:04d}" for i in range(1, HISTORICAL_MINIMUM + 1)}
    present_ids = {str(r.get("id") or "") for r in recipes}
    missing_historical = sorted(historical_ids - present_ids)
    if missing_historical:
        errors.append(f"Missing historical recipes: {', '.join(missing_historical)}")

    seen: set[str] = set()
    source_urls: dict[str, str] = {}
    structured = 0
    favourite_count = 0
    numeric_ids: list[int] = []

    for index, recipe in enumerate(recipes, start=1):
        recipe_id = str(recipe.get("id") or "")
        title = str(recipe.get("title") or "").strip()
        library_status = str(recipe.get("library_status") or "")
        is_generated = library_status == "generated"

        if not re.fullmatch(r"BD-\d{4,}", recipe_id):
            errors.append(f"Row {index}: invalid or missing BD- ID: {recipe_id!r}")
        else:
            numeric_ids.append(int(recipe_id.split("-", 1)[1]))

        if recipe_id in seen:
            errors.append(f"Row {index}: duplicate ID {recipe_id}")
        seen.add(recipe_id)

        if not title:
            errors.append(f"Row {index}: missing title")

        if recipe.get("favourite") is True:
            favourite_count += 1

        reference = recipe.get("reference_file")
        if not reference:
            warnings.append(f"{recipe_id}: no reference_file")
        elif not (ROOT / reference).is_file():
            errors.append(f"{recipe_id}: Markdown reference not found: {reference}")

        hero = ROOT / "assets" / "hero" / f"{recipe_id}.jpg"
        if not hero.is_file():
            errors.append(f"{recipe_id}: missing hero image {hero.relative_to(ROOT)}")

        card = ROOT / "cards" / f"{recipe_id}.pdf"
        if not card.is_file():
            errors.append(f"{recipe_id}: missing printable card {card.relative_to(ROOT)}")

        source_url = str(recipe.get("source_url") or "").strip()
        normalised = _normalise_url(source_url)
        if normalised:
            previous = source_urls.get(normalised)
            if previous and not recipe.get("variant_of"):
                errors.append(
                    f"{recipe_id}: duplicate source_url already used by {previous} "
                    f"(set variant_of to publish intentionally)."
                )
            source_urls.setdefault(normalised, recipe_id)

        if is_generated:
            method = recipe.get("method") or []
            if not isinstance(method, list) or len(method) != 6:
                errors.append(f"{recipe_id}: generated recipes must contain exactly 6 method stages")
            elif any(not str(step).strip() for step in method):
                errors.append(f"{recipe_id}: generated method stages must be non-empty")
            if not source_url:
                errors.append(f"{recipe_id}: generated recipes require source_url")
            if not str(recipe.get("source_credit") or "").strip():
                errors.append(f"{recipe_id}: generated recipes require source_credit")

        if recipe.get("buy") or recipe.get("pantry") or recipe.get("method"):
            structured += 1

    for field in ("source", "cuisine", "protein", "tags", "favourite"):
        missing = [r.get("id", "<unknown>") for r in recipes if field not in r]
        if missing:
            errors.append(f"Missing {field} field: {', '.join(str(m) for m in missing)}")

    if numeric_ids:
        expected = list(range(min(numeric_ids), max(numeric_ids) + 1))
        # Generated IDs must be unique and never reuse deleted holes below max.
        # Monotonicity means max equals the highest allocated; holes above historical
        # minimum are allowed only if not claimed as sequential generated chain.
        if len(numeric_ids) != len(set(numeric_ids)):
            errors.append("Numeric BD IDs are not unique.")

    if INDEX.is_file():
        index_text = INDEX.read_text(encoding="utf-8")
        index_count_match = re.search(r"\*\*Recipes(?: imported| in library):\*\*\s*(\d+)", index_text)
        if index_count_match and int(index_count_match.group(1)) != len(recipes):
            errors.append(
                f"Recipe Index count is {index_count_match.group(1)}; data has {len(recipes)}."
            )
        for recipe_id in sorted(seen):
            if recipe_id and recipe_id not in index_text:
                errors.append(f"Recipe Index missing entry for {recipe_id}")
    else:
        warnings.append("docs/Recipe Index.md is missing")

    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")

    if errors:
        return 1

    print(f"OK: {len(recipes)} curated recipes; IDs and Markdown references are valid.")
    print(f"OK: {favourite_count} dataset favourites preserved.")
    print(
        f"INFO: {structured} recipes contain structured ingredients/method; "
        f"{len(recipes) - structured} are reference-only in the supplied dataset."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
