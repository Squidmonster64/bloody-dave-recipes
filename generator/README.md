# Bloody Dave Recipe Studio

Private FastAPI service that implements:

```text
URL → extract → adapt → hero → 2-page PDF → QA → atomic Git publish
```

## Quick start

```bash
pip install -r requirements.txt
export AUTH_MODE=open
export PYTHONPATH=.
uvicorn app.main:app --reload --port 8000
```

## Tests

```bash
pytest tests -q
```

Offline tests do not call OpenAI or mutate the live library. Without `GITHUB_TOKEN`, publish writes a dry-run folder under `.work/`.

## Package layout

See `app/` for fetch, extract, normalise, image, card, QA, ID allocation and GitHub publish modules.
