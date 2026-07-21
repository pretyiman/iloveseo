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
| 4 -- GEO/AI Visibility tracker | Done, verified | Perplexity + OpenAI providers; OpenAI has now made a real live API call (see below) -- Perplexity still untested (no key configured) |
| 5a -- Public API + API keys | Done, verified | See below |
| 5b -- CLI + GitHub Action | Done, verified | See below. Teams and tools 10-13 remain not started |
| -- Dashboard UX + AI Visibility bundling + competitor comparison | Done, verified | See below. Orthogonal to the Phase 5 growth track, not a Phase 5c |
| -- Report export/share (public link + PDF) | Done, verified | See below. First piece of the freemium/pay-as-you-go product-direction pivot (2026-07-19) |
| -- Anonymous single-scan mode | Done, verified | See below. Second piece of the pivot |
| -- Surface already-fetched tool data (tech stack, PSI opportunities, raw headers) | Done, verified | See below. Prompted by a comparative analysis against a second report for the same site |
| -- Scheduled monitoring + Gmail-sent reports (Parts A + B) | Done, verified except live send | See below. Third piece of the pivot. The pay-as-you-go billing rework is next, not started |

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
| Provider adapters (`app/services/geo/providers.py`) | 7 | OpenAI: yes (real API call, see below). Perplexity: no -- no key configured |
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

**Update: a real OpenAI API call has now been made.** A real
`OPENAI_API_KEY` was configured and `query_openai` reached
`https://api.openai.com/v1/responses` for real. The request succeeded in
the sense that mattered most -- no shape-parsing crash -- but the response
was itself an error: `{"error": {"type": "insufficient_quota", "message":
"You exceeded your current quota, please check your plan and billing
details."}}`, surfaced correctly end-to-end as a `GeoCheck` row with
`status="error"` and that message. This confirms the adapter's HTTP
plumbing and error handling work correctly; it does **not** yet confirm the
success-path response parsing (`output[].content[].annotations[].url_citation.url`)
since no successful (non-error) response has been received yet -- that
still needs billing enabled on the OpenAI account before it can be checked.
**Perplexity remains completely untested** -- no `PERPLEXITY_API_KEY` has
been configured in this environment at any point.

## Public API / API keys (Phase 5a)

Lets external callers (a future CLI/GitHub Action, or scripts) authenticate
with a long-lived key instead of a Clerk session JWT. Deliberately extends
the *existing* dashboard routers (`/projects`, `/audits`, `/geo`) rather
than duplicating them into a separate route tree -- one code path serves
both dashboard and API-key traffic, since external callers need the same
operations (create project, start audit, poll results) the dashboard
already exposes.

| Component | Tests | Live-verified |
|---|---|---|
| Key generation/hashing (`app/core/api_keys.py`) | 3 | Pure logic, no external calls needed |
| Combined auth dependency (`get_current_user_or_api_key`, `app/core/auth.py`) | none | Yes -- see below |
| Rate limiter (`app/core/rate_limit.py`) | none | Yes -- see below |
| `check_api_key_limit` (`app/core/plan_limits.py`) | none | Yes -- see below |
| `/api-keys` router (create/list/revoke) | none | Partially -- see below |

**What was verified**, against a real Postgres + Redis with no Clerk keys
configured (a test user and API key row were inserted directly via SQL,
then deleted afterward -- Clerk itself was never exercised, `/api-keys`'
own create/list/revoke endpoints require a real Clerk JWT and were **not**
called over HTTP this session, only their underlying logic):
booted the API server and confirmed `/api-keys` (POST/GET, `/api-keys/{id}`
DELETE) are registered and appear in the OpenAPI schema; calling
`GET /projects` with no `Authorization` header returns 401; calling it with
a valid `srk_live_...` key returns 200 with the expected data; calling it
with a garbage key returns 401 ("Invalid or revoked API key"); revoking a
key (`revoked_at` set) makes the same key 401 on the next call; firing 65
rapid requests with one key against `/projects` returns 200 for the first
60 and 429 for the rest, confirming the Redis-backed fixed-window limiter
(`app/core/rate_limit.py`, `rate_limit_per_minute=60`); calling
`check_api_key_limit` directly against a free-plan user who already holds
one active key raises 402, confirming the per-plan cap
(`PLAN_API_KEY_LIMITS`).

