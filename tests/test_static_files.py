#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
payload = json.loads((ROOT / "recipes.json").read_text(encoding="utf-8"))
recipes = payload["recipes"]
html = (ROOT / "index.html").read_text(encoding="utf-8")
sw = (ROOT / "sw.js").read_text(encoding="utf-8")
app = (ROOT / "app.js").read_text(encoding="utf-8")

required_ids = {
    "libraryView", "archiveView", "shoppingView", "detailView", "librarySearch",
    "favouritesOnly", "timeFilter", "libraryGrid", "archiveGrid", "needList",
    "haveList", "pantryList", "recipeDetail", "installBtn"
}
found_ids = set(re.findall(r'id="([^"]+)"', html))
missing = sorted(required_ids - found_ids)
assert not missing, f"Missing HTML IDs: {missing}"

assert len(recipes) >= 41
assert payload.get("recipe_count") == len(recipes)
for recipe in recipes:
    reference = recipe["reference_file"]
    assert (ROOT / reference).is_file(), reference
    hero = ROOT / "assets" / "hero" / f"{recipe['id']}.jpg"
    card = ROOT / "cards" / f"{recipe['id']}.pdf"
    assert hero.is_file(), hero
    assert card.is_file(), card

assert "Recipes/BD-0001.md" not in sw, "Markdown references must not be hard-coded into the service-worker precache"
assert "assets/bloody_dave_logo.png" in sw
assert "recipes.json" in sw
assert "Archive/index.json" in app
assert not (ROOT / "Archive" / "index.json").exists(), "Archive must remain optional in this build"
assert "studio.recipes.bloodydaves.com" in html or "Recipe Studio" in html
print(f"OK: application shell, {len(recipes)} Markdown/hero/card assets, scalable offline cache and optional archive structure.")
