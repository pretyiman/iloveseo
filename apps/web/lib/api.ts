"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Project = {
  id: string;
  domain: string;
  brand_name: string | null;
  created_at: string;
};

export type TrackedQuery = {
  id: string;
  project_id: string;
  query_text: string;
  competitor_domains: string[];
  active: boolean;
  created_at: string;
};

export type GeoCheck = {
  id: string;
  tracked_query_id: string;
  provider: "perplexity" | "openai";
  status: "ok" | "error";
  cited: boolean | null;
  position: number | null;
  competitor_mentions: Record<string, boolean>;
  citation_urls: string[];
  response_text: string | null;
  error_message: string | null;
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

export type AiVisibilityProvider = {
  provider: "perplexity" | "openai";
  configured: boolean;
  status: "ok" | "error" | null;
  cited: boolean | null;
  position: number | null;
  error_message: string | null;
  checked_at: string | null;
};

export type AiVisibility = {
  query_text: string | null;
  providers: AiVisibilityProvider[];
};

export type Audit = {
  id: string;
  project_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
  results: AuditResult[];
  ai_visibility: AiVisibility | null;
};

export type AuditCompare = {
  audit_a: Audit;
  audit_b: Audit;
  diff_by_tool: Record<string, AuditDiff | null>;
};

export type AuditSummary = {
  id: string;
  status: Audit["status"];
  created_at: string;
  completed_at: string | null;
};

export type AuditShare = {
  share_token: string;
  share_url: string;
};

export type ScanResultItem = {
  tool: string;
  status: "ok" | "error";
  score: number | null;
  findings: Finding[];
};

export type ScanResult = {
  domain: string;
  results: ScanResultItem[];
};

/** Anonymous, unauthenticated scan -- no Clerk token, matching the public
 * report page's plain-fetch pattern. Not part of useApiClient() since it
 * deliberately isn't tied to a signed-in session at all. */
export async function scanPublicDomain(domain: string): Promise<ScanResult> {
  const res = await fetch(`${API_URL}/public/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ domain }),
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<ScanResult>;
}

/** Thin authenticated fetch wrapper -- attaches the Clerk session token to
 * every request so the API's `get_current_user` dependency can verify it. */
export function useApiClient() {
  const { getToken } = useAuth();

  const request = useCallback(
    async <T,>(path: string, init?: RequestInit): Promise<T> => {
      const token = await getToken();
      const res = await fetch(`${API_URL}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...init?.headers,
        },
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`${res.status} ${res.statusText}: ${body}`);
      }
      if (res.status === 204) {
        return undefined as T;
      }
      return res.json() as Promise<T>;
    },
    [getToken]
  );

  return {
    listProjects: () => request<Project[]>("/projects"),
    createProject: (domain: string, brandName?: string, isCompetitorOnly = false) =>
      request<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ domain, brand_name: brandName || null, is_competitor_only: isCompetitorOnly }),
      }),
    createAudit: (projectId: string) =>
      request<Audit>("/audits", { method: "POST", body: JSON.stringify({ project_id: projectId }) }),
    getAudit: (auditId: string) => request<Audit>(`/audits/${auditId}`),
    compareAudits: (a: string, b: string) => request<AuditCompare>(`/audits/compare?a=${a}&b=${b}`),
    shareAudit: (auditId: string) => request<AuditShare>(`/audits/${auditId}/share`, { method: "POST" }),
    revokeAuditShare: (auditId: string) => request<void>(`/audits/${auditId}/share`, { method: "DELETE" }),
    listProjectAudits: (projectId: string) => request<AuditSummary[]>(`/projects/${projectId}/audits`),
    listTrackedQueries: (projectId: string) => request<TrackedQuery[]>(`/projects/${projectId}/tracked-queries`),
    createTrackedQuery: (projectId: string, queryText: string, competitorDomains: string[]) =>
      request<TrackedQuery>(`/projects/${projectId}/tracked-queries`, {
        method: "POST",
        body: JSON.stringify({ query_text: queryText, competitor_domains: competitorDomains }),
      }),
    deleteTrackedQuery: (trackedQueryId: string) =>
      request<void>(`/tracked-queries/${trackedQueryId}`, { method: "DELETE" }),
    runGeoCheck: (trackedQueryId: string) =>
      request<GeoCheck[]>(`/tracked-queries/${trackedQueryId}/check`, { method: "POST" }),
    listGeoChecks: (trackedQueryId: string) => request<GeoCheck[]>(`/tracked-queries/${trackedQueryId}/checks`),
  };
}