**What was not verified: the `/api-keys` create/list/revoke endpoints
themselves over HTTP.** They require `get_current_user` (Clerk-only, by
design -- a key must not be able to mint further keys), and no Clerk
instance is configured in this environment. Their logic (plan-cap check,
row creation, soft revoke via `revoked_at`) was verified indirectly by
calling `check_api_key_limit` directly and by inserting/revoking API key
rows via SQL to exercise the auth dependency, but the actual route
handlers in `app/routers/api_keys.py` have not been hit over HTTP with a
real Clerk session. Before relying on this in production, create a real
Clerk account, obtain a session JWT, and confirm `POST /api-keys` returns
the raw key exactly once and `GET /api-keys` never returns it again.

**No automated route-level test coverage**, consistent with the rest of
this codebase (no FastAPI `TestClient`/`conftest.py` scaffolding exists
anywhere yet -- see the pre-existing orchestrator/diffing gap below). Only
the pure key-generation/hashing logic has unit tests; the auth dependency,
rate limiter, and plan-cap check were exercised manually as described
above, not via pytest.

**The plan-key-cap check is non-atomic**, the same pre-existing class of
race already noted below for the scan/GEO quotas (read-then-write, no row
locking) -- not a new bug, just the same shape extended to a new counter.

## CLI + GitHub Action (Phase 5b)

A standalone Node/TypeScript package (`apps/cli`, bin name `seokit`) that
authenticates with an `srk_live_...` API key (Phase 5a) instead of a Clerk
session, and a composite GitHub Action (`.github/actions/seo-audit`) that
wraps it for CI. Mirrors `apps/web/lib/api.ts`'s request/response shapes and
polling condition field-for-field rather than reinventing them.

| Component | Tests | Live-verified |
|---|---|---|
| `severity.ts` (`hasFindingAtOrAbove`, `isValidSeverity`) | 5 | Pure logic, no external calls needed |
| `format.ts` (`formatAuditSummary`) | 2 | Pure logic, no external calls needed |
| `client.ts`, `poll.ts`, `cli.ts` commands | none | Yes -- see below |
| `.github/actions/seo-audit/action.yml` | none (can't trigger a real GH Actions run from here) | Partially -- see below |

**What was verified**, against the same local Postgres + Redis used for
Phase 5a, plus a render-sidecar and a `--pool=solo` Celery worker started for
this session (neither runs by default in this dev environment) so a Page
Crawl result could actually leave `"running"`: a test user + API key row
inserted directly via SQL (as in Phase 5a); `seokit projects create
example.com` and `seokit projects list` against the real API; `seokit audit
run --project-id <id> --wait` correctly polled through a full real audit (13
tools, ~13s, including waiting for the Celery-backed `page_crawl` result to
leave `"running"`) and printed a per-tool summary; re-running with `--fail-on
critical` exited 1 given the real `speed` tool's critical finding (no
`PSI_API_KEY` configured, same known gap as Phase 4); `seokit audit get
<id> --json` returned the raw API JSON unmodified; running without
`SRK_API_KEY` set exited 1 with a clear error. `action.yml` was confirmed to
be well-formed YAML (parsed with PyYAML) and its steps were manually
replicated in a shell (`npm ci && npm run build && node dist/src/cli.js
audit run ...`) to simulate what a runner would execute, since an actual
GitHub Actions run can't be triggered from this environment.

**What was not verified: an actual GitHub Actions run.** The composite
action itself (`uses: pretyiman/iloveseo/.github/actions/seo-audit@main`)
has never executed on a real GitHub-hosted runner -- only its constituent
shell commands, run by hand, against the same local API. Before relying on
this for a real CI gate, add a workflow that calls the action in this repo
(or another) and confirm the job actually fails when `fail-on` is breached
and succeeds otherwise.

**No automated tests for `client.ts`/`poll.ts`/`cli.ts` command wiring** --
consistent with the rest of this codebase's testing philosophy (pure logic
gets unit tests, network/DB-touching code gets manual verification), and
there's no existing HTTP-mocking convention on the Node side of this repo
to build one on top of (neither `apps/web` nor `apps/render-sidecar` has any
test framework at all).

