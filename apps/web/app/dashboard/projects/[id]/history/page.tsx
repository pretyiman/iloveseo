"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useApiClient, type AuditSummary } from "@/lib/api";

const STATUS_STYLES: Record<AuditSummary["status"], string> = {
  pending: "text-neutral-500",
  running: "text-blue-400",
  completed: "text-green-400",
  failed: "text-red-400",
};

export default function ProjectHistoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const api = useApiClient();
  const [audits, setAudits] = useState<AuditSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listProjectAudits(id)
      .then(setAudits)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-neutral-50">Audit history</h1>
        <Link href="/dashboard" className="text-sm text-neutral-400 hover:text-neutral-200">
          Back to projects
        </Link>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-neutral-500">Loading...</p>}

      <ul className="flex flex-col gap-3">
        {audits.map((a) => (
          <li key={a.id}>
            <Link
              href={`/dashboard/audits/${a.id}`}
              className="flex items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3 hover:border-neutral-600"
            >
              <span className="text-sm text-neutral-300">{new Date(a.created_at).toLocaleString()}</span>
              <span className={`text-sm font-medium ${STATUS_STYLES[a.status]}`}>{a.status}</span>
            </Link>
          </li>
        ))}
        {!loading && audits.length === 0 && (
          <p className="text-sm text-neutral-500">No audits run for this project yet.</p>
        )}
      </ul>
    </div>
  );
}
