"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Project = {
  id: string;
  domain: string;
  created_at: string;
};

export type Finding = {
  severity: "critical" | "high" | "medium" | "low" | "info";
  code: string;
  message: string;
};

export type AuditResult = {
  tool: string;
  status: "running" | "ok" | "error";
  score: number | null;
  findings: Finding[];
  raw: Record<string, unknown>;
  progress: { pages_crawled: number; pages_total_estimate: number } | null;
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
      return res.json() as Promise<T>;
    },
    [getToken]
  );

  return {
    listProjects: () => request<Project[]>("/projects"),
    createProject: (domain: string) =>
      request<Project>("/projects", { method: "POST", body: JSON.stringify({ domain }) }),
    createAudit: (projectId: string) =>
      request<Audit>("/audits", { method: "POST", body: JSON.stringify({ project_id: projectId }) }),
    getAudit: (auditId: string) => request<Audit>(`/audits/${auditId}`),
  };
}