**No npm-registry publish.** The Action builds the CLI from source at the
pinned ref on every run rather than installing a published package -- there's
no hosted production API yet either (see gaps below), so a distribution
decision for the CLI was deliberately deferred alongside it.

## Dashboard UX + AI Visibility bundling + competitor comparison

Collapses the previous 3-click-per-site dashboard (Add domain, then
separately History / AI Visibility / Run audit) into one action: paste a
URL, hit "Audit", get one compiled report. Per explicit product decision,
AI Visibility is now generated automatically as part of every audit rather
than a separate manual step, and a new "History & Compare" page adds a
genuinely new capability: full 13-tool side-by-side comparison, either
against your own past reports or a **fresh** audit run against a
competitor's domain on demand.

**Backend** (`apps/api`): `AiVisibilityOut`/`AiVisibilityProviderOut`
schemas, `app/services/geo/auto_check.py` (auto-managed default tracked
query + best-effort GEO check run after every audit's fast tool batch,
gated on at least one provider being configured and the monthly GEO quota
not being exhausted -- never fails or delays the audit itself), wired into
`orchestrator.run_audit` and `GET /audits/{id}`. New
`projects.is_competitor_only` column (migration `c2f2145a4281`) excludes
one-off competitor lookups from the main site list. New `GET
/audits/compare?a=&b=` endpoint reuses the existing `diff_result` function
from Phase 3's diffing module completely unchanged -- it already computed
exactly "compare two AuditResults for the same tool," so no new diffing
logic was needed for arbitrary A-vs-B comparison (including competitor
audits, which are just an audit against a different project like any
other).

**Frontend** (`apps/web`): redesigned `dashboard/page.tsx` (hero search +
single "Audit" button, domain-reuse-on-resubmit so re-entering the same
domain doesn't create a duplicate project -- handled client-side against
the already-loaded project list, no backend uniqueness constraint added),
new shared `ScoreBadge`/`DashboardNav` components, an "AI Visibility"
section folded into `audits/[id]/page.tsx` (not integrated / not
functional / cited / not cited states per provider), and new
`dashboard/history/page.tsx` + `dashboard/compare/page.tsx` for the
history/comparison flows. The old `dashboard/projects/[id]/history` route
was removed (superseded by the global History & Compare page); the
existing `dashboard/projects/[id]/geo` page was kept, de-emphasized, for
anyone who wants to hand-edit the auto-generated tracked query.

**Real bug found and fixed along the way**: ClerkJS overwrites `<body>`'s
`className` at runtime (observed value: `"cl-component v6"`), silently
dropping any Tailwind classes placed directly on `<body>` in
`app/layout.tsx`. This was invisible on pages with enough content to fill
the viewport (the marketing page, the original denser dashboard) but
produced a jarring white background gap below the fold on the new,
shorter dashboard layout. Fixed by moving the dark theme background off
`<body>` onto an inner wrapper `<div>` that Clerk doesn't touch.

