# Importing this package registers every tool module's `@register_tool`
# call with the orchestrator. Add new tool modules to this import list as
# they're built (Phase 1 plan: meta_tags -> headers -> ai_crawlers ->
# redirects -> sitemap -> speed -> tech_checker).
from app.services.tools import (  # noqa: F401
    accessibility,
    ai_crawlers,
    headers,
    hreflang,
    meta_tags,
    mobile,
    redirects,
    sitemap,
    speed,
    ssl_dns,
    structured_data,
    tech_checker,
)

__all__: list[str] = []
