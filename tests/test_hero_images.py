#!/usr/bin/env python3
"""Audit published recipe hero assets and image-pipeline wiring."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERO_DIR = ROOT / "assets" / "hero"
OLD_CARTOON_SIZE = 122646


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if data[:2] != b"\xff\xd8":
        raise AssertionError("not a JPEG")
    index = 2
    while index < len(data) - 8:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7 or marker == 0x00:
            index += 2 if marker != 0x00 else 1
            continue
        length = int.from_bytes(data[index + 2 : index + 4], "big")
        if marker in {0xC0, 0xC1, 0xC2}:
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return width, height
        index += 2 + length
    raise AssertionError("JPEG SOF marker not found")


def main() -> int:
    payload = json.loads((ROOT / "recipes.json").read_text(encoding="utf-8"))
    recipes = payload["recipes"]
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    errors: list[str] = []

    ids = [str(recipe["id"]) for recipe in recipes]
    if len(ids) != 41:
        errors.append(f"expected 41 recipes, found {len(ids)}")
    if len(set(ids)) != len(ids):
        errors.append("duplicate recipe IDs in recipes.json")

    hashes: dict[str, str] = {}
    for recipe in recipes:
        recipe_id = str(recipe["id"])
        path = HERO_DIR / f"{recipe_id}.jpg"
        if not path.is_file():
            errors.append(f"{recipe_id}: missing hero file {path.relative_to(ROOT)}")
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in hashes:
            errors.append(f"{recipe_id}: duplicate image bytes also used by {hashes[digest]}")
        hashes[digest] = recipe_id
        if data[:3] != b"\xff\xd8\xff":
            errors.append(f"{recipe_id}: {path.name} is not a JPEG (avoid PNG-as-JPG)")
            continue
        try:
            width, height = jpeg_dimensions(data)
        except AssertionError as exc:
            errors.append(f"{recipe_id}: {exc}")
            continue
        if min(width, height) < 800 or max(width, height) < 1100:
            errors.append(f"{recipe_id}: low-resolution hero {width}x{height}")
        if recipe_id == "BD-0012":
            if path.stat().st_size == OLD_CARTOON_SIZE:
                errors.append("BD-0012 still uses the cartoon recipe-card screenshot")
            if path.stat().st_size < 300_000:
                errors.append("BD-0012 hero is unexpectedly small; expected the meal photograph")
            if digest.startswith("b304174b04a0"):
                errors.append("BD-0012 still hashes to the previous cartoon asset")

    if "heroAssetUrl" not in app or "showCardPlaceholder" not in app:
        errors.append("app.js is missing hero URL helper or image fallback")
    if "image.onerror" not in app or "hero.replaceWith" not in app:
        errors.append("app.js is missing broken-image fallback handlers")
    compacted = re.sub(r"\s+", "", css)
    if "object-fit:cover" not in compacted:
        errors.append("styles.css is missing object-fit:cover")
    if "object-position:var(--hero-focal" not in compacted:
        errors.append("styles.css is missing hero focal object-position")
    if "aspect-ratio:16/10" not in compacted:
        errors.append("styles.css is missing 16/10 hero aspect ratio")
    if "aspect-ratio:16/8" in compacted:
        errors.append("styles.css still uses the overly wide 16/8 detail crop")

    for message in errors:
        print(f"ERROR: {message}")
    if errors:
        return 1

    print(f"OK: {len(recipes)} published recipes resolve unique JPEG hero assets.")
    print("OK: no duplicate hero mappings, JPEG magic, and minimum dimensions.")
    print("OK: BD-0012 is no longer the cartoon card screenshot.")
    print("OK: image component uses object-fit:cover, 16/10 crop and focal overrides.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