**What was verified**: `pytest` (122 tests, unchanged, still pass),
`alembic upgrade head` applied cleanly, `tsc --noEmit` clean. The backend
AI Visibility auto-bundling was verified end-to-end for real via direct
API calls (a fresh project + audit against a real domain correctly
produced an auto-created tracked query, a real OpenAI call surfacing the
same `insufficient_quota` billing error as before, and Perplexity correctly
reported "not configured"). The new `/audits/compare` endpoint was
verified the same way across two real completed audits, correctly
diffing all 13 tools. The redesigned dashboard and History & Compare pages
were visually verified in a real signed-in browser session (screenshot,
confirmed both the layout fix and the new "Your sites"/compare UI render
correctly against the real signed-up user's actual data).

**What was not verified**: the audit report page's new AI Visibility
section and the full click-through "paste URL → Audit → report" flow were
not screenshotted in a live browser session -- repeated automated Clerk
sign-in-token generation (used to drive a browser session without the
real user's interactive login) was blocked by this environment's action
classifier after a few uses, reasonably treating repeated auth-token
minting as sensitive. The underlying data and logic this UI renders were
directly proven correct via the API-level verification above, and the
component code follows the same JSX/styling patterns already visually
confirmed elsewhere on the same page (severity summary boxes, per-tool
cards) -- but the actual rendered pixels for this specific section haven't
been eyeballed. Worth a manual click-through by a real user before
considering this fully done.

**No automated frontend tests**, consistent with this codebase's existing
Node-side testing gap (no test framework in `apps/web`/`apps/render-sidecar`
at all).

**Competitor comparison has no cleanup/dedup**: per explicit product
decision ("there must be both fresh report"), every competitor comparison
creates a brand-new `Project`/`Audit` row rather than reusing a prior
lookup of the same competitor domain -- intentional, but means repeated
comparisons against the same competitor accumulate `is_competitor_only`
rows with no pruning.

## Report export/share (public link + PDF)

First piece of a broader product-direction pivot agreed with the user
(2026-07-19): anonymous single-scan mode, pay-as-you-go metered billing,
and scheduled monitoring + auto-emailed comparison reports are the next
three pieces, **not yet started** -- this covers only export/share, the
one explicitly confirmed to build first. The target workflow: a
freelancer/consultant/agency scans a prospect's site and emails the owner
a professional report as an outreach pitch -- something the product could
not do at all before this (every report lived behind a Clerk login).

New nullable, unique-indexed `audits.share_token` column (migration
`048c3b2bb464`) -- null means "not shared." `POST /audits/{id}/share`
(idempotent) and `DELETE /audits/{id}/share` (revoke) mint/clear it;
`GET /public/audits/{share_token}` and `GET /public/audits/{share_token}/pdf`
(new `app/routers/public.py`, genuinely unauthenticated, IP-rate-limited via
new `enforce_public_rate_limit`) serve the full report -- same fidelity as
the dashboard's own view, not a teaser, since the point is credibility for
an outreach pitch. PDF generation reuses the existing Puppeteer sidecar: a
new `POST /pdf` route (`apps/render-sidecar/src/pdf.js`) opens the public
`/report/{token}` page in headless Chrome and prints it, so the PDF can
never drift from what the live page shows -- no separate template.

**What was verified end-to-end for real** (the established
direct-API-with-a-test-user-and-API-key pattern, inserted and cleaned up
via SQL): created a project + real completed audit against `example.net`;
`POST /audits/{id}/share` returned a token; `GET
/public/audits/{token}` with **no** `Authorization` header at all returned
the full report including the AI Visibility section; `GET
/public/audits/{token}/pdf` returned a genuine `%PDF-1.4` file (~110KB, 3
pages) that was opened and visually confirmed -- clean light-themed layout,
all 13 tool sections, severity summary, AI Visibility, and a footer
credit, faithfully matching the live page; `DELETE
/audits/{id}/share` followed by the same public `GET` correctly 404'd.

**Real bug caught during verification, not related to this feature's own
code**: the render sidecar needs restarting after adding a new Express
route to it -- obvious in hindsight, but worth noting since the first PDF
attempt 404'd against the sidecar's stale in-memory route table until it
was restarted. Not a code bug, a deployment-step reminder.

**What was not verified**: the dashboard's own "Share & Export" UI (the
Copy link/Download PDF/Revoke buttons in `audits/[id]/page.tsx`) was not
clicked through in a live authenticated browser session -- verified via
direct API calls instead, consistent with this session's established
Clerk-automation-is-flaky caveat. `tsc --noEmit` is clean and the component
follows the same patterns already visually confirmed elsewhere on the same
page.

**No automated tests for the DB/network-touching parts** (share/revoke
endpoints, public router, PDF rendering) -- consistent with this
codebase's whole-session convention (pure logic gets unit tests --
`generate_share_token()` does -- DB/HTTP-touching code gets manual
verification). No cleanup job for orphaned share tokens if an audit is
deleted (audits aren't currently deletable at all, so this isn't reachable
yet, but worth remembering if that changes).

