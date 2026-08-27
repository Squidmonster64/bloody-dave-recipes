#!/usr/bin/env python3
"""Rebuild docs/Recipe Index.md from canonical recipes.json."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "recipes.json"
INDEX = ROOT / "docs" / "Recipe Index.md"


def _numeric_id(recipe_id: str) -> int:
    match = re.fullmatch(r"BD-(\d+)", str(recipe_id or ""))
    return int(match.group(1)) if match else 10**12


def favourite_label(value) -> str:
    return "Yes" if value is True else "No"


def rebuild_index(payload: dict | None = None) -> str:
    if payload is None:
        payload = json.loads(DATA.read_text(encoding="utf-8"))
    recipes = list(payload.get("recipes", []))
    recipes.sort(key=lambda r: _numeric_id(r.get("id", "")))
    count = len(recipes)
    lines = [
        "# Bloody Dave Recipe Index",
        "",
        f"**Recipes in library:** {count}  ",
        "**Favourite field:** Editable (`Yes` / `No`)",
        "",
        "| Favourite | ID | Recipe | Source | Protein | Cuisine | Time |",
        "|---|---|---|---|---|---|---|",
    ]
    for recipe in recipes:
        lines.append(
            "| {fav} | {id} | {title} | {source} | {protein} | {cuisine} | {time} |".format(
                fav=favourite_label(recipe.get("favourite")),
                id=recipe.get("id", ""),
                title=(recipe.get("title") or "").replace("|", "/"),
                source=(recipe.get("source") or "").replace("|", "/"),
                protein=(recipe.get("protein") or "").replace("|", "/"),
                cuisine=(recipe.get("cuisine") or "").replace("|", "/"),
                time=(recipe.get("total_time") or "").replace("|", "/"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_index(payload: dict | None = None) -> Path:
    text = rebuild_index(payload)
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(text, encoding="utf-8")
    return INDEX


def main() -> int:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    recipes = payload.get("recipes", [])
    if isinstance(payload, dict):
        payload["recipe_count"] = len(recipes)
    path = write_index(payload)
    print(f"OK: wrote {path} with {len(recipes)} recipes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
