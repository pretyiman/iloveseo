# Implementation Progress

Status as of the Phase 3 completion (before first git push). Update this
file as work continues -- it's the source of truth for "what's actually
done" vs. `docs/PLAN.md`'s "what's intended."

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 -- SaaS foundation | Done, verified | Auth, billing webhook, data model, orchestrator v1, dashboard shell |
| 1 -- 7 sync tools | Done, verified | Each tool live-tested against real domains, not just mocks |
| 2 -- browser tools + queue | Done, verified | Sidecar, Celery/Redis, Mobile Test, Page Crawl |
| 3 -- site-health gaps | Done, verified | SSL/DNS, hreflang, structured data, accessibility, diffing |
| 4 -- GEO/AI Visibility tracker | Not started | |
| 5 -- Growth (API, CLI, teams, tools 10-13) | Not started | |

## Tools (13 live)

| Tool | Registry name | Kind | Tests | Live-verified against |
|---|---|---|---|---|
| Meta Tag Extractor | `meta_tags` | sync | 4 | example.com |
| HTTP Header Test | `http_headers` | sync | 6 | example.com |
| AI Crawler / llms.txt Checker | `ai_crawlers` | sync | 8 | github.com |
| Redirect Chain Checker | `redirects` | sync | 7 | github.com |
| Sitemap Finder | `sitemap` | sync | 6 | wordpress.org, stripe.com |
| Website Speed Test | `speed` | sync (needs `PSI_API_KEY`) | 6 | not live-tested -- no API key in this env |
| Website Technology Checker | `tech_checker` | sync | 5 | wordpress.org, shopify.com, github.com |
| Mobile Support Test | `mobile` | sidecar, in fast batch | 9 (+2 render-client) | example.com (real screenshot captured) |
| Page Crawl (site-wide) | `page_crawl` | sidecar + **Celery task** | 18 | quotes.toscrape.com (49 pages) |
| SSL/TLS + DNS Health Checker | `ssl_dns` | sync | 7 | github.com, google.com |
| hreflang / Intl. SEO Checker | `hreflang` | sync | 8 | airbnb.com (96 hreflang entries) |
| Structured Data Validator | `structured_data` | sync | 9 | github.com, stripe.com |
| Accessibility Audit | `accessibility` | sidecar (axe-core), in fast batch | 3 (+2 render-client) | example.com |

104 backend tests total, all passing (`pytest` from `apps/api`, no external
services required).

## Known gaps / not yet done

**Billing is one-directional.** The Stripe webhook consumer
(`app/routers/billing.py`) keeps `subscriptions` in sync, but there's no
Checkout Session creation endpoint yet -- a user can't actually click
"upgrade" anywhere in the dashboard. Needs a `POST /billing/checkout`
endpoint plus a dashboard billing page before Pro/Agency plans are sellable.

**No real credentials configured in this environment.** Clerk, Stripe, and
`PSI_API_KEY` are all unset locally (`.env`/`.env.local` are gitignored, see
`.env.example` files for what's needed). The Speed Test tool has never been
live-tested against the real PageSpeed Insights API as a result -- only
against mocked responses.

**No CI/CD.** Tests run locally only; nothing runs them on push yet.

**No production deployment.** Docker Compose is dev-only; no hosting target
chosen (Railway/Fly.io/VPS -- see the open items in the original SaaS plan).

**Single-user project ownership.** No teams/workspaces -- `projects.user_id`
is a straight FK, no multi-seat concept. Planned for Phase 5.

**No API-level rate limiting beyond plan quota.** `check_and_increment_usage`
enforces the monthly scan quota, but there's nothing stopping e.g. rapid-fire
requests within quota from one user hammering target sites -- worth adding
per-request throttling before this is public.

**Orchestrator and the DB-querying half of diffing have no automated tests.**
`diff_result` itself (the pure comparison logic) has 4 unit tests, but
`get_previous_results_by_tool` and `app/services/orchestrator.py` were only
verified manually against a real Postgres + Celery worker in this session
(including finding and fixing a real bug -- see below). There's no pytest
fixture wiring up a test database yet, so regressions in the DB-touching
code paths won't be caught by `pytest` alone.

**Sitemap coverage check in Page Crawl is shallow.** `crawl.py`'s
`_discover_sitemap_urls` only expands the first 3 child sitemaps of a
sitemap index before comparing against crawled URLs -- fine for the
"sample and flag" use case, but the `sitemap_urls_not_crawled` count will
undercount on sites with many child sitemaps.

**Structured Data Validator checks presence, not semantics.** It confirms
required properties exist (e.g. `Product.offers.price`) but doesn't validate
their types/formats (e.g. that `price` parses as a number, or that
`availability` uses the full `https://schema.org/InStock` URL form Google
actually requires).

**Accessibility Audit is desktop-only.** Unlike Mobile Support Test, it
doesn't run a mobile device pass -- axe-core rules like target-size overlap
with Mobile Test's tap-target check but aren't cross-validated.

## Real bugs found and fixed during verification (not just features)

- **respx (test HTTP mock library) treats a path-less mocked URL as a
  wildcard** matching any path on that host, not just `/`. Cost two rounds
  of false-green tests (redirect checker, crawl checker) before being
  caught by asserting on hop/page counts instead of just finding codes.
  Fix: always mock with an explicit trailing slash (`https://example.com/`).
- **SQLAlchemy's async engine pools connections tied to the event loop that
  created them.** Celery (`--pool=solo` on Windows, and prefork too) runs
  each task via its own `asyncio.run()` / fresh event loop, so pooled
  connections from one Page Crawl task were being reused (broken) by the
  next one, failing with `'NoneType' object has no attribute 'send'`.
  Fixed by calling `engine.dispose()` at the end of every Celery task, in
  the same loop the connections were opened on. Verified with 3 clean
  sequential runs.

## Platform note

Local dev on Windows requires `celery ... --pool=solo` (the default
prefork pool doesn't work on Windows). The Docker Compose `worker` service
runs on Linux inside the container and doesn't need this flag.
