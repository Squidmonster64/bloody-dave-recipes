# Bloody Dave's Recipes PWA — Build 4

Production-ready static PWA for:

`https://recipes.bloodydaves.com`

## Live starting library

This build contains the supplied current dataset unchanged:

- 41 curated recipes in `recipes.json`
- stable IDs `BD-0001` through `BD-0041`
- all 41 supplied favourite values preserved as `true`
- 41 supporting Markdown files in `Recipes/`
- no dependency on `Archive/index.json`

## Current dataset coverage

The application does not invent missing recipe details.

- All 41 recipes contain structured buy/pantry ingredient lists and methods in the live `recipes.json` payload.
- All 41 can contribute ingredients to a combined shopping list.
- Supporting Markdown references remain bundled for traceability and offline access.

The app displays this limitation where it matters rather than silently filling gaps.

## Functions

- Browse all curated recipes
- Search title, ingredient, cuisine, source, protein, tag, ID and recorded cooking time
- Filter and toggle favourites
- Sort by ID, title, cooking time or source
- Open hash-addressable recipe detail pages
- Load the supporting Markdown reference for each recipe
- Select multiple recipes
- Merge duplicate ingredients and compatible quantities
- Separate pantry items
- Mark every item Have or Need
- Pantry items default to Have but can be switched to Need
- Print or export the Need list
- Install on iPhone, iPad and Mac
- Work offline after the first complete load
- Load a future `Archive/index.json` without changing application code
- Search the optional archive and prepare local promotions with the next sequential BD ID

## Run locally

A local web server is required because browsers do not allow PWA service workers from a file opened directly in Finder.

```bash
cd bloody-dave-recipes-pwa-build-3
python3 -m http.server 8080
```

Open:

```text
http://localhost:8080
```

## Validate before deployment

```bash
python3 scripts/validate_data.py
node --check app.js
node --check sw.js
node tests/test_data_logic.js
python3 tests/test_static_files.py
python3 tests/test_hero_images.py
```

## Archive later

Add the completed archive using this structure:

```text
Archive/
├── index.json
├── recipes/
└── images/          # optional
```

Publish the added files and reload the PWA. No application-code rebuild is required.

## Static promotion limitation

A static PWA cannot directly rewrite the deployed `recipes.json`. Archive promotion therefore:

1. assigns the next sequential `BD-` ID;
2. stores the promotion locally on the current device;
3. downloads `bloody-dave-promotions.json`;
4. requires those records to be merged into the source `recipes.json` for permanent cross-device publication.

## Contact

`info@bloodydaves.com`

### Printable recipe cards

Each curated recipe has a matching printable PDF at `cards/<BD-ID>.pdf`. Open any recipe in the app and choose **Open printable recipe card (PDF)**.


## Build 6 branding
- Canonical `assets/bloody_dave_logo.png` from the approved rebuilt recipe-card bundle is used in the app header.
- PWA 192px and 512px install icons are generated from that same canonical logo.
- Service-worker cache bumped to `bd-recipes-v6`.
