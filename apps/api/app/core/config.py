from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    database_url: str = "postgresql+asyncpg://seokit:seokit@localhost:5432/seokit"

    # Clerk issues RS256 JWTs; verify against the instance's JWKS endpoint.
    # Set to e.g. https://your-app.clerk.accounts.dev/.well-known/jwks.json
    clerk_jwks_url: str = ""
    clerk_issuer: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_agency: str = ""

    psi_api_key: str = ""

    redis_url: str = "redis://localhost:6379/0"
    render_sidecar_url: str = "http://localhost:4000"

    # The backend's-eye view of where the Next.js app is reachable --
    # symmetric with the frontend's own NEXT_PUBLIC_API_URL. Used to build
    # public share links and to tell the render sidecar what URL to print
    # to PDF (the sidecar can't reach a Clerk-authenticated page, only a
    # public one served from this base).
    web_public_url: str = "http://localhost:3000"

    # Phase 1 tools run inline in a FastAPI BackgroundTask; Phase 2's
    # browser-driven tools (Page Crawl) run as Celery tasks instead since a
    # full-site crawl can take minutes and needs its own progress tracking.
    page_crawl_max_pages: int = 50

    # GEO/AI-visibility tracker (Phase 4). Unlike every other tool, these
    # calls cost real money per check -- each provider is independently
    # optional, and a tracked-query check simply skips (with an error
    # result) any provider whose key isn't set.
    perplexity_api_key: str = ""
    openai_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]

    # Applies to every request authenticated via get_current_user_or_api_key
    # (dashboard + API-key traffic alike) -- a fixed window per user, not
    # per key, so a user can't dodge it by rotating keys.
    rate_limit_per_minute: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
