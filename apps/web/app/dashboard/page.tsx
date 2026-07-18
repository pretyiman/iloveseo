"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useApiClient, type Project } from "@/lib/api";

export default function DashboardPage() {
  const api = useApiClient();
  const [projects, setProjects] = useState<Project[]>([]);
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningAuditFor, setRunningAuditFor] = useState<string | null>(null);

  useEffect(() => {
    api
      .listProjects()
      .then(setProjects)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleAddDomain(e: React.FormEvent) {
    e.preventDefault();
    if (!domain.trim()) return;
    try {
      const project = await api.createProject(domain.trim());
      setProjects((prev) => [project, ...prev]);
      setDomain("");
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleRunAudit(projectId: string) {
    setRunningAuditFor(projectId);
    try {
      const audit = await api.createAudit(projectId);
      window.location.href = `/dashboard/audits/${audit.id}`;
    } catch (e) {
      setError(String(e));
      setRunningAuditFor(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <div className="mb-10 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-neutral-50">Projects</h1>
        <UserButton />
      </div>

      <form onSubmit={handleAddDomain} className="mb-8 flex gap-3">
        <input
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          placeholder="example.com"
          className="flex-1 rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-2 text-neutral-100 placeholder:text-neutral-500"
        />
        <button
          type="submit"
          className="rounded-lg bg-neutral-50 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-200"
        >
          Add domain
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-neutral-500">Loading projects...</p>}

      <ul className="flex flex-col gap-3">
        {projects.map((p) => (
          <li
            key={p.id}
            className="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3"
          >
            <span className="text-neutral-100">{p.domain}</span>
            <div className="flex items-center gap-2">
              <Link
                href={`/dashboard/projects/${p.id}/history`}
                className="rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-100 hover:border-neutral-500"
              >
                History
              </Link>
              <button
                onClick={() => handleRunAudit(p.id)}
                disabled={runningAuditFor === p.id}
                className="rounded-full border border-neutral-700 px-4 py-1.5 text-sm text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
              >
                {runningAuditFor === p.id ? "Starting..." : "Run audit"}
              </button>
            </div>
          </li>
        ))}
        {!loading && projects.length === 0 && (
          <p className="text-sm text-neutral-500">No projects yet -- add a domain above.</p>
        )}
      </ul>

      <p className="mt-6 text-xs text-neutral-600">
        Free plan: 10 audit runs / month.
      </p>
    </div>
  );
}
