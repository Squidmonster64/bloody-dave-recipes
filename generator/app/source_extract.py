"""Deterministic recipe extraction before AI normalisation."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from .models import SourceFacts
from .source_fetch import FetchResult

ISO_DURATION = re.compile(
    r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
    re.I,
)


def _duration_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        minutes = int(value)
        return f"{minutes} minutes" if minutes else ""
    text = str(value).strip()
    match = ISO_DURATION.fullmatch(text)
    if not match:
        return text
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0) + int(match.group("days") or 0) * 24 * 60
    total = hours * 60 + minutes
    if not total:
        return ""
    if total < 60:
        return f"{total} minutes"
    h, m = divmod(total, 60)
    return f"{h} hour {m} minutes" if m else f"{h} hour" + ("" if h == 1 else "s")


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text") or item.get("name") or item.get("@value") or ""
                if text:
                    out.append(str(text).strip())
            else:
                text = str(item).strip()
                if text:
                    out.append(text)
        return out
    if isinstance(value, dict):
        return _as_list(value.get("itemListElement") or value.get("text") or value.get("name"))
    text = str(value).strip()
    return [text] if text else []


def _walk_jsonld(node: Any) -> list[dict]:
    found: list[dict] = []
    if isinstance(node, dict):
        types = node.get("@type") or node.get("type")
        type_list = types if isinstance(types, list) else [types]
        if any(str(t).lower() == "recipe" for t in type_list if t):
            found.append(node)
        for value in node.values():
            found.extend(_walk_jsonld(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk_jsonld(item))
    return found


def _publisher_from_recipe(recipe: dict, soup: BeautifulSoup) -> str:
    for key in ("publisher", "author"):
        value = recipe.get(key)
        if isinstance(value, dict):
            name = value.get("name")
            if name:
                return str(name)
        elif isinstance(value, list) and value:
            return _publisher_from_recipe({key: value[0]}, soup)
        elif isinstance(value, str) and value.strip():
            return value.strip()
    site = soup.find("meta", property="og:site_name")
    if site and site.get("content"):
        return site["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.split("|")[-1].strip()
    return ""


def extract_from_html(fetch: FetchResult, *, pasted_fallback: str = "") -> SourceFacts:
    html = fetch.content.decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")
    source_hash = "sha256:" + hashlib.sha256(fetch.content).hexdigest()
    facts = SourceFacts(
        submitted_url=fetch.submitted_url,
        resolved_url=fetch.final_url,
        source_hash=source_hash,
    )

    # 1) JSON-LD Recipe
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for recipe in _walk_jsonld(data):
            facts.extraction_method = "json_ld"
            facts.title = str(recipe.get("name") or "").strip()
            facts.publisher = _publisher_from_recipe(recipe, soup)
            facts.serves = str(recipe.get("recipeYield") or "").strip()
            if isinstance(recipe.get("recipeYield"), list):
                facts.serves = ", ".join(str(x) for x in recipe["recipeYield"])
            facts.prep_time = _duration_to_text(recipe.get("prepTime"))
            facts.cook_time = _duration_to_text(recipe.get("cookTime"))
            facts.total_time = _duration_to_text(recipe.get("totalTime"))
            facts.cuisine = str(recipe.get("recipeCuisine") or "").strip()
            if isinstance(recipe.get("recipeCuisine"), list):
                facts.cuisine = ", ".join(str(x) for x in recipe["recipeCuisine"])
            facts.category = str(recipe.get("recipeCategory") or "").strip()
            facts.ingredients = _as_list(recipe.get("recipeIngredient"))
            instructions = recipe.get("recipeInstructions")
            facts.instructions = _as_list(instructions)
            nutrition = recipe.get("nutrition")
            if isinstance(nutrition, dict):
                parts = []
                for key, label in (
                    ("calories", "Calories"),
                    ("proteinContent", "Protein"),
                    ("fatContent", "Fat"),
                    ("carbohydrateContent", "Carbohydrate"),
                ):
                    if nutrition.get(key):
                        parts.append(f"{label}: {nutrition[key]}")
                facts.nutrition_text = "; ".join(parts)
            image = recipe.get("image")
            if isinstance(image, list) and image:
                image = image[0]
            if isinstance(image, dict):
                image = image.get("url")
            facts.image_url = str(image or "")
            if facts.title and facts.ingredients and facts.instructions:
                return facts

    # 2) Microdata
    recipe_node = soup.find(attrs={"itemtype": re.compile(r"schema\.org/Recipe", re.I)})
    if recipe_node:
        facts.extraction_method = "microdata"
        name = recipe_node.find(attrs={"itemprop": "name"})
        facts.title = (name.get_text(" ", strip=True) if name else "") or facts.title
        facts.ingredients = [
            el.get_text(" ", strip=True)
            for el in recipe_node.find_all(attrs={"itemprop": "recipeIngredient"})
            if el.get_text(strip=True)
        ]
        facts.instructions = [
            el.get_text(" ", strip=True)
            for el in recipe_node.find_all(attrs={"itemprop": "recipeInstructions"})
            if el.get_text(strip=True)
        ]
        facts.publisher = _publisher_from_recipe({}, soup)
        if facts.title and facts.ingredients and facts.instructions:
            return facts

    # 3) Obvious recipe-card DOM
    ingredient_candidates = soup.select(".recipe-ingredients li, .ingredients li, [class*='ingredient'] li")
    instruction_candidates = soup.select(".recipe-instructions li, .instructions li, .method li, [class*='instruction'] li, [class*='method'] li")
    if ingredient_candidates and instruction_candidates:
        facts.extraction_method = "dom"
        h1 = soup.find("h1")
        facts.title = h1.get_text(" ", strip=True) if h1 else facts.title
        facts.ingredients = [el.get_text(" ", strip=True) for el in ingredient_candidates if el.get_text(strip=True)]
        facts.instructions = [el.get_text(" ", strip=True) for el in instruction_candidates if el.get_text(strip=True)]
        facts.publisher = _publisher_from_recipe({}, soup)
        if facts.title and facts.ingredients and facts.instructions:
            return facts

    # 4) Cleaned visible text / pasted fallback
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))
    facts.raw_excerpt = text[:20_000]
    if pasted_fallback.strip():
        facts.extraction_method = "pasted_source"
        facts.raw_excerpt = pasted_fallback.strip()[:50_000]
        facts.source_hash = "sha256:" + hashlib.sha256(pasted_fallback.encode("utf-8")).hexdigest()
        if not facts.title:
            first_line = facts.raw_excerpt.splitlines()[0].strip()
            facts.title = first_line[:160]
        return facts

    facts.extraction_method = "page_text"
    return facts


def extract_from_pasted(url: str, pasted: str) -> SourceFacts:
    content = pasted.encode("utf-8")
    text = pasted.strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0][:160] if lines else "Pasted recipe"
    ingredients: list[str] = []
    instructions: list[str] = []
    section = ""
    serves = ""
    for line in lines[1:]:
        lower = line.lower().rstrip(":")
        if lower in {"ingredients", "ingredient", "buy", "what you need"}:
            section = "ingredients"
            continue
        if lower in {"method", "methods", "instructions", "directions", "steps"}:
            section = "instructions"
            continue
        if lower.startswith("serves"):
            serves = line.split(":", 1)[-1].strip() if ":" in line else line.replace("Serves", "").strip()
            continue
        if section == "ingredients":
            ingredients.append(re.sub(r"^[-*•]\s*", "", line))
        elif section == "instructions":
            instructions.append(re.sub(r"^\d+[\).\s]+", "", line))
        elif re.match(r"^[\d½¼¾]", line) or re.search(r"\b(g|ml|tsp|tbsp|cup)\b", line, re.I):
            ingredients.append(line)
        elif re.match(r"^\d+[\).]", line):
            instructions.append(re.sub(r"^\d+[\).\s]+", "", line))
    return SourceFacts(
        submitted_url=url,
        resolved_url=url,
        title=title,
        serves=serves,
        ingredients=ingredients,
        instructions=instructions,
        extraction_method="pasted_source",
        source_hash="sha256:" + hashlib.sha256(content).hexdigest(),
        raw_excerpt=text[:50_000],
    )
