# Importing this package registers every tool module's `@register_tool`
# call with the orchestrator. Add new tool modules to this import list as
# they're built (Phase 1 plan: meta_tags -> headers -> ai_crawlers ->
# redirects -> sitemap -> speed -> tech_checker).
from app.services.tools import ai_crawlers, headers, meta_tags, mobile, redirects, sitemap, speed, tech_checker  # noqa: F401

__all__: list[str] = []
