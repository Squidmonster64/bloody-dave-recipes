"""Recipe Studio configuration — secrets stay server-side."""
from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    openai_api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    recipe_text_model: str = Field(default_factory=lambda: os.getenv("RECIPE_TEXT_MODEL", "gpt-4.1-mini"))
    recipe_image_model: str = Field(default_factory=lambda: os.getenv("RECIPE_IMAGE_MODEL", "gpt-image-1"))
    recipe_qa_model: str = Field(default_factory=lambda: os.getenv("RECIPE_QA_MODEL", "gpt-4.1-mini"))

    github_token: str = Field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    github_owner: str = Field(default_factory=lambda: os.getenv("GITHUB_OWNER", "Squidmonster64"))
    github_repo: str = Field(default_factory=lambda: os.getenv("GITHUB_REPO", "bloody-recipes"))
    github_branch: str = Field(default_factory=lambda: os.getenv("GITHUB_BRANCH", "main"))

    public_recipes_url: str = Field(
        default_factory=lambda: os.getenv("PUBLIC_RECIPES_URL", "https://recipes.bloodydaves.com")
    )
    studio_base_url: str = Field(
        default_factory=lambda: os.getenv("STUDIO_BASE_URL", "https://studio.recipes.bloodydaves.com")
    )

    session_secret: str = Field(default_factory=lambda: os.getenv("SESSION_SECRET", "dev-only-change-me"))
    admin_password_hash: str = Field(default_factory=lambda: os.getenv("ADMIN_PASSWORD_HASH", ""))
    admin_password: str = Field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    # When Cloudflare Access protects the domain, set AUTH_MODE=cloudflare_access
    auth_mode: str = Field(default_factory=lambda: os.getenv("AUTH_MODE", "password"))

    job_retention_days: int = Field(default_factory=lambda: int(os.getenv("JOB_RETENTION_DAYS", "14")))
    max_source_bytes: int = Field(default_factory=lambda: int(os.getenv("MAX_SOURCE_BYTES", "3000000")))
    work_dir: Path = Field(default_factory=lambda: Path(os.getenv("JOB_WORK_DIR", str(_repo_root() / "generator" / ".work"))))
    repo_root: Path = Field(default_factory=_repo_root)
    generator_version: str = "bd-recipe-studio-v1"
    card_version: str = "bd-card-v1"
    qr_url: str = "https://recipes.bloodydaves.com"
    rate_limit_per_minute: int = Field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "20")))


settings = Settings()
settings.work_dir.mkdir(parents=True, exist_ok=True)
