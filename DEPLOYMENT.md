# Deployment — recipes.bloodydaves.com

## Recommended platform

Cloudflare Pages, using a direct upload or a connected Git repository.

This is a static application. It has no build step and no server dependency.

## Pre-deployment check

From the project root:

```bash
python3 scripts/validate_data.py
node --check app.js
node --check sw.js
node tests/test_data_logic.js
python3 tests/test_static_files.py
python3 tests/test_hero_images.py
```

Expected result:

```text
41 curated recipes
41 valid Markdown references
41 dataset favourites
41 structured recipes
0 reference-only recipes
```

## Cloudflare Pages — direct upload

1. Sign in to Cloudflare.
2. Open **Workers & Pages**.
3. Choose **Create** → **Pages** → **Upload assets**.
4. Upload the contents of this folder, not an extra enclosing folder.
5. Deploy.
6. In the Pages project, open **Custom domains**.
7. Add `recipes.bloodydaves.com`.
8. Allow Cloudflare to create or confirm the DNS record.

The deployed root must contain:

```text
/index.html
/app.js
/styles.css
/sw.js
/manifest.webmanifest
/recipes.json
/Recipes/
/assets/
/Archive/
```

## Cloudflare Pages — Git deployment

Use these settings:

```text
Framework preset: None
Build command:       leave blank
Build output:        /
Root directory:      repository root
```

If Cloudflare requires an output directory, place the app files in a folder such as `public/` and set the output directory to `public`.

## DNS

The preferred method is adding the custom domain inside Cloudflare Pages. If DNS is hosted elsewhere, Cloudflare will provide the required CNAME target.

Do not create a redirect from the subdomain to another path. The PWA scope and service worker are designed for the root of:

`https://recipes.bloodydaves.com`

## First production test

1. Open the site in a private browser window.
2. Confirm the Library status reports **41 of 41 recipes**.
3. Search `barramundi` and confirm one matching recipe.
4. Select `BD-0001` and `BD-0004` and open Shopping.
5. Confirm duplicate Garlic is merged to `4 clove`.
6. Switch a pantry item from Have to Need.
7. Print or export the Need list.
8. Open `BD-0001` and confirm the supporting Markdown reference appears.
9. Disconnect the device from the network and reload after the first complete load.
10. Confirm the library still opens.

## Install on Apple devices

### iPhone and iPad

1. Open the production URL in Safari.
2. Tap **Share**.
3. Tap **Add to Home Screen**.
4. Tap **Add**.

### Mac

In Safari, use **File → Add to Dock** where available. In Chrome or Edge, use the install icon in the address bar or **Install app** from the browser menu.

## Updating the app

Whenever `app.js`, `styles.css`, `recipes.json` or the Markdown files change:

1. update the cache name in `sw.js`, for example `bd-recipes-v4` to `bd-recipes-v5`;
2. validate the dataset;
3. redeploy the complete folder.

Changing the cache name ensures installed devices discard the old application cache.

## Adding the archive later

Place the completed archive at:

```text
Archive/index.json
Archive/recipes/
Archive/images/
```

Redeploy those files. The existing app will detect and search the archive automatically. The main 41-recipe library remains independent.
