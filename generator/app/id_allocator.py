"""Permanent BD ID allocation against canonical library state."""
from __future__ import annotations

import re
from typing import Iterable


ID_RE = re.compile(r"^BD-(\d+)$")


def parse_numeric_ids(ids: Iterable[str]) -> list[int]:
    out: list[int] = []
    for value in ids:
        match = ID_RE.fullmatch(str(value or ""))
        if match:
            out.append(int(match.group(1)))
    return out


def next_id(existing_ids: Iterable[str]) -> str:
    numbers = parse_numeric_ids(existing_ids)
    nxt = (max(numbers) + 1) if numbers else 1
    return f"BD-{nxt:04d}"


def id_available(recipe_id: str, *, recipes_json_ids: set[str], markdown_ids: set[str], card_ids: set[str], hero_ids: set[str]) -> bool:
    return recipe_id not in recipes_json_ids and recipe_id not in markdown_ids and recipe_id not in card_ids and recipe_id not in hero_ids


def allocate_id(existing_recipe_ids: Iterable[str], *, filesystem_ids: Iterable[str] | None = None) -> str:
    used = set(existing_recipe_ids) | set(filesystem_ids or [])
    candidate = next_id(used)
    # Never reuse holes: always max+1 against the union of known IDs.
    while candidate in used:
        n = int(candidate.split("-", 1)[1]) + 1
        candidate = f"BD-{n:04d}"
    return candidate
