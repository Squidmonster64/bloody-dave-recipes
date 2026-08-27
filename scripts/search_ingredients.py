#!/usr/bin/env python3
"""Derive search_ingredients tokens from buy/pantry lists."""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_QTY_PREFIX = re.compile(
    r"""^\s*
    (?:
      \d+\s*[/x×]\s*\d+ |
      \d+(?:[./]\d+)? |
      \d+\s*-\s*\d+
    )
    \s*
    (?:
      cups|cup|tbsp|tsp|kg|ml|g|l|
      cloves|clove|packets|packet|tins|tin|cans|can|
      bunches|bunch|pinches|pinch|drizzles|drizzle|drizz?le|splash|
      knobs|knob|slices|slice|pieces|piece|sheets|sheet|
      sachets|sachet|handfuls|handful|sprigs|sprig|leaves|leaf
    )?
    \s*
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PACK_NOISE = re.compile(
    r"\b(?:packet|packets|sachet|sachets|tin|tins|can|cans|jar|jars|"
    r"bottle|bottles|bag|bags|bunch|bunches|pack|packs)\b",
    re.IGNORECASE,
)

_MULTI_SPACE = re.compile(r"\s+")


def _strip_accents(text: str) -> str:
    normalised = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalised if not unicodedata.combining(ch))


def tokenise_ingredient(raw: str) -> str:
    text = _strip_accents(str(raw or "")).lower().strip()
    text = text.replace("×", "x")
    text = _QTY_PREFIX.sub("", text)
    text = _PACK_NOISE.sub(" ", text)
    text = re.sub(r"[^\w\s'-]", " ", text)
    text = _MULTI_SPACE.sub(" ", text).strip(" -'")
    return text


def derive_search_ingredients(buy: Iterable[str] | None, pantry: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in list(buy or []) + list(pantry or []):
        token = tokenise_ingredient(item)
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "recipes.json").read_text(encoding="utf-8"))
    for recipe in payload["recipes"]:
        recipe["search_ingredients"] = derive_search_ingredients(
            recipe.get("buy"), recipe.get("pantry")
        )
    if "--write" in sys.argv:
        (root / "recipes.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"Updated search_ingredients for {len(payload['recipes'])} recipes.")
    else:
        print(json.dumps(derive_search_ingredients(["1 Capsicum", "2 cloves Garlic"], ["1 drizzle Olive Oil"]), indent=2))
