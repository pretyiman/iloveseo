"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DashboardNav } from "../_components/DashboardNav";
import { useApiClient, type Audit, type AuditSummary, type Project } from "@/lib/api";

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

async function waitForAudit(api: ReturnType<typeof useApiClient>, auditId: string): Promise<Audit> {
  while (true) {
    const audit = await api.getAudit(auditId);
    const stillRunning = audit.results.some((r) => r.status === "running");
    if ((audit.status === "completed" || audit.status === "failed") && !stillRunning) {
      return audit;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}

export default function HistoryPage() {
  const api = useApiClient();
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [audits, setAudits] = useState<AuditSummary[]>([]);
  const [auditA, setAuditA] = useState("");
  const [auditB, setAuditB] = useState("");
  const [competitorDomain, setCompetitorDomain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningCompetitor, setRunningCompetitor] = useState(false);

  useEffect(() => {
    api
      .listProjects()
      .then((projs) => {
        setProjects(projs);
        if (projs[0]) setSelectedProjectId(projs[0].id);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    setAuditA("");
    setAuditB("");
    api
      .listProjectAudits(selectedProjectId)
      .then(setAudits)
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProjectId]);

  function handleCompareOwn() {
    if (!auditA || !auditB) return;
    router.push(`/dashboard/compare?a=${auditA}&b=${auditB}`);
  }

  async function handleCompareCompetitor(e: React.FormEvent) {
    e.preventDefault();
    const domain = normalizeDomain(competitorDomain);
    if (!auditA || !domain) return;

    setRunningCompetitor(true);
    setError(null);
    try {
      const project = await api.createProject(domain, undefined, true);
      const audit = await api.createAudit(project.id);
      const finished = await waitForAudit(api, audit.id);
      router.push(`/dashboard/compare?a=${auditA}&b=${finished.id}`);
    } catch (err) {
      setError(String(err));
      setRunningCompetitor(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <DashboardNav />
      <h1 className="mb-8 text-2xl font-semibold text-neutral-50">History & Compare</h1>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-neutral-500">Loading...</p>}

      {!loading && projects.length === 0 && (
        <p className="text-sm text-neutral-500">No sites yet -- run an audit first from the Audit tab.</p>
      )}

      {!loading && projects.length > 0 && (
        <>
          <div className="mb-8">
            <label className="mb-2 block text-sm font-medium text-neutral-400">Site</label>
            <select
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="w-full rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-2 text-neutral-100"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.domain}
                </option>
              ))}
            </select>
          </div>

          {audits.length === 0 ? (
            <p className="text-sm text-neutral-500">No audits run for this site yet.</p>
          ) : (
            <>
              <div className="mb-8 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                <h2 className="mb-3 font-medium text-neutral-100">Compare your own reports</h2>
                <div className="flex items-center gap-3">
                  <select
                    value={auditA}
                    onChange={(e) => setAuditA(e.target.value)}
                    className="flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100"
                  >
                    <option value="">Select a report...</option>
                    {audits.map((a) => (
                      <option key={a.id} value={a.id}>
                        {new Date(a.created_at).toLocaleString()} ({a.status})
                      </option>
                    ))}
                  </select>
                  <span className="text-sm text-neutral-500">vs.</span>
                  <select
                    value={auditB}
                    onChange={(e) => setAuditB(e.target.value)}
                    className="flex-1 rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100"
                  >
                    <option value="">Select a report...</option>
                    {audits.map((a) => (
                      <option key={a.id} value={a.id}>
                        {new Date(a.created_at).toLocaleString()} ({a.status})
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleCompareOwn}
                  disabled={!auditA || !auditB}
                  className="mt-3 rounded-full bg-neutral-50 px-4 py-1.5 text-sm font-medium text-neutral-950 hover:bg-neutral-200 disabled:opacity-50"
                >
                  Compare
                </button>
              </div>

              <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                <h2 className="mb-3 font-medium text-neutral-100">Compare against a competitor</h2>
                <p className="mb-3 text-xs text-neutral-500">
                  Runs a brand-new audit against the competitor's domain right now, then compares it against one of
                  your own reports.
                </p>
                <form onSubmit={handleCompareCompetitor} className="flex flex-col gap-3">
                  <select
                    value={auditA}
                    onChange={(e) => setAuditA(e.target.value)}
                    className="rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100"
                  >
                    <option value="">Your baseline report...</option>
                    {audits.map((a) => (
                      <option key={a.id} value={a.id}>
                        {new Date(a.created_at).toLocaleString()} ({a.status})
                      </option>
                    ))}
                  </select>
                  <input
                    value={competitorDomain}
                    onChange={(e) => setCompetitorDomain(e.target.value)}
                    placeholder="competitor.com"
                    className="rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600"
                  />
                  <button
                    type="submit"
                    disabled={!auditA || !competitorDomain || runningCompetitor}
                    className="self-start rounded-full bg-neutral-50 px-4 py-1.5 text-sm font-medium text-neutral-950 hover:bg-neutral-200 disabled:opacity-50"
                  >
                    {runningCompetitor ? "Running competitor audit..." : "Run & compare"}
                  </button>
                </form>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
