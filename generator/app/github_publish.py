"""GitHub atomic publication via Git Data API."""
from __future__ import annotations

import base64
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import settings
from .id_allocator import allocate_id
from .index_builder import rebuild_index_text


class PublishError(Exception):
    pass


@dataclass
class RepoSnapshot:
    commit_sha: str
    tree_sha: str
    recipes_payload: dict[str, Any]
    markdown_ids: set[str]
    card_ids: set[str]
    hero_ids: set[str]


def _headers() -> dict[str, str]:
    if not settings.github_token:
        raise PublishError("GITHUB_TOKEN is not configured")
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bd-recipe-studio",
    }


def _api(path: str) -> str:
    return f"https://api.github.com/repos/{settings.github_owner}/{settings.github_repo}{path}"


def _normalise_source_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = (parsed.netloc or "").lower().removeprefix("www.")
    path = (parsed.path or "").rstrip("/")
    return f"{host}{path}"


def find_duplicate(payload: dict[str, Any], source_url: str) -> str | None:
    target = _normalise_source_url(source_url)
    if not target:
        return None
    for recipe in payload.get("recipes", []):
        if recipe.get("variant_of"):
            continue
        if _normalise_source_url(str(recipe.get("source_url") or "")) == target:
            return str(recipe.get("id"))
    return None


def find_duplicate_local(
    payload: dict[str, Any], source_url: str, title: str = "", source: str = ""
) -> str | None:
    found = find_duplicate(payload, source_url)
    if found:
        return found
    title_n = (title or "").strip().lower()
    source_n = (source or "").strip().lower()
    if not title_n or not source_n:
        return None
    for recipe in payload.get("recipes", []):
        if recipe.get("variant_of"):
            continue
        if (
            str(recipe.get("title") or "").strip().lower() == title_n
            and str(recipe.get("source") or "").strip().lower() == source_n
        ):
            return str(recipe.get("id"))
    return None


async def load_repo_snapshot() -> RepoSnapshot:
    async with httpx.AsyncClient(timeout=60.0, headers=_headers()) as client:
        ref = await client.get(_api(f"/git/ref/heads/{settings.github_branch}"))
        if ref.status_code != 200:
            raise PublishError(f"Unable to read branch {settings.github_branch}: {ref.text}")
        commit_sha = ref.json()["object"]["sha"]
        commit = await client.get(_api(f"/git/commits/{commit_sha}"))
        commit.raise_for_status()
        tree_sha = commit.json()["tree"]["sha"]
        recipes_resp = await client.get(_api(f"/contents/recipes.json?ref={settings.github_branch}"))
        recipes_resp.raise_for_status()
        content_b64 = recipes_resp.json()["content"]
        payload = json.loads(base64.b64decode(content_b64).decode("utf-8"))

        tree = await client.get(_api(f"/git/trees/{tree_sha}?recursive=1"))
        tree.raise_for_status()
        markdown_ids, card_ids, hero_ids = set(), set(), set()
        for item in tree.json().get("tree", []):
            path = item.get("path", "")
            if path.startswith("Recipes/BD-") and path.endswith(".md"):
                markdown_ids.add(path.removeprefix("Recipes/").removesuffix(".md"))
            elif path.startswith("cards/BD-") and path.endswith(".pdf"):
                card_ids.add(path.removeprefix("cards/").removesuffix(".pdf"))
            elif path.startswith("assets/hero/BD-") and path.endswith(".jpg"):
                hero_ids.add(path.removeprefix("assets/hero/").removesuffix(".jpg"))
        return RepoSnapshot(
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            recipes_payload=payload,
            markdown_ids=markdown_ids,
            card_ids=card_ids,
            hero_ids=hero_ids,
        )


def load_local_snapshot() -> RepoSnapshot:
    root = settings.repo_root
    payload = json.loads((root / "recipes.json").read_text(encoding="utf-8"))
    markdown_ids = {p.stem for p in (root / "Recipes").glob("BD-*.md")}
    card_ids = {p.stem for p in (root / "cards").glob("BD-*.pdf")}
    hero_ids = {p.stem for p in (root / "assets" / "hero").glob("BD-*.jpg")}
    return RepoSnapshot(
        commit_sha="local",
        tree_sha="local",
        recipes_payload=payload,
        markdown_ids=markdown_ids,
        card_ids=card_ids,
        hero_ids=hero_ids,
    )


async def allocate_from_github() -> tuple[str, RepoSnapshot]:
    if settings.github_token:
        snap = await load_repo_snapshot()
    else:
        snap = load_local_snapshot()
    existing = [str(r.get("id")) for r in snap.recipes_payload.get("recipes", [])]
    filesystem = snap.markdown_ids | snap.card_ids | snap.hero_ids
    return allocate_id(existing, filesystem_ids=filesystem), snap


