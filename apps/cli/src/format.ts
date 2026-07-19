import { Audit } from "./types";
import { SEVERITY_ORDER } from "./severity";

export function formatAuditSummary(audit: Audit): string {
  const lines: string[] = [];
  lines.push(`Audit ${audit.id} (project ${audit.project_id}) -- ${audit.status}`);
  lines.push("");

  for (const result of audit.results) {
    const scoreLabel = result.score === null ? "n/a" : String(result.score);
    lines.push(`  ${result.tool.padEnd(20)} score=${scoreLabel.padEnd(5)} status=${result.status}`);

    const counts = new Map<string, number>();
    for (const finding of result.findings) {
      counts.set(finding.severity, (counts.get(finding.severity) ?? 0) + 1);
    }
    if (counts.size > 0) {
      const parts = SEVERITY_ORDER.filter((s) => counts.has(s)).map((s) => `${s}=${counts.get(s)}`);
      lines.push(`    findings: ${parts.join(", ")}`);
    }
  }

  return lines.join("\n");
}
