import { Audit, Project } from "./types";

export type ClientOptions = {
  apiUrl: string;
  apiKey: string;
};

export function resolveClientOptions(opts: { apiUrl?: string; apiKey?: string }): ClientOptions {
  // "||" not "??" -- an empty string must fall through too, since GitHub
  // Actions sets an unset `inputs.*` to "" in an env: block rather than
  // omitting the variable entirely.
  const apiUrl = opts.apiUrl || process.env.SRK_API_URL || "http://localhost:8000";
  const apiKey = opts.apiKey || process.env.SRK_API_KEY;
  if (!apiKey) {
    throw new Error("No API key provided -- set SRK_API_KEY or pass --api-key");
  }
  return { apiUrl, apiKey };
}

/** Thin authenticated fetch wrapper -- mirrors apps/web/lib/api.ts's
 * request() so the CLI and dashboard behave identically against the same
 * API, just with an API key instead of a Clerk session token. */
export function createClient({ apiUrl, apiKey }: ClientOptions) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${apiUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
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
  }

  return {
    listProjects: () => request<Project[]>("/projects"),
    createProject: (domain: string, brandName?: string) =>
      request<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({ domain, brand_name: brandName ?? null }),
      }),
    createAudit: (projectId: string) =>
      request<Audit>("/audits", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId }),
      }),
    getAudit: (auditId: string) => request<Audit>(`/audits/${auditId}`),
  };
}

export type ApiClient = ReturnType<typeof createClient>;
