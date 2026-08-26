# Bloody Dave Recipe System — Stage 7 HelloFresh Archive

This stage adds a **separate offline HelloFresh archive** alongside the existing Bloody Dave recipe library.

## What it does

- Sweeps all publicly accessible HelloFresh Australia recipe pages.
- Stores them offline in `Archive/` as JSON and Markdown.
- Optionally downloads hero images for offline browsing.
- Leaves the active Bloody Dave library untouched.
- Provides a small local search app for the archive.
- Lets you **promote selected archive recipes into the Bloody Dave library** when you want them.

## Folder structure

- `recipes.json` — active Bloody Dave recipe library
- `Recipes/` — active Bloody Dave recipe Markdown files
- `Archive/index.json` — HelloFresh archive index
- `Archive/recipes/` — one file per archived HelloFresh recipe
- `Archive/images/` — optional hero images
- `archive_app/` — offline archive search app

## Run order

### 1. Build / refresh the HelloFresh archive
Double-click:

`Run HelloFresh Full Archive.command`

This scrapes the public HelloFresh Australia site and fills `Archive/`.

### 2. Search the archive offline
Double-click:

`Run Archive Search App.command`

This opens a local web app in your browser.

### 3. Promote recipes into the Bloody Dave library
Use the archive search app to select recipes and copy their archive IDs.

Then double-click:

`Run Promote Selected.command`

Paste the copied IDs. The script will:
- assign the next BD numbers;
- create new Markdown recipe files in `Recipes/`;
- update `recipes.json`;
- update `Recipe Index.md`;
- leave favourites set to `No` by default.

## Notes

- The HelloFresh archive is a **warehouse**, not the curated library.
- The Bloody Dave library remains the place for favourites, cards and meal planning.
- The QR code for all future recipe cards should point to:

`https://recipes.bloodydaves.com`

- Feedback contact can be:

`info@bloodydaves.com`
