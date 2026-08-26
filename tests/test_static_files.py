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

required_ids = {
    "libraryView", "archiveView", "shoppingView", "detailView", "librarySearch",
    "favouritesOnly", "timeFilter", "libraryGrid", "archiveGrid", "needList",
    "haveList", "pantryList", "recipeDetail", "installBtn"
}
found_ids = set(re.findall(r'id="([^"]+)"', html))
missing = sorted(required_ids - found_ids)
assert not missing, f"Missing HTML IDs: {missing}"

assert len(recipes) == 41
for recipe in recipes:
    reference = recipe["reference_file"]
    assert (ROOT / reference).is_file(), reference
    assert f'"{reference}"' in sw, f"Reference not precached: {reference}"

assert "Archive/index.json" in (ROOT / "app.js").read_text(encoding="utf-8")
assert not (ROOT / "Archive" / "index.json").exists(), "Archive must remain optional in this build"

css = (ROOT / "styles.css").read_text(encoding="utf-8")
assert ".card-image{" in css.replace(" ", "") or "object-fit:cover" in css.replace(" ", "")
assert "object-fit:cover" in css.replace(" ", "")
assert "object-position:var(--hero-focal" in css.replace(" ", "")
assert "aspect-ratio:16/10" in css.replace(" ", "")
assert "aspect-ratio:16/8" not in css.replace(" ", "")

app = (ROOT / "app.js").read_text(encoding="utf-8")
assert "function showCardPlaceholder" in app
assert "image.onerror" in app
assert "hero.replaceWith" in app

print("OK: application shell, 41 Markdown references, offline cache list and optional archive structure.")
print("OK: hero image components use object-fit cover with focal overrides and fallbacks.")
