import { Audit, Severity } from "./types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

export function isValidSeverity(value: string): value is Severity {
  return (SEVERITY_ORDER as string[]).includes(value);
}

/** True if any finding across any tool's results is at least as severe as
 * `threshold` (lower index in SEVERITY_ORDER = more severe). */
export function hasFindingAtOrAbove(audit: Audit, threshold: Severity): boolean {
  const thresholdRank = SEVERITY_ORDER.indexOf(threshold);
  return audit.results.some((result) =>
    result.findings.some((finding) => SEVERITY_ORDER.indexOf(finding.severity) <= thresholdRank)
  );
}
