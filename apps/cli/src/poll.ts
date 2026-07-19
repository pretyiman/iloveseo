import { ApiClient } from "./client";
import { Audit } from "./types";

const TERMINAL_STATUSES = new Set<Audit["status"]>(["completed", "failed"]);

function isFullyDone(audit: Audit): boolean {
  // Audit.status flips to "completed" as soon as the fast asyncio.gather
  // batch finishes, independently of whether the Celery Page Crawl task is
  // still running in the background -- so we also require every result
  // row to have left the "running" state before calling it done.
  return TERMINAL_STATUSES.has(audit.status) && audit.results.every((r) => r.status !== "running");
}

export type WaitOptions = {
  timeoutMs?: number;
  intervalMs?: number;
};

export async function waitForAudit(client: ApiClient, auditId: string, opts: WaitOptions = {}): Promise<Audit> {
  const timeoutMs = opts.timeoutMs ?? 300_000;
  const intervalMs = opts.intervalMs ?? 2_000;
  const deadline = Date.now() + timeoutMs;

  while (true) {
    const audit = await client.getAudit(auditId);
    if (isFullyDone(audit)) {
      return audit;
    }
    if (Date.now() >= deadline) {
      throw new Error(`Timed out after ${timeoutMs}ms waiting for audit ${auditId} to complete`);
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
