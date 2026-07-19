# SEO Repair Kit

All-in-one SEO and website-health audit SaaS. Started as a research report
(`SEO_Repair_Kit_Research_Report.pdf`) describing a 14-tool audit platform;
being rebuilt from scratch as a multi-tenant SaaS product for web developers.

See [`docs/PLAN.md`](docs/PLAN.md) for the development plan and architecture
decisions, and [`docs/PROGRESS.md`](docs/PROGRESS.md) for what's built,
what's verified, and what's left.

## Architecture

```
apps/
  api/             FastAPI backend -- one router + service per tool
  render-sidecar/  Node.js + Puppeteer + axe-core -- browser rendering for
                    JS-dependent tools (Mobile Test, Page Crawl, Accessibility)
  web/             Next.js dashboard + marketing site (Clerk auth)
infra/
  docker-compose.yml   postgres, redis, render-sidecar, api, worker, web
```

- **Backend**: FastAPI (Python), SQLAlchemy (async) + PostgreSQL, Alembic migrations
- **Auth**: Clerk (JWT verified server-side)
- **Billing**: Stripe (webhook-driven, plan-quota enforcement)
- **Background jobs**: Celery + Redis -- only Page Crawl needs this; every
  other tool runs inline via `asyncio.gather` in a FastAPI BackgroundTask
- **Browser automation**: a standalone Node/Puppeteer sidecar service, called
  over HTTP by the Python tools that need a rendered page (Mobile Test,
  Page Crawl's JS-diff sampling, Accessibility)
- **Frontend**: Next.js 16 (App Router), Clerk components, Tailwind

## Local development

```bash
cd infra
docker compose up -d postgres redis render-sidecar
cd ../apps/api
cp .env.example .env        # fill in Clerk/Stripe/PSI keys as needed
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload
# separate terminal, for Page Crawl:
.venv/Scripts/python -m celery -A app.core.celery_app worker --loglevel=info --pool=solo

cd ../web
cp .env.local.example .env.local   # fill in Clerk keys
npm install && npm run dev
```

Run the backend test suite with `pytest` from `apps/api` (no external
services required -- everything is mocked with `respx`).

## Status

13 audit tools live (see `docs/PROGRESS.md` for the full breakdown): Meta
Tags, HTTP Headers, AI Crawler/llms.txt Checker, Redirect Chain Checker,
Sitemap Finder, Website Speed Test (PSI), Website Technology Checker,
Mobile Support Test, Page Crawl (site-wide), SSL/TLS + DNS Health Checker,
hreflang Checker, Structured Data Validator, Accessibility Audit. Plus
audit-over-time diffing, a project history view, and a GEO/AI Visibility
tracker (Perplexity + OpenAI, on-demand citation checks against tracked
queries) -- the GEO provider integrations are built and structurally
verified but have not yet made a real API call (no keys configured in this
environment; see `docs/PROGRESS.md`).

Phase 5a adds a public API: users can generate `srk_live_...` API keys
(`/api-keys`) and use them in place of a Clerk session JWT on `/projects`,
`/audits`, and `/geo`, gated by a per-plan key limit and a 60 requests/minute
rate limiter. CLI/GitHub Action, teams/workspaces, and tools 10-13 are not
yet started -- see `docs/PROGRESS.md` for what's verified vs. not.
