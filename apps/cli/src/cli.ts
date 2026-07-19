#!/usr/bin/env node
import { Command } from "commander";
import { createClient, resolveClientOptions } from "./client";
import { formatAuditSummary } from "./format";
import { waitForAudit } from "./poll";
import { hasFindingAtOrAbove, isValidSeverity } from "./severity";
import { Severity } from "./types";

const program = new Command();

program
  .name("seokit")
  .description("SEO Repair Kit CLI -- run audits and gate CI builds on findings")
  .version("0.1.0")
  .option("--api-key <key>", "API key (or set SRK_API_KEY)")
  .option("--api-url <url>", "API base URL (or set SRK_API_URL, default http://localhost:8000)");

function clientFrom(command: Command) {
  const globalOpts = command.optsWithGlobals();
  const { apiUrl, apiKey } = resolveClientOptions({ apiUrl: globalOpts.apiUrl, apiKey: globalOpts.apiKey });
  return createClient({ apiUrl, apiKey });
}

async function run(fn: () => Promise<void>): Promise<void> {
  try {
    await fn();
  } catch (err) {
    console.error(`Error: ${err instanceof Error ? err.message : String(err)}`);
    process.exitCode = 1;
  }
}

const projects = program.command("projects").description("Manage projects");

projects
  .command("list")
  .description("List your projects")
  .action((options, command: Command) =>
    run(async () => {
      const client = clientFrom(command);
      const items = await client.listProjects();
      if (items.length === 0) {
        console.log("No projects yet.");
        return;
      }
      for (const p of items) {
        console.log(`${p.id}  ${p.domain}${p.brand_name ? `  (${p.brand_name})` : ""}  created ${p.created_at}`);
      }
    })
  );

projects
  .command("create <domain>")
  .description("Create a new project")
  .option("--brand-name <name>", "Brand name, used by the GEO tracker")
  .action((domain: string, options, command: Command) =>
    run(async () => {
      const client = clientFrom(command);
      const project = await client.createProject(domain, options.brandName);
      console.log(`Created project ${project.id} (${project.domain})`);
    })
  );

const audit = program.command("audit").description("Run and inspect audits");

audit
  .command("run")
  .description("Start an audit for a project")
  .requiredOption("--project-id <uuid>", "Project id to audit")
  .option("--wait", "Wait for the audit to finish before exiting", false)
  .option("--timeout <seconds>", "Max seconds to wait with --wait (default 300)", "300")
  .option("--fail-on <severity>", "Exit 1 if any finding at or above this severity exists (requires --wait)")
  .option("--json", "Print raw JSON instead of a human-readable summary", false)
  .action((options, command: Command) =>
    run(async () => {
      if (options.failOn && !isValidSeverity(options.failOn)) {
        throw new Error(`--fail-on must be one of critical, high, medium, low, info (got "${options.failOn}")`);
      }
      const client = clientFrom(command);
      let audit = await client.createAudit(options.projectId);

      if (options.wait) {
        audit = await waitForAudit(client, audit.id, { timeoutMs: Number(options.timeout) * 1000 });
      } else {
        console.log(`Created audit ${audit.id} (status: ${audit.status})`);
        return;
      }

      if (options.json) {
        console.log(JSON.stringify(audit, null, 2));
      } else {
        console.log(formatAuditSummary(audit));
      }

      if (options.failOn && hasFindingAtOrAbove(audit, options.failOn as Severity)) {
        console.error(`\nFound a finding at or above severity "${options.failOn}".`);
        process.exitCode = 1;
      }
    })
  );

audit
  .command("get <auditId>")
  .description("Fetch the current state of an audit")
  .option("--json", "Print raw JSON instead of a human-readable summary", false)
  .action((auditId: string, options, command: Command) =>
    run(async () => {
      const client = clientFrom(command);
      const audit = await client.getAudit(auditId);
      console.log(options.json ? JSON.stringify(audit, null, 2) : formatAuditSummary(audit));
    })
  );

program.parseAsync(process.argv);