**Real bug found and fixed later (2026-07-21), reported by the user**: the
public share page (`report/[shareToken]/page.tsx`) never actually had a
"Download PDF" link -- the backend's `GET /public/audits/{token}/pdf` has
been genuinely unauthenticated since this feature was built, but the only
PDF button that ever existed was in the *dashboard's* `ShareAndExport`
component, which sits behind Clerk auth. So a recipient who received a share
link but no account could view the report but had no way to download a PDF
of it, even though the API fully supported it. Fixed by adding the link
directly (the page already has `shareToken` from its own route param, no
extra API round-trip needed). Verified for real: `curl` against
`/public/audits/{token}/pdf` with no `Authorization` header returned a
genuine PDF. Separately, the render-sidecar's headless Chrome process had
also died mid-session (`GET :4000/health` showed `browser_connected: false`,
every `/pdf`/`/render`/`/accessibility` call was failing with a 502
`ConnectionClosedError`) -- unrelated code-wise, just needed the sidecar
process restarted to relaunch Chrome; it has no auto-recovery on browser
crash today.

## Anonymous single-scan mode

Second piece of the freemium pivot: `POST /public/scan` runs a real scan for a
signed-out visitor. Reuses `TOOL_REGISTRY` (`app/services/tools/base.py`) directly,
which already excludes Page Crawl (Celery-only), so a scan is a single ~10-25s
synchronous request covering the 12 fast tools; AI Visibility is excluded outright
since it costs real per-call money with no per-user quota to meter an anonymous
caller against, and the endpoint's own IP rate limit is the only cost guard here.

**Revised 2026-07-21, explicit user instruction**: originally built with **nothing
persisted at all** and findings CSS-blurred behind a "Sign up free" tease (see the
original verification notes below, kept for history). The user asked to remove the
gate entirely for now ("we will modify/change it later") after finding a signed-out
visitor genuinely couldn't read their own scan. Now: results *are* persisted (a real
`Project`/`Audit`/`AuditResult`, owned by a fixed system row,
`ANONYMOUS_SCAN_USER_ID = "system_anonymous_scan_user"` in `app/routers/public.py` --
chosen specifically so it can never collide with a real Clerk user id, which always
starts `user_...`, and so these projects can never appear in any real user's
dashboard) so a signed-out visitor can immediately share or download a PDF of their
own scan via the exact same `/public/audits/{share_token}` and
`/public/audits/{share_token}/pdf` machinery every other report already uses --
`ScanOut` now returns `share_token`/`share_url` alongside the results. The homepage
(`apps/web/app/page.tsx`) no longer blurs findings and adds "Copy share link"/
"Download PDF" buttons next to the (now non-blocking) "Sign up free" upsell.
AI Visibility and Page Crawl remain excluded from anonymous scans -- this only
changes what happens to the 12 fast-tool results after they're computed, not what
gets computed.

**What was verified for real (this revision)**: `pytest` still 138/138 (no test
coverage existed for this route before or after, consistent with the DB/network-
touching-code-gets-manual-verification convention); real `curl -X POST .../public/scan`
calls against `example.com` and `github.com` each returned a `share_token`/`share_url`
alongside the usual 12 results; `GET /public/audits/{token}` (no auth header)
returned the full composed report; `GET /public/audits/{token}/pdf` (no auth header)
returned a genuine PDF. `tsc --noEmit` is clean. **Not verified**: the homepage's
interactive scan flow wasn't screenshotted in a live browser session (no browser-
automation tool available this session) -- the JSX change is a straightforward
removal of the blur wrapper/overlay plus two new buttons using already-proven
patterns from `ShareAndExport`, and the underlying API responses driving it were
confirmed correct via the direct calls above, but the actual rendered page wasn't
eyeballed.

**Original scope, superseded above but kept for context**: this was built as **no
login and nothing persisted at all** -- no `Project`/`Audit`/`AuditResult` rows,
matching the product direction literally as first agreed.

New `app/core/domain_safety.py`: `normalize_domain` (extracted from
`app/routers/projects.py`, now shared) and `validate_public_domain` -- a basic SSRF
guard (rejects loopback/private/link-local resolved addresses) added specifically
because this is the first *unauthenticated* endpoint that runs tools against a
caller-supplied domain; not retrofitted onto the existing authenticated
project-creation path, which already has some accountability via the Clerk/API-key
account behind it. `app/core/rate_limit.py`'s fixed-window helper was generalized
(explicit `window_seconds`/`limit` instead of hardcoded 60s) so a new, much stricter
`enforce_anonymous_scan_rate_limit` (5/hour per IP, `anonymous_scan_limit_per_hour`
setting) could reuse it without duplicating the Redis logic.

