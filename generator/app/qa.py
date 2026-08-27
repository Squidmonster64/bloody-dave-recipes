"""Automated PDF and recipe QA."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from .config import settings
from .models import QAResult, RecipeDraft


def render_previews(pdf_path: Path, front_png: Path, back_png: Path) -> None:
    import fitz

    doc = fitz.open(pdf_path)
    try:
        if doc.page_count < 2:
            raise ValueError("PDF must contain exactly two pages for preview")
        for index, dest in ((0, front_png), (1, back_png)):
            page = doc.load_page(index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            dest.parent.mkdir(parents=True, exist_ok=True)
            pix.save(str(dest))
    finally:
        doc.close()


def decode_qr_from_png(png_path: Path) -> str | None:
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode
    except Exception:
        return None
    results = decode(Image.open(png_path))
    if not results:
        return None
    return results[0].data.decode("utf-8", errors="replace")


def run_qa(
    *,
    recipe: RecipeDraft,
    recipe_id: str,
    pdf_path: Path,
    overflows: list[str] | None = None,
    front_png: Path | None = None,
    back_png: Path | None = None,
) -> QAResult:
    checks: list[dict] = []
    errors: list[str] = []
    warnings: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            errors.append(f"{name}: {detail or 'failed'}")

    check("pdf_exists", pdf_path.is_file(), str(pdf_path))
    if not pdf_path.is_file():
        return QAResult(passed=False, checks=checks, errors=errors, warnings=warnings)

    reader = PdfReader(str(pdf_path))
    check("page_count", len(reader.pages) == 2, f"pages={len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        box = page.mediabox
        w, h = float(box.width), float(box.height)
        a4_ok = abs(w - 595.27) < 8 and abs(h - 841.89) < 8
        check(f"page_{i + 1}_a4_portrait", a4_ok and h > w, f"{w}x{h}")

    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    check("text_layer", bool(text.strip()), "empty text layer" if not text.strip() else "ok")
    for required in (
        "BIG FLAVOUR. NO WORRIES.",
        "info@bloodydaves.com",
        "https://recipes.bloodydaves.com",
        recipe_id,
        recipe.title.split()[0],
    ):
        check(f"required::{required}", required in text, "missing" if required not in text else "ok")
    if recipe.source_credit:
        check("source_credit", recipe.source_credit[:20] in text, recipe.source_credit)

    method_hits = sum(1 for n in range(1, 7) if str(n) in text)
    check("six_method_numbers_visible", method_hits >= 6, f"found={method_hits}")
    check("six_structured_stages", len(recipe.method) == 6, f"count={len(recipe.method)}")
    check("no_empty_method", all(s.heading.strip() and s.directions.strip() for s in recipe.method))
    check("no_overflow", not overflows, ",".join(overflows or []) or "ok")

    if front_png and front_png.exists() and back_png and back_png.exists():
        check("previews_present", True)
        qr_value = decode_qr_from_png(back_png)
        if qr_value is None:
            warnings.append("QR decode library unavailable or QR not detected in preview; generation used locked URL.")
            check("qr_locked_url_configured", settings.qr_url == "https://recipes.bloodydaves.com")
        else:
            check("qr_decodes", qr_value == "https://recipes.bloodydaves.com", qr_value)
    else:
        warnings.append("Preview PNGs not available for visual QR decode.")

    return QAResult(passed=not errors, checks=checks, errors=errors, warnings=warnings)
