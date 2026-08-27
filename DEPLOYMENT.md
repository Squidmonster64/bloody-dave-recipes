# Deployment — recipes.bloodydaves.com

## Topology

```text
Public PWA:      Cloudflare Pages  → https://recipes.bloodydaves.com
Recipe Studio:   Railway           → https://studio.recipes.bloodydaves.com
Published truth: GitHub main       → Squidmonster64/bloody-recipes
```

Publishing a recipe from Studio commits to GitHub. Cloudflare Pages (Git-connected) rebuilds the static PWA.

## Pre-deployment check

```bash
python3 scripts/validate_data.py
python3 scripts/rebuild_recipe_index.py
node --check app.js
node --check sw.js
node tests/test_data_logic.js
python3 tests/test_static_files.py
python3 -m pytest generator/tests -q
```

## Cloudflare Pages — Git

```text
Framework preset: None
Build command:       leave blank
Build output:        /
Root directory:      repository root
```

Custom domain: `recipes.bloodydaves.com` at the site root (PWA scope and service worker require root).

## Recipe Studio — Railway

See `docs/RECIPE_STUDIO.md` and `generator/Dockerfile`.

Required secrets are listed in `generator/.env.example`. Prefer Cloudflare Access on `studio.recipes.bloodydaves.com`.

## Service worker / cache

`sw.js` precaches the application shell and `recipes.json` only. Markdown references, printable cards and hero images use runtime caching so newly published recipes appear without manually editing a precache list. Cache name is bumped when shell assets change.

## First production test

1. Open the site in a private window.
2. Confirm the library loads and search still finds `barramundi`.
3. Open `BD-0001` and confirm hero + printable card.
4. Confirm the header **Recipe Studio** link points at the private studio host.
5. After a Studio publish, confirm the new `BD-####` appears after the Pages deploy.