Marketing homepage (`apps/web/app/page.tsx`) gets a hero search box for signed-out
visitors (signed-in visitors still see "Go to dashboard" unchanged). Results render
inline: real, unblurred score badges per tool (the trust-building numbers) with
findings CSS-blurred behind a "Sign up free to see N issues" overlay -- a **soft
tease, not a server-side redaction wall**, matching what SEOptimer's own live report
actually does (verified earlier this session: the real numbers are in the page,
just styled with blur) rather than building a harder redaction layer. Reversible
if scraping becomes a real problem later.

**What was verified for real**: `curl -X POST .../public/scan -d
'{"domain":"nexigosolutions.com"}'` returned exactly 12 tool results (no
`page_crawl`) with real scores in ~23s, and `projects`/`audits` row counts in
Postgres were confirmed unchanged before and after -- nothing persisted. The SSRF
guard was confirmed rejecting `localhost` and `127.0.0.1` (400) and a private
`192.168.x.x` address. The rate limiter was confirmed tripping (429) once the
5/hour-per-IP budget was exhausted by the verification calls above -- proven
correctly cumulative across every call to the endpoint, not just intentional
"real" scans, which is the right behavior (you don't want unlimited free probing
even with invalid domains). The homepage was screenshotted before and after a real
scan in a real (signed-out, no Clerk needed at all for this page) browser session,
confirming the blur/CTA renders as designed.

**What was not verified**: no automated tests for `POST /public/scan` itself or the
homepage's fetch/render logic (DB/network-touching and frontend, respectively --
consistent with the whole-session convention of manual verification for both).
`validate_public_domain`/`normalize_domain` do have unit tests (mocked DNS
resolution, matching this codebase's established pure-logic-gets-unit-tests pattern).

**Known gap carried forward, not solved here**: the existing authenticated
project-creation path (`POST /projects`) still has no SSRF guard -- deliberately out
of scope for this change (a working, already-tested code path), but worth
revisiting if that endpoint's trust model ever changes.

## Surfacing already-fetched tool data

Prompted by comparing our report against a second, differently-branded report for
the same site: several tools already compute richer data than any report surface
showed -- it just sat unused in `ToolResult.raw`, which no report view (dashboard,
public share page, PDF) ever reads, only `findings`.

- **Tech stack** (`tech_checker.py`) already detects technologies with a
  confidence score and confirmed/possible status -- now shown as a "Technologies
  detected" chip row under that tool's card, in both the dashboard
  (`audits/[id]/page.tsx`) and public share/PDF (`report/[shareToken]/page.tsx`)
  report pages. No backend change; `raw` was already in the API response.
- **Speed** (`speed.py`) already fetches PageSpeed Insights' "Opportunities" list
  but never turned any into a `Finding`. Now surfaces the top 3 as `info`-severity
  findings framed as "Improvement opportunity: ..." -- the one backend change in
  this batch, plus a new unit test (`tests/test_speed.py`).
- **HTTP headers** (`headers.py`) already captures every raw response header, not
  just the security-relevant subset already flagged as findings. Now shown as a
  collapsed "View all N response headers" `<details>` disclosure under that tool's
  card, both report pages.

**Tone constraint applied to all new copy** (see the feedback recorded alongside
this change): factual and calm, not alarmist -- the real reader is often a
non-technical site owner being pitched by a freelancer/consultant using this report,
and the goal is to inform, not manufacture urgency. The new Speed findings
deliberately use `info` severity and "Improvement opportunity" framing rather than
reading as new failures; technology detections use neutral chip styling, not
severity colors.

**What was verified for real**: a fresh audit against `nexigosolutions.com`
(temporary test user + API key, cleaned up after) confirmed
`tech_checker`'s `raw.detections` correctly includes `{"name": "Cloudflare",
"status": "confirmed", "confidence": 100}` and `speed`'s findings now include 3
`opportunity_*` entries with `info` severity and the expected message framing. The
public share report page was screenshotted for this same audit, confirming all
three additions render correctly together: the tech-stack chip, the collapsed
all-headers disclosure, and the three Improvement-opportunity lines under Speed.

**What was not verified**: the dashboard's own rendering of the same three
additions wasn't screenshotted in a live authenticated session (same Clerk-
automation-flakiness caveat as prior features) -- the dashboard and public pages
share the same data and near-identical component logic (deliberately duplicated
per-theme, not a shared component, matching this codebase's established pattern for
these two pages), and `tsc --noEmit` is clean, but the actual dashboard pixels
weren't eyeballed this time.

**Explicitly out of scope**: the anonymous homepage scan (`ScanResultItem`) still
omits `raw` by design from the prior feature, so it doesn't show tech-stack
detections -- extending that is a reasonable follow-up, not bundled into this
change. The compare page and CLI's `format.ts` also don't render this new data yet.

## Scheduled monitoring + Gmail-sent reports (Part A: manual trigger)

Third piece of the freemium/pay-as-you-go pivot. Per an explicit user correction
mid-design, this does **not** use a transactional email provider (Resend/Postmark/
SendGrid) -- reports are sent from the signed-in user's own Gmail account via the
Gmail API, so a freelancer/consultant's report to a prospect reads as a genuine
personal email, not "reports@seorepairkit.com" spam. Confirmed via live research
(not training-data assumption) that `gmail.send` is a **sensitive** Google OAuth
scope (standard ~10-day verification) rather than a **restricted** one
(`gmail.compose`/`https://mail.google.com/`, which need Google's heavier CASA
security assessment) -- an initial claim to the user that this would need CASA was
wrong and was corrected the same session.