async def _create_blob(client: httpx.AsyncClient, content: bytes, *, binary: bool = False) -> str:
    if binary:
        body = {"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"}
    else:
        body = {"content": content.decode("utf-8"), "encoding": "utf-8"}
    resp = await client.post(_api("/git/blobs"), json=body)
    if resp.status_code >= 300:
        raise PublishError(f"Blob create failed: {resp.text}")
    return resp.json()["sha"]


async def publish_local_dry_run(
    *,
    recipe_id: str,
    recipe_record: dict[str, Any],
    markdown: str,
    hero_bytes: bytes,
    pdf_bytes: bytes,
    target_root: Path | None = None,
) -> str:
    """Offline publication into a temporary directory for tests (does not touch real library)."""
    root = Path(target_root or (settings.work_dir / "dry-run-publish"))
    if root.exists():
        shutil.rmtree(root)
    src = settings.repo_root
    root.mkdir(parents=True)
    (root / "recipes.json").write_bytes((src / "recipes.json").read_bytes())
    for folder in ("Recipes", "cards", "assets/hero", "docs"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    payload = json.loads((root / "recipes.json").read_text(encoding="utf-8"))
    payload["recipes"] = list(payload.get("recipes", [])) + [recipe_record]
    payload["recipe_count"] = len(payload["recipes"])
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    (root / "recipes.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (root / f"Recipes/{recipe_id}.md").write_text(markdown, encoding="utf-8")
    (root / f"assets/hero/{recipe_id}.jpg").write_bytes(hero_bytes)
    (root / f"cards/{recipe_id}.pdf").write_bytes(pdf_bytes)
    (root / "docs" / "Recipe Index.md").write_text(rebuild_index_text(payload), encoding="utf-8")
    return f"local-dry-run:{root}"


async def publish_atomic(
    *,
    recipe_id: str,
    recipe_record: dict[str, Any],
    markdown: str,
    hero_bytes: bytes,
    pdf_bytes: bytes,
    expected_parent_sha: str | None = None,
    max_retries: int = 3,
) -> str:
    if not settings.github_token:
        return await publish_local_dry_run(
            recipe_id=recipe_id,
            recipe_record=recipe_record,
            markdown=markdown,
            hero_bytes=hero_bytes,
            pdf_bytes=pdf_bytes,
        )

    async with httpx.AsyncClient(timeout=120.0, headers=_headers()) as client:
        for _attempt in range(max_retries):
            snap = await load_repo_snapshot()
            dup = find_duplicate(snap.recipes_payload, str(recipe_record.get("source_url") or ""))
            if dup and dup != recipe_id and not recipe_record.get("variant_of"):
                raise PublishError(f"Already in library: {dup}")

            existing_ids = {str(r.get("id")) for r in snap.recipes_payload.get("recipes", [])}
            if recipe_id in existing_ids:
                raise PublishError(f"{recipe_id} already exists in recipes.json")
            if recipe_id in snap.markdown_ids or recipe_id in snap.card_ids or recipe_id in snap.hero_ids:
                raise PublishError(f"{recipe_id} collides with existing artifacts")

            payload = dict(snap.recipes_payload)
            recipes = list(payload.get("recipes", []))
            recipes.append(recipe_record)
            payload["recipes"] = recipes
            payload["recipe_count"] = len(recipes)
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            index_text = rebuild_index_text(payload)

            files = {
                "recipes.json": json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"),
                f"Recipes/{recipe_id}.md": markdown.encode("utf-8"),
                "docs/Recipe Index.md": index_text.encode("utf-8"),
                f"assets/hero/{recipe_id}.jpg": hero_bytes,
                f"cards/{recipe_id}.pdf": pdf_bytes,
            }
            tree_items = []
            for path, content in files.items():
                binary = path.endswith((".jpg", ".pdf"))
                sha = await _create_blob(client, content, binary=binary)
                tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})

            tree_resp = await client.post(
                _api("/git/trees"),
                json={"base_tree": snap.tree_sha, "tree": tree_items},
            )
            if tree_resp.status_code >= 300:
                raise PublishError(f"Tree create failed: {tree_resp.text}")
            new_tree = tree_resp.json()["sha"]
            commit_resp = await client.post(
                _api("/git/commits"),
                json={
                    "message": f"Add {recipe_id} {recipe_record.get('title')}",
                    "tree": new_tree,
                    "parents": [snap.commit_sha],
                },
            )
            if commit_resp.status_code >= 300:
                raise PublishError(f"Commit create failed: {commit_resp.text}")
            new_commit = commit_resp.json()["sha"]
            ref_resp = await client.patch(
                _api(f"/git/refs/heads/{settings.github_branch}"),
                json={"sha": new_commit, "force": False},
            )
            if ref_resp.status_code == 422:
                continue
            if ref_resp.status_code >= 300:
                raise PublishError(f"Ref update failed: {ref_resp.text}")
            return new_commit
    raise PublishError("Could not publish after concurrency retries")
