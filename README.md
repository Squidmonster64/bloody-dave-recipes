# Bloody Dave's Recipes PWA

Production static PWA:

`https://recipes.bloodydaves.com`

Canonical library lives in this GitHub repository. Cloudflare Pages deploys the public app from `main`.

## Library

- Canonical data: `recipes.json`
- Markdown references: `Recipes/BD-####.md`
- Printable cards: `cards/BD-####.pdf`
- Hero images: `assets/hero/BD-####.jpg`
- Human index: `docs/Recipe Index.md` (generated)

`recipe_count` is always derived from `recipes.length`. The historical library of 41 recipes remains intact; new recipes are appended with the next permanent `BD-####` ID.

## Recipe Studio (add recipes)

New recipes are created through the private Recipe Studio service:

`https://studio.recipes.bloodydaves.com`

Flow:

1. Paste recipe URL
2. Optional natural-language changes ("remove the beef", "Australianise", "serve 4")
3. Generate → review/edit → Publish
4. Studio writes one atomic Git commit containing JSON, Markdown, hero JPG, PDF card and rebuilt index
5. Cloudflare Pages redeploys; the recipe appears in the live PWA

Secrets (`OPENAI_API_KEY`, `GITHUB_TOKEN`, session/password material) stay server-side. See `docs/RECIPE_STUDIO.md` and `generator/`.

The old static promotion JSON download/merge workflow is retired for new recipes.

## App functions

- Browse curated recipes
- Search title, ingredient, cuisine, source, protein, tag, ID and cooking time
- Favourites, sorting and hash-addressable detail pages (`#recipe/BD-0001`)
- Multi-select shopping list with Have/Need and pantry defaults
- Weekly planning and suite hand-offs
- Installable PWA with offline shell; recipe/card/hero assets use runtime caching

## Run locally

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## Validate

```bash
python3 scripts/validate_data.py
python3 scripts/rebuild_recipe_index.py
node --check app.js
node --check sw.js
node tests/test_data_logic.js
python3 tests/test_static_files.py
python3 -m pytest generator/tests -q
```

## Contact

`info@bloodydaves.com`
