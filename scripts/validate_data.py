#!/usr/bin/env python3
"""Validate the deployed Bloody Dave curated dataset."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "recipes.json"
EXPECTED_COUNT = 41


def main() -> int:
    try:
        payload = json.loads(DATA.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: missing {DATA}")
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}")
        return 1

    recipes = payload if isinstance(payload, list) else payload.get("recipes", [])
    errors: list[str] = []
    warnings: list[str] = []

    if len(recipes) != EXPECTED_COUNT:
        errors.append(f"Expected {EXPECTED_COUNT} recipes; found {len(recipes)}.")
    if isinstance(payload, dict) and payload.get("recipe_count") != len(recipes):
        errors.append(
            f"recipe_count is {payload.get('recipe_count')!r}; actual recipe array contains {len(recipes)}."
        )

    seen: set[str] = set()
    structured = 0
    favourite_count = 0
    for index, recipe in enumerate(recipes, start=1):
        recipe_id = str(recipe.get("id") or "")
        title = str(recipe.get("title") or "").strip()
        if not re.fullmatch(r"BD-\d{4,}", recipe_id):
            errors.append(f"Row {index}: invalid or missing BD- ID: {recipe_id!r}")
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
        if recipe.get("buy") or recipe.get("pantry") or recipe.get("method"):
            structured += 1

    for field in ("source", "cuisine", "protein", "tags", "favourite"):
        missing = [r.get("id", "<unknown>") for r in recipes if field not in r]
        if missing:
            errors.append(f"Missing {field} field: {', '.join(missing)}")

    for message in errors:
        print(f"ERROR: {message}")
    for message in warnings:
        print(f"WARNING: {message}")

    if errors:
        return 1
    print(f"OK: {len(recipes)} curated recipes; IDs and Markdown references are valid.")
    print(f"OK: {favourite_count} dataset favourites preserved.")
    print(f"INFO: {structured} recipes contain structured ingredients/method; {len(recipes)-structured} are reference-only in the supplied dataset.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
