"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DashboardNav } from "./_components/DashboardNav";
import { useApiClient, type Audit, type Project } from "@/lib/api";

function normalizeDomain(value: string): string {
  value = value.trim();
  if (value.includes("://")) {
    try {
      value = new URL(value).hostname;
    } catch {
      // fall through, use as-is
    }
  }
  return value.replace(/\/+$/, "").replace(/^www\./, "");
}

const STATUS_LABELS: Record<Audit["status"], string> = {
  pending: "Queued",
  running: "Auditing...",
  completed: "Completed",
  failed: "Failed",
};

export default function DashboardPage() {
  const api = useApiClient();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [latestStatus, setLatestStatus] = useState<Record<string, { status: Audit["status"]; created_at: string }>>(
    {}
  );
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then(async (projs) => {
        setProjects(projs);
        const entries = await Promise.all(
          projs.map(async (p) => {
            const audits = await api.listProjectAudits(p.id);
            return [p.id, audits[0]] as const;
          })
        );
        setLatestStatus(
          Object.fromEntries(
            entries.filter(([, a]) => a).map(([id, a]) => [id, { status: a.status, created_at: a.created_at }])
          )
        );
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAudit(e: React.FormEvent) {
    e.preventDefault();
    const normalized = normalizeDomain(domain);
    if (!normalized) return;

    setAuditing(true);
    setError(null);
    try {
      const existing = projects.find((p) => p.domain === normalized);
      const project = existing ?? (await api.createProject(normalized));
      const audit = await api.createAudit(project.id);
      router.push(`/dashboard/audits/${audit.id}`);
    } catch (e) {
      setError(String(e));
      setAuditing(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <DashboardNav />

      <div className="mb-12 rounded-2xl border border-neutral-800 bg-gradient-to-b from-neutral-900 to-neutral-950 p-8 text-center">
        <h1 className="text-2xl font-semibold text-neutral-50 sm:text-3xl">Audit your site</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Paste a URL to run every SEO/site-health check and AI Visibility in one report.
        </p>

        <form onSubmit={handleAudit} className="mx-auto mt-6 flex max-w-md gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="example.com"
              className="w-full rounded-full border border-neutral-700 bg-neutral-900 py-2.5 pl-10 pr-4 text-neutral-100 placeholder:text-neutral-500 focus:border-neutral-500 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={auditing}
            className="shrink-0 rounded-full bg-neutral-50 px-6 py-2.5 text-sm font-medium text-neutral-950 hover:bg-neutral-200 disabled:opacity-50"
          >
            {auditing ? "Starting..." : "Audit"}
          </button>
        </form>
      </div>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-neutral-500">Loading your sites...</p>}

      {!loading && projects.length > 0 && (
        <>
          <h2 className="mb-3 text-sm font-medium text-neutral-400">Your sites</h2>
          <ul className="flex flex-col gap-2">
            {projects.map((p) => {
              const latest = latestStatus[p.id];
              return (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={async () => {
                      setAuditing(true);
                      setError(null);
                      try {
                        if (latest) {
                          const audits = await api.listProjectAudits(p.id);
                          if (audits[0]) {
                            router.push(`/dashboard/audits/${audits[0].id}`);
                            return;
                          }
                        }
                        const audit = await api.createAudit(p.id);
                        router.push(`/dashboard/audits/${audit.id}`);
                      } catch (err) {
                        setError(String(err));
                        setAuditing(false);
                      }
                    }}
                    className="flex w-full items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3 text-left hover:border-neutral-600"
                  >
                    <span className="text-neutral-100">{p.domain}</span>
                    <span className="text-sm text-neutral-500">
                      {latest ? (
                        <>
                          {STATUS_LABELS[latest.status]} · {new Date(latest.created_at).toLocaleDateString()}
                        </>
                      ) : (
                        "Run first audit"
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}

      {!loading && projects.length === 0 && (
        <p className="text-center text-sm text-neutral-500">No sites audited yet -- paste a URL above.</p>
      )}
    </div>
  );
}
