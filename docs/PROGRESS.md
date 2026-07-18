# Implementation Progress

Status as of Phase 4 completion. Update this file as work continues --
it's the source of truth for "what's actually done" vs. `docs/PLAN.md`'s
"what's intended."

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 -- SaaS foundation | Done, verified | Auth, billing webhook, data model, orchestrator v1, dashboard shell |
| 1 -- 7 sync tools | Done, verified | Each tool live-tested against real domains, not just mocks |
| 2 -- browser tools + queue | Done, verified | Sidecar, Celery/Redis, Mobile Test, Page Crawl |
| 3 -- site-health gaps | Done, verified | SSL/DNS, hreflang, structured data, accessibility, diffing |
| 4 -- GEO/AI Visibility tracker | Done, structurally verified | Perplexity + OpenAI providers; **no live LLM API call has been tested** -- see gaps |
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

119 backend tests total, all passing (`pytest` from `apps/api`, no external
services required).

## GEO / AI Visibility tracker (Phase 4)

Not an audit tool like the 13 above -- a recurring feature: a project
defines "tracked queries" (questions its customers might ask an AI), and
each on-demand check fans out to configured providers concurrently, checks
whether the project's domain/brand name got cited, and records the result.

| Component | Tests | Live-verified |
|---|---|---|
| Provider adapters (`app/services/geo/providers.py`) | 7 | No -- see gaps |
| Citation/mention detection (`app/services/geo/analysis.py`) | 6 | Pure logic, no external calls needed |
| Check runner (`app/services/geo/runner.py`) | 2 | Structurally, via mocked providers |
| API endpoints + DB round-trip | none (manual only) | Yes -- real Postgres, see below |

**What was actually verified**, against a real Postgres with no API keys
configured: creating a project with a `brand_name`, creating a tracked
query with competitor domains, the GEO-check monthly quota check (a
brand-new user's first check correctly allowed, correctly increments),
`run_geo_check` gracefully reporting "not configured" for both providers
instead of crashing, writing `GeoCheck` rows, and deleting a tracked query
cleanly cascading its checks. Also booted the API server and confirmed the
4 new routes are registered, require auth (401 unauthenticated), and appear
in the OpenAPI schema.

**What was not verified: any real LLM API call.** Both provider adapters
(`query_perplexity`, `query_openai`) are written against current provider
documentation (checked via web search during this build, not assumed from
training data) but have never received a real response from either API --
no keys are configured in this environment. The OpenAI adapter in
particular carries more risk here: it parses a specific nested shape
(`output[].content[].annotations[].url_citation.url`) from the Responses
API that could differ in practice. **Before relying on this in production,
add real `PERPLEXITY_API_KEY`/`OPENAI_API_KEY` values and run one real
check against a known query to confirm both response shapes still match.**

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

**GEO tracker has no scheduling.** Checks are on-demand only (a "Check now"
button) -- no Celery Beat periodic re-checking, so there's no automatic
trend-over-time data yet, only whatever the user manually triggers. Also
only 2 of the eventual 4 providers (Perplexity, OpenAI) are implemented;
Anthropic and Gemini are addable behind the same `PROVIDERS` dict in
`app/services/geo/providers.py` without touching the runner, analysis, API,
or frontend layers.

**GEO citation-URL provider integration is unverified against a real API
response.** See the Phase 4 section above.

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
- **A refactor in `plan_limits.py` (done to share logic between the scan
  quota and the new GEO-check quota) dropped an explicit `scans_used=0` /
  `geo_checks_used=0` on newly-created counter rows**, relying instead on
  SQLAlchemy's column-level `default=0`. That default only applies at
  flush/INSERT time, not immediately on object construction -- so reading
  `counter.geo_checks_used >= limit` right after creating a brand-new
  counter crashed with `TypeError: '>=' not supported between instances of
  'NoneType' and 'int'`. This would have broken **every brand-new user's
  first scan too**, not just GEO checks -- caught by manually exercising a
  fresh user through `check_and_increment_usage` after fixing the GEO path,
  specifically because neither path has an automated test (see gap above).
  Fixed by passing both fields explicitly in the constructor.

## Platform notes

Local dev on Windows requires `celery ... --pool=solo` (the default
prefork pool doesn't work on Windows). The Docker Compose `worker` service
runs on Linux inside the container and doesn't need this flag.

In this dev environment, `docker compose up -d <service>` (and even plain
`docker run -d`) has repeatedly left containers stuck in `Created` status
without actually starting them -- `docker ps` shows nothing until you run
an explicit `docker start <container>` afterward. Separately, a container
that's been through a `down`/`up` cycle can come back with its configured
port mapping present in `docker inspect`'s `HostConfig.PortBindings` but
**not actually live** in `NetworkSettings.Ports` -- `docker port` shows
nothing and the host can't connect. Removing the container and letting
Compose recreate it from scratch (`docker rm -f <name>` then `docker
compose up -d <service>` then `docker start <name>`) has reliably fixed it
each time; a stale `com.docker.backend.exe` port-proxy registration is the
likely cause, not the compose file or the app.
