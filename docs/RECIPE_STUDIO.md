# Recipe Studio — operator notes

## What it is

Private admin surface that turns a recipe URL (plus optional adaptation instructions) into a Bloody Dave canonical publication:

```text
recipes.json
Recipes/BD-####.md
assets/hero/BD-####.jpg
cards/BD-####.pdf
docs/Recipe Index.md
```

in **one atomic Git commit** to `Squidmonster64/bloody-recipes` `main`.

## Runtime topology

```text
Public PWA:     Cloudflare Pages  → https://recipes.bloodydaves.com
Recipe Studio:  Railway service   → https://studio.recipes.bloodydaves.com
Published truth: GitHub main
```

The public PWA stays static. Studio holds OpenAI and GitHub secrets server-side.

## Local run

```bash
cd generator
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export AUTH_MODE=open
export PYTHONPATH=.
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`.

## Railway deploy

1. Create a Railway service from this repo.
2. Set the Dockerfile path to `generator/Dockerfile` (build context = repo root).
3. Attach a persistent volume at `/data/work` for draft jobs.
4. Set secrets from `generator/.env.example`.
5. Map custom domain `studio.recipes.bloodydaves.com`.
6. Prefer Cloudflare Access in front of that hostname. If Access is authoritative, set `AUTH_MODE=cloudflare_access`. Otherwise set `AUTH_MODE=password` and `ADMIN_PASSWORD_HASH=sha256:<hex>`.

Generate a password hash:

```bash
python3 - <<'PY'
import hashlib
print('sha256:' + hashlib.sha256(b'your-password').hexdigest())
PY
```

## GitHub token

Fine-grained token scoped only to `Squidmonster64/bloody-recipes` with:

- Contents: Read and write
- Metadata: Read

Never expose the token to browser JavaScript.

## Operator flow

1. Open Recipe Studio.
2. Paste URL + optional instructions.
3. Generate → review/edit → regenerate image/card if needed → Publish.
4. Cloudflare Pages rebuilds from the Git commit; the new recipe appears in the live PWA.

## Retired workflow

Manual archive promotion JSON download/merge is obsolete for new recipes. The Archive tab export remains only as a legacy offline helper.
