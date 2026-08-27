"""Original hero image generation and JPEG normalisation."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import settings
from .models import RecipeDraft


def _placeholder_image(recipe: RecipeDraft, size: tuple[int, int] = (1800, 1200)) -> Image.Image:
    img = Image.new("RGB", size, "#F3E4D8")
    draw = ImageDraw.Draw(img)
    # Soft vignette-like bands without looking like a card overlay.
    for i in range(8):
        shade = 210 - i * 8
        draw.ellipse(
            [-200 + i * 20, -100 + i * 10, size[0] + 200 - i * 20, size[1] + 100 - i * 10],
            outline=(shade, shade - 20, shade - 30),
            width=3,
        )
    title = recipe.title[:48]
    draw.rectangle([80, size[1] // 2 - 80, size[0] - 80, size[1] // 2 + 80], fill="#FFFDFC")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((120, size[1] // 2 - 40), title, fill="#2C2723", font=font)
    draw.text((120, size[1] // 2 + 20), "Original hero placeholder (configure OPENAI_API_KEY for live image)", fill="#6c625b", font=small)
    return img


def generate_hero_image(recipe: RecipeDraft, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if settings.openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            prompt = (
                f"Appetising natural food photography of: {recipe.hero_image_subject or recipe.title}. "
                f"Finished plated dish, Australian home kitchen lighting, no text, no logos, no watermark, "
                f"no QR, no borders, realistic proportions, useful crop for a portrait recipe card."
            )
            result = client.images.generate(
                model=settings.recipe_image_model,
                prompt=prompt,
                size="1536x1024",
            )
            import base64

            item = result.data[0]
            if getattr(item, "b64_json", None):
                raw = base64.b64decode(item.b64_json)
                image = Image.open(io.BytesIO(raw)).convert("RGB")
            elif getattr(item, "url", None):
                import httpx

                raw = httpx.get(item.url, timeout=60).content
                image = Image.open(io.BytesIO(raw)).convert("RGB")
            else:
                image = _placeholder_image(recipe)
        except Exception:
            image = _placeholder_image(recipe)
    else:
        image = _placeholder_image(recipe)

    return normalise_hero_jpeg(image, dest)


def normalise_hero_jpeg(image: Image.Image, dest: Path) -> Path:
    image = image.convert("RGB")
    w, h = image.size
    long_edge = max(w, h)
    target = 2000
    if long_edge > 2400 or long_edge < 1600:
        scale = target / long_edge
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="JPEG", quality=90, optimize=True, progressive=True)
    # Recompress if still huge.
    if dest.stat().st_size > 1_500_000:
        image.save(dest, format="JPEG", quality=85, optimize=True, progressive=True)
    return dest
