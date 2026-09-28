"""Environment-driven configuration. Secrets are only ever read server-side."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        # "DATABASE_URL=" (empty, as in .env.example) means "use the default".
        env_ignore_empty=True,
    )

    # --- Threads / Meta app -------------------------------------------------
    threads_app_id: str = ""
    threads_app_secret: SecretStr = SecretStr("")
    # Optional manual token (e.g. a long-lived token generated in the Meta
    # dashboard). The OAuth flow is preferred; a token stored via OAuth wins.
    threads_access_token: SecretStr = SecretStr("")
    threads_redirect_uri: str = "http://localhost:8000/auth/threads/callback"
    threads_api_base: str = "https://graph.threads.net"
    threads_api_version: str = "v1.0"
    threads_authorize_url: str = "https://threads.net/oauth/authorize"
    threads_scopes: str = "threads_basic,threads_keyword_search,threads_profile_discovery"

    # Local, conservative request budget for keyword_search. Meta documents a
    # limit of 2,200 keyword-search queries per user per rolling 24h; we stay
    # well below it by default.
    threads_keyword_search_daily_budget: int = 500
    # Local budget for profile_lookup + profile_posts calls (profile discovery).
    threads_profile_daily_budget: int = 800
    threads_request_timeout_s: float = 20.0

    # --- Storage ------------------------------------------------------------
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'creator_finder.db'}"
    reference_upload_dir: Path = BACKEND_DIR / "data" / "references"
    # Optional Fernet key used to encrypt stored OAuth tokens at rest.
    token_encryption_key: SecretStr = SecretStr("")

    # --- Embeddings ---------------------------------------------------------
    # Any Hugging Face CLIP/SigLIP checkpoint (requires requirements-ml.txt),
    # e.g. "openai/clip-vit-base-patch32" or "google/siglip-base-patch16-224".
    # "debug-color-histogram" is a dependency-free fallback for development
    # and tests only; it is NOT a semantic model.
    embedding_model: str = "openai/clip-vit-base-patch32"
    embedding_device: str = "cpu"
    max_image_bytes: int = 8 * 1024 * 1024

    # --- App ----------------------------------------------------------------
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"

    min_reference_images: int = Field(default=3)
    max_reference_images: int = Field(default=20)

    @property
    def threads_graph_url(self) -> str:
        return f"{self.threads_api_base.rstrip('/')}/{self.threads_api_version}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
