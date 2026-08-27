"""AI normalisation with Australianisation rules and offline deterministic fallback."""
from __future__ import annotations

import json
import re
from typing import Any

from .config import settings
from .models import MethodStage, NormalisedAIRecipe, RecipeDraft, SourceFacts

AU_REPLACEMENTS = [
    (re.compile(r"\bbell peppers?\b", re.I), "capsicum"),
    (re.compile(r"\bcilantro\b", re.I), "coriander"),
    (re.compile(r"\bscallions?\b", re.I), "spring onion"),
    (re.compile(r"\bgreen onions?\b", re.I), "spring onion"),
    (re.compile(r"\bground beef\b", re.I), "beef mince"),
    (re.compile(r"\ball-purpose flour\b", re.I), "plain flour"),
    (re.compile(r"\bconfectioners'? sugar\b", re.I), "icing sugar"),
    (re.compile(r"\bzucchini\b", re.I), "zucchini"),  # AU also uses zucchini
    (re.compile(r"\bfahrenheit\b", re.I), "Celsius"),
]

MATERIAL_HINTS = re.compile(
    r"\b(remove|replace|substitute|vegetarian|vegan|without|no beef|no dairy|"
    r"serve[s]?\s+\d+|australianise|australianize|coles|woolworths)\b",
    re.I,
)


def australianise_text(text: str) -> str:
    out = text
    for pattern, repl in AU_REPLACEMENTS:
        out = pattern.sub(repl, out)
    # F to C for common oven temps: 350°F -> 180°C
    def _f_to_c(match: re.Match[str]) -> str:
        f = int(match.group(1))
        c = int(round((f - 32) * 5 / 9 / 5.0) * 5)
        return f"{c}°C"

    out = re.sub(r"(\d{2,3})\s*°?\s*F\b", _f_to_c, out)
    return out


def is_material_adaptation(instructions: str, notes: list[str] | None = None) -> bool:
    blob = " ".join([instructions or "", *(notes or [])])
    return bool(MATERIAL_HINTS.search(blob))


def _split_or_combine_steps(steps: list[str]) -> list[MethodStage]:
    cleaned = [re.sub(r"^\d+[\).\s]+", "", s).strip() for s in steps if str(s).strip()]
    if not cleaned:
        cleaned = [
            "Prepare the ingredients as listed.",
            "Heat the pan or oven as needed.",
            "Cook the main components until nearly done.",
            "Combine sauces or seasonings and finish cooking.",
            "Rest or finalise textures.",
            "Plate and serve.",
        ]
    while len(cleaned) < 6:
        # Split the longest remaining compound step on sentence boundaries.
        idx = max(range(len(cleaned)), key=lambda i: len(cleaned[i]))
        parts = re.split(r"(?<=[.!?])\s+", cleaned[idx])
        if len(parts) >= 2:
            cleaned[idx : idx + 1] = [parts[0].strip(), " ".join(parts[1:]).strip()]
        else:
            cleaned.append(cleaned[idx])
        cleaned = [c for c in cleaned if c]
    while len(cleaned) > 6:
        # Combine shortest adjacent pair.
        pair_lengths = [(len(cleaned[i]) + len(cleaned[i + 1]), i) for i in range(len(cleaned) - 1)]
        _, i = min(pair_lengths)
        cleaned[i] = f"{cleaned[i]} {cleaned[i + 1]}".strip()
        del cleaned[i + 1]
    stages: list[MethodStage] = []
    for i, text in enumerate(cleaned[:6], start=1):
        text = australianise_text(text)
        words = text.split()
        heading = " ".join(words[:4]).rstrip(".,:;!") or f"Stage {i}"
        stages.append(MethodStage(heading=heading[:60], directions=text))
    return stages


def _guess_protein(ingredients: list[str], category: str = "") -> str:
    blob = " ".join(ingredients + [category]).lower()
    mapping = [
        ("prawn", "Prawns"),
        ("shrimp", "Prawns"),
        ("barramundi", "Seafood"),
        ("salmon", "Fish"),
        ("fish", "Fish"),
        ("chicken", "Chicken"),
        ("beef", "Beef"),
        ("lamb", "Lamb"),
        ("pork", "Pork"),
        ("tofu", "Vegetarian"),
        ("halloumi", "Vegetarian"),
    ]
    for needle, label in mapping:
        if needle in blob:
            return label
    if any(x in blob for x in ("bean", "lentil", "chickpea", "veg")):
        return "Vegetarian"
    return category or "Mixed"


