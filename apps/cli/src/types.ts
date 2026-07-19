// Mirrors apps/web/lib/api.ts field-for-field -- same API, same shapes.

export type Project = {
  id: string;
  domain: string;
  brand_name: string | null;
  created_at: string;
};

export type Finding = {
  severity: "critical" | "high" | "medium" | "low" | "info";
  code: string;
  message: string;
};

export type AuditDiff = {
  previous_score: number | null;
  score_delta: number | null;
  new_finding_codes: string[];
  resolved_finding_codes: string[];
};

export type AuditResult = {
  tool: string;
  status: "running" | "ok" | "error";
  score: number | null;
  findings: Finding[];
  raw: Record<string, unknown>;
  progress: { pages_crawled: number; pages_total_estimate: number } | null;
  diff: AuditDiff | null;
  created_at: string;
};

export type Audit = {
  id: string;
  project_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
  results: AuditResult[];
};

export type Severity = Finding["severity"];
