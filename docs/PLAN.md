# Development Plan

## Context

`SEO_Repair_Kit_Research_Report.pdf` (and its `.docx` source) documents a
planned 14-tool SEO audit platform, 8 of which the report describes as
already built prior to this repo existing. When work on this repo started,
no code existed yet -- only the report. The report was reviewed for
technical flaws (character-count vs. pixel-width truncation, static-only
detection blind spots, missing TLS/accessibility/international-SEO
coverage, etc.) and for what's changed in the SEO/AI-search landscape since
it was written (AI crawler access control, Generative Engine Optimization,
the June 2026 Core Web Vitals INP sampling change). That review became the
basis for this rebuild, rather than a literal port of the report.

## Confirmed decisions

- **Stack**: FastAPI (Python) + Celery/Redis + Node/Puppeteer sidecar +
  PostgreSQL, per the report's original design.
- **Sequencing**: lean MVP first, ship fast, fund further phases from
  revenue rather than building all 14 tools before launch.
- **Distribution wedge**: hosted web dashboard SaaS with subscription tiers
  (Free / Pro / Agency), not a CLI/API-first product to start.
- **Resourcing**: solo build, optimized for speed over process.
- **Frontend**: Next.js (App Router) -- chosen over a plain SPA for SSR,
  which matters for the marketing site's own SEO.
- **Auth/billing**: Clerk + Stripe, chosen over hand-rolled auth purely to
  move faster solo. Both are swappable later without a rewrite (the user
  has noted possibly moving to Google OAuth directly -- not yet done).

## Architecture rationale

The original report's 8 "live" tools split cleanly into two groups:

- **Sync / no-browser tools** -- Meta Tags, Headers, Redirects, Sitemap,
  Speed (PSI API), Tech Checker, plus AI Crawler/llms.txt Checker (new).
  These need nothing but an HTTP client, so they run **inline**, concurrently
  via `asyncio.gather`, inside a single FastAPI BackgroundTask per audit.
- **Browser-required tools** -- Mobile Support Test, Page Crawl,
  Accessibility Audit. These need a real rendered page (viewport, tap
  targets, computed styles, axe-core injection), so they call a dedicated
  Node/Puppeteer sidecar over HTTP.

Only **Page Crawl** needs a real job queue: a full-site crawl can take
minutes, so it's dispatched as a **Celery task**, decoupled from the fast
batch, with its own `AuditResult` row (`status="running"`, incremental
`progress` JSON) that the frontend polls. Every other browser-required tool
(Mobile Test, Accessibility) is a single-page render -- fast enough to join
the concurrent `asyncio.gather` batch like the sync tools, no queue needed.

This is why Celery/Redis and the Puppeteer sidecar were deliberately
deferred out of the MVP (Phase 1) and only introduced in Phase 2 -- they add
real operational surface that most of the tool set doesn't need.

## Phases

**Phase 0 -- SaaS foundation.** Auth (Clerk), billing (Stripe webhooks +
plan-quota enforcement), core data model (`users`, `projects`, `audits`,
`audit_results`, `usage_counters`), orchestrator v1 (`asyncio.gather` over a
`TOOL_REGISTRY`), Next.js dashboard shell with live-polling results.

**Phase 1 -- MVP: the 7 sync tools.** Meta Tag Extractor, HTTP Header Test,
AI Crawler/llms.txt Checker, Redirect Chain Checker, Sitemap Finder, Website
Speed Test, Website Technology Checker. Each one deliberately fixes a
specific flaw identified in the original report (e.g. pixel-width title/
description scoring instead of character-count bands; TLS/cookie checks
added to Headers; a broader, less WordPress-biased tech-signature set).

**Phase 2 -- browser-required tools + job queue.** Puppeteer sidecar
(device emulation, tap-target/font extraction, screenshots), Celery + Redis,
Mobile Support Test (multi-device, throttled), Page Crawl (thin-content
thresholds per page type, heading structure, broken images, mixed content,
minhash near-duplicate detection, robots-based indexability reasoning,
sitemap coverage cross-check, JS-render-diff sampling).

**Phase 3 -- remaining site-health gaps.** SSL/TLS + DNS Health Checker
(cipher grading, HSTS preload list, SPF/DMARC), hreflang/International SEO
Checker (reciprocity, locale validation), Structured Data/Rich Results
Validator (per-type required properties, deprecated-type warnings --
verified against current Google documentation rather than assumed, which
mattered: FAQ rich results were deprecated 2026-05-07, after this project's
knowledge cutoff), Accessibility Audit (axe-core via the sidecar),
audit-over-time diffing (score deltas / new-resolved findings across audits,
project history view).

**Phase 4 -- AI Visibility / GEO tracker (not started).** Track brand/domain
citations across ChatGPT, Perplexity, Gemini, Claude answers; share-of-voice
vs. named competitors. Deliberately sequenced ahead of the original report's
tools 10-13 (Backlink/Keyword/SERP/Traffic checkers) because it needs LLM
API access rather than an expensive third-party SEO data license --
consistent with the "fund further phases from revenue" sequencing decision,
this is the highest-leverage next build once Phase 3's tool set is proven
in front of real users.

**Phase 5 -- growth (not started).** Public API + API keys, GitHub
Action/CLI for CI/CD integration (the "necessary infrastructure" positioning
from the original discussion), the original report's tools 10-13 via
third-party data APIs once revenue justifies the licensing cost, and
teams/workspaces once solo-user traction is proven.

See `docs/PROGRESS.md` for what's actually built and verified per phase.