def deterministic_normalise(source: SourceFacts, instructions: str) -> RecipeDraft:
    ingredients = [australianise_text(i) for i in (source.ingredients or [])]
    if not ingredients and source.raw_excerpt:
        # Heuristic lines that look like ingredients.
        for line in source.raw_excerpt.splitlines():
            if re.match(r"^[\d½¼¾]", line.strip()) or re.search(r"\b(g|ml|tsp|tbsp|cup)\b", line, re.I):
                ingredients.append(australianise_text(line.strip()))
        ingredients = ingredients[:30]
    pantry_words = ("oil", "salt", "pepper", "sugar", "butter", "flour", "water", "vinegar")
    buy, pantry = [], []
    for item in ingredients:
        if any(w in item.lower() for w in pantry_words) and len(item.split()) <= 5:
            pantry.append(item)
        else:
            buy.append(item)
    if not buy and ingredients:
        buy = ingredients
    method = _split_or_combine_steps(source.instructions or [])
    material = is_material_adaptation(instructions)
    nutrition = source.nutrition_text or "Nutrition not supplied for this adapted version"
    nutrition_basis = "source_retained"
    if material or not source.nutrition_text:
        nutrition = "Nutrition not supplied for this adapted version"
        nutrition_basis = "not_supplied_after_adaptation" if material else "not_supplied"
    title = australianise_text(source.title or "Bloody Dave Recipe")
    publisher = source.publisher or "Unknown source"
    quote = f"Keep the {title.split()[0].lower()} honest and don't rush the finish."
    return RecipeDraft(
        title=title[:160],
        subtitle=australianise_text((source.category or source.cuisine or title)[:220]),
        hook=f"A Bloody Dave take on {title}.",
        source=publisher[:120],
        source_url=source.resolved_url or source.submitted_url,
        serves=str(source.serves or "2")[:40],
        prep_time=source.prep_time,
        cook_time=source.cook_time,
        total_time=source.total_time,
        cuisine=australianise_text(source.cuisine or "Modern Australian")[:80],
        protein=_guess_protein(ingredients, source.category),
        tags=[t for t in [source.cuisine, source.category, "Generated"] if t][:8],
        buy=buy,
        pantry=pantry,
        method=method,
        allergens="Check current product labels.",
        nutrition=nutrition,
        nutrition_display=nutrition,
        nutrition_table=None,
        hero_image_subject=f"Finished {title}",
        bloody_dave_quote=quote[:180],
        source_credit=f"Adapted from {publisher}"[:160],
        nutrition_basis=nutrition_basis,
        requested_adaptations=[s.strip() for s in re.split(r"[;\n]", instructions) if s.strip()],
    )


def _openai_client():
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return OpenAI(api_key=settings.openai_api_key)


def ai_normalise(source: SourceFacts, instructions: str) -> RecipeDraft:
    if not settings.openai_api_key:
        return deterministic_normalise(source, instructions)

    try:
        client = _openai_client()
        payload = {
            "source_facts": source.model_dump(),
            "requested_adaptations": instructions,
            "rules": {
                "australianise": True,
                "metric": True,
                "celsius": True,
                "exactly_six_method_stages": True,
                "no_fabricated_nutrition_as_source": True,
                "retailer_language_generic": True,
                "rewrite_concise_bloody_dave_prose": True,
            },
        }
        parsed: NormalisedAIRecipe | None = None
        if hasattr(client, "responses") and hasattr(client.responses, "parse"):
            response = client.responses.parse(
                model=settings.recipe_text_model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You normalise recipes for Bloody Dave's Recipes. "
                            "Return only structured data matching the schema. "
                            "Preserve factual quantities, temperatures, timings and food-safety cues. "
                            "Rewrite method prose concisely. Use Australian kitchen language. "
                            "Do not invent source nutrition. Exactly six method stages."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
                text_format=NormalisedAIRecipe,
            )
            parsed = response.output_parsed
        else:
            completion = client.chat.completions.create(
                model=settings.recipe_text_model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Return JSON for a Bloody Dave recipe with keys matching "
                            "NormalisedAIRecipe and exactly six method stages."
                        ),
                    },
                    {"role": "user", "content": json.dumps(payload)},
                ],
            )
            parsed = NormalisedAIRecipe.model_validate_json(completion.choices[0].message.content or "{}")

        material = is_material_adaptation(instructions, parsed.adaptation_notes)
        nutrition = parsed.nutrition
        nutrition_display = parsed.nutrition_display
        if material or not parsed.retain_source_nutrition:
            nutrition = "Nutrition not supplied for this adapted version"
            nutrition_display = nutrition
            nutrition_basis = "not_supplied_after_adaptation" if material else "not_supplied"
        else:
            nutrition_basis = "source_retained"
        return RecipeDraft(
            title=australianise_text(parsed.title),
            subtitle=australianise_text(parsed.subtitle),
            hook=australianise_text(parsed.hook),
            source=parsed.source,
            source_url=source.resolved_url or source.submitted_url,
            serves=parsed.serves,
            prep_time=parsed.prep_time,
            cook_time=parsed.cook_time,
            total_time=parsed.total_time,
            cuisine=australianise_text(parsed.cuisine),
            protein=parsed.protein,
            difficulty=parsed.difficulty,
            tags=[australianise_text(t) for t in parsed.tags],
            buy=[australianise_text(i) for i in parsed.buy],
            pantry=[australianise_text(i) for i in parsed.pantry],
            method=[
                MethodStage(
                    heading=australianise_text(s.heading),
                    directions=australianise_text(s.directions),
                )
                for s in parsed.method
            ],
            allergens=(
                parsed.allergens
                if "check current product labels" in parsed.allergens.lower()
                else f"{parsed.allergens}. Check current product labels."
            ),
            nutrition=nutrition,
            nutrition_display=nutrition_display,
            nutrition_table=None,
            hero_image_subject=parsed.hero_image_subject or f"Finished {parsed.title}",
            bloody_dave_quote=parsed.bloody_dave_quote,
            source_credit=parsed.source_credit or f"Adapted from {parsed.source}",
            nutrition_basis=nutrition_basis,
            requested_adaptations=[s.strip() for s in re.split(r"[;\n]", instructions) if s.strip()]
            or parsed.adaptation_notes,
        )
    except Exception:
        # Bounded resilience: fall back to deterministic normalisation rather than crashing the job.
        return deterministic_normalise(source, instructions)


def apply_patch(recipe: RecipeDraft, patch: dict[str, Any]) -> RecipeDraft:
    data = recipe.model_dump()
    for key, value in patch.items():
        if value is not None and key in data:
            data[key] = value
    return RecipeDraft.model_validate(data)