**Backend** (`apps/api`): new `clerk_secret_key` setting (needed to call Clerk's
Backend API, separate from the JWKS-based JWT verification already used for
regular auth); `app/services/gmail_sender.py` (`get_google_access_token` via
Clerk's `GET /v1/users/{id}/oauth_access_tokens/google`, `send_email` via Gmail's
`users.messages.send`, MIME built with stdlib `email.mime`, deliberately omitting
the `From` header so Gmail fills in the authenticated account's real address);
`app/services/monitoring_email.py` (`build_report_email_html` -- inline-styled
HTML only, no flexbox/grid, since this renders in real email clients rather than a
browser or the PDF pipeline's headless Chrome); `app/services/monitoring.py`
(`send_monitoring_report` -- the shared core: runs a fresh audit via the existing
`run_audit`, waits for full completion including Page Crawl, reuses the existing
share-link mechanism, composes via the existing `compose_audit_out` diffing, sends
the email, stamps `monitoring_last_sent_at` -- built reusable so the future Celery
Beat task (Part B) can call the same function). Six new nullable `Project` columns
(migration `4ebdd716cf06`, applied). Three new/extended endpoints: `GET`/`PUT
/projects/{id}/monitoring` (config upsert) and `POST
/projects/{id}/monitoring/send-now` (the actual send, converting
`GmailNotConnectedError`/`MonitoringNotConfiguredError` into 400s).

**Frontend** (`apps/web`): `lib/api.ts` gains `Monitoring`/`MonitoringFrequency`
types and `getMonitoring`/`updateMonitoring`/`sendMonitoringReportNow` client
methods; a new `MonitoringPanel` component on `audits/[id]/page.tsx` -- "Connect
Gmail" button using Clerk's `reauthorize({ additionalScopes: ["...gmail.send"] })`
on the user's existing Google external account (per-user incremental consent,
Clerk's own documented pattern), plus a frequency/recipient-email/personal-message
form and a "Send report now" button. Deliberately does **not** try to detect
client-side whether the `gmail.send` scope was actually granted (Clerk's
`ExternalAccount.approvedScopes` shape wasn't worth relying on for this) -- the
backend's `GmailNotConnectedError` is the single source of truth, surfaced to the
user as a plain error message if they try to send before connecting.

**New prerequisite pages**: `apps/web/app/privacy/page.tsx` and `.../terms/page.tsx`
-- plain-language disclosure required as live URLs before Google will accept a
sensitive-scope verification submission, specifically calling out that the
`gmail.send` permission is send-only (no inbox read access) and only used on
explicit user action. Linked from the homepage footer. **Not reviewed by a
lawyer** -- fine for development/testing, worth a real review before relying on
them at production scale.

**What was verified**: `pytest` (138 passed, up from 132 -- 6 new tests for
`build_report_email_html` and `compute_next_run_at`, pure-logic only per this
codebase's established convention); `alembic upgrade head` applied the new
columns; `tsc --noEmit` clean; the API server was restarted and its OpenAPI
schema confirmed the three new `/projects/{id}/monitoring...` routes are
registered. A proactive security fix was made (not user-reported): the initial
`build_report_email_html` interpolated the free-text personal message directly
into HTML with no escaping, before that HTML becomes a real email sent to a third
party -- fixed with `html.escape()` and covered by a regression test.

**What was not verified: an actual email arriving in a real inbox from a real
connected Gmail account.** This requires a genuinely manual, external step the
user must do first -- add a test user (or complete verification) for the
`gmail.send` scope on the Google Cloud OAuth consent screen backing this Clerk
instance, since without it Google will reject the consent screen for anyone who
isn't already an approved test user. Until that's done, clicking "Connect Gmail"
in the dashboard will show Google's "app not verified" block for any account not
on the test-user list. This is the single remaining step before Part A can be
exercised end-to-end for real.

### Part B -- Celery Beat automation

Makes the schedule actually run itself instead of needing a manual "Send report
now" click: a new hourly-scheduled task (`run_due_monitoring_reports`,
`celery_app.conf.beat_schedule`) queries every `Project` with
`monitoring_enabled=True` and `monitoring_next_run_at` in the past, and for each
one calls the exact same `send_monitoring_report` the manual endpoint uses --
no separate send logic to keep in sync. Each due project gets its own
session/commit, and a failure on one (Gmail not connected, a transient audit
error, anything) is caught and logged rather than raised, so it can't roll back
or block the rest of the batch; `monitoring_next_run_at` is advanced to the next
interval either way, so a persistently-failing project retries on its normal
schedule instead of being hammered every hourly Beat tick. New third local-dev
process (`celery -A app.core.celery_app beat`), documented in the README
alongside the existing worker command.

**Real circular import hit and fixed during this work**: `app.tasks` importing
`app.services.monitoring` at module load time created a cycle
(`app.tasks -> app.services.monitoring -> app.services.orchestrator ->
app.tasks`, the last hop being `orchestrator`'s existing dispatch of the Page
Crawl Celery task). Fixed with a deferred (function-local) import inside the new
task, the standard fix for this shape of cycle -- not a restructure, since
`app.tasks` importing `orchestrator`-adjacent code was already an existing
one-way dependency this just happened to close into a loop.

**What was verified for real**: `celery -A app.core.celery_app worker` was
restarted and its startup log confirms `run_due_monitoring_reports` is
registered alongside `run_page_crawl`; `celery -A app.core.celery_app beat` was
started fresh and logs a clean "beat: Starting...". The task's actual logic was
exercised directly against real Postgres (temporary user + project inserted via
SQL, matching this codebase's established manual-verification pattern): a
project with `monitoring_enabled=True`, `monitoring_next_run_at` an hour in the
past, and deliberately no `monitoring_recipient_email` was correctly picked up
as due, its failure (`MonitoringNotConfiguredError`) was caught and logged
without crashing the task, and `monitoring_next_run_at` was correctly advanced
~7 days out per its `weekly` frequency; a second run immediately after
confirmed the same project was no longer picked up (now correctly not due).
Test data was deleted afterward.

**What was not verified: a real project actually being picked up and
successfully emailing a live report via Beat.** Same underlying gap as Part A --
requires a real Gmail-connected account (blocked on the user's Google Cloud
Console test-user step) and, additionally, a project that's actually had
monitoring enabled through the real dashboard UI rather than inserted directly.
Once the Google Cloud Console step is done, the cleanest real check is: enable
monitoring on a real project with a real recipient email through the dashboard,
set `monitoring_next_run_at` a minute into the past via SQL, and watch the
running Beat + worker pick it up on the next hourly tick (or trigger it early
with `run_due_monitoring_reports_task.delay()` from a shell).

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

**API-level rate limiting was added in Phase 5a** (`app/core/rate_limit.py`,
60 requests/minute per user via Redis fixed window) on the routes reachable
via `get_current_user_or_api_key` (`/projects`, `/audits`, `/geo`). The
`/api-keys` management endpoints themselves (Clerk-only) are not
rate-limited, on the assumption that dashboard-authenticated key management
isn't the abuse surface a public API needs guarding against.

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
