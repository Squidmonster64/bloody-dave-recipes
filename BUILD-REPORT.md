# Build Report

## Dataset confirmed

- Schema version: `5.0-final-review`
- Release status: `PENDING_USER_SIGNOFF`
- Declared recipe count: `41`
- Actual recipe count: `41`
- Unique IDs: `41`
- ID range: `BD-0001` to `BD-0041`
- Dataset favourites: `41`
- Markdown references found: `41`
- Optional archive included: `No`

## Structured content confirmed

| Coverage | Count |
|---|---:|
| Structured ingredients/method | 41 |
| Reference-only | 0 |
| Recipes with recorded total time | 39 |

All 41 curated recipes can now contribute structured ingredients to the combined shopping-list workflow.

## Automated checks

- JSON parses successfully.
- Recipe count and declared count agree.
- IDs are unique and use `BD-0001` format.
- All 41 Markdown paths exist.
- All 41 Markdown files are listed in the offline precache.
- All 41 dataset favourites are preserved.
- JavaScript and service-worker syntax checks pass.
- Ingredient parsing handles fractions, attached metric units, product-pack multipliers and quantity ranges.
- Pantry defaults to Have; shopping items default to Need.
- `Archive/index.json` remains optional.
- Service-worker cache bumped to `bd-recipes-v4` for dataset rollout.

## Dataset review flag

The supplied schema identifies the payload as `PENDING_USER_SIGNOFF`. The app preserves the supplied data unchanged; it does not silently alter source-derived recipe content.

## Build 5 recipe-card integration

- Added 41 printable two-page recipe-card PDFs under `cards/BD-0001.pdf` through `cards/BD-0041.pdf`.
- Added the 41 approved hero images under `assets/hero/`.
- Curated recipe records automatically resolve their matching hero image and printable PDF by stable BD ID.
- Recipe detail pages now include **Open printable recipe card (PDF)**.
- PDFs and hero images are runtime-cached when accessed; they are not part of the initial service-worker precache, keeping first install lighter.


## Build 6 branding
- Canonical `assets/bloody_dave_logo.png` from the approved rebuilt recipe-card bundle is used in the app header.
- PWA 192px and 512px install icons are generated from that same canonical logo.
- Service-worker cache bumped to `bd-recipes-v6`.
