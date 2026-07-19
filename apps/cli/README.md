# seokit-cli

Command-line client for SEO Repair Kit -- run audits and gate CI builds on
findings. Authenticates with an API key (`srk_live_...`, created via the
dashboard's `/api-keys` endpoint) rather than a Clerk session.

## Install / build

No npm-registry package yet -- build from source:

```bash
cd apps/cli
npm install
npm run build
node dist/src/cli.js --help
```

## Configuration

| Flag | Env var | Default |
|---|---|---|
| `--api-key <key>` | `SRK_API_KEY` | *(required)* |
| `--api-url <url>` | `SRK_API_URL` | `http://localhost:8000` |

There's no hosted production API yet, so `SRK_API_URL` must point at wherever
your instance actually runs.

## Commands

```bash
seokit projects list
seokit projects create <domain> [--brand-name <name>]

seokit audit run --project-id <uuid> [--wait] [--timeout <seconds>] [--fail-on <severity>] [--json]
seokit audit get <audit-id> [--json]
```

`audit run --wait --fail-on <severity>` is the CI-facing command: it creates
an audit, polls until every tool (including the Page Crawl background task)
has finished, prints a summary, and exits 1 if any finding at or above
`<severity>` (`critical` > `high` > `medium` > `low` > `info`) was found.

## GitHub Action

```yaml
- uses: pretyiman/iloveseo/.github/actions/seo-audit@main
  with:
    api-key: ${{ secrets.SRK_API_KEY }}
    api-url: https://your-seokit-instance.example.com
    project-id: <your-project-id>
    fail-on: high
```

The step's exit code is the gate -- no output-parsing required for the job
to fail when `fail-on` is breached.
