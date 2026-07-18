"use client";

import { use, useEffect, useRef, useState } from "react";
import { useApiClient, type Audit, type Finding } from "@/lib/api";

const SEVERITY_ORDER: Finding["severity"][] = ["critical", "high", "medium", "low", "info"];

const SEVERITY_STYLES: Record<Finding["severity"], string> = {
  critical: "bg-red-950 text-red-300 border-red-800",
  high: "bg-orange-950 text-orange-300 border-orange-800",
  medium: "bg-yellow-950 text-yellow-300 border-yellow-800",
  low: "bg-blue-950 text-blue-300 border-blue-800",
  info: "bg-neutral-800 text-neutral-400 border-neutral-700",
};

const POLL_INTERVAL_MS = 2000;

export default function AuditResultsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const api = useApiClient();
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const a = await api.getAudit(id);
        setAudit(a);
        const stillRunning = a.results.some((r) => r.status === "running");
        if ((a.status === "completed" || a.status === "failed") && !stillRunning) {
          if (intervalRef.current) clearInterval(intervalRef.current);
        }
      } catch (e) {
        setError(String(e));
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    }

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const allFindings = audit?.results.flatMap((r) => r.findings.map((f) => ({ ...f, tool: r.tool }))) ?? [];
  const counts = SEVERITY_ORDER.reduce<Record<string, number>>((acc, sev) => {
    acc[sev] = allFindings.filter((f) => f.severity === sev).length;
    return acc;
  }, {});

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <h1 className="mb-2 text-2xl font-semibold text-neutral-50">Audit results</h1>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!audit && !error && <p className="text-sm text-neutral-500">Loading...</p>}

      {audit && (
        <>
          <p className="mb-6 text-sm text-neutral-400">
            Status: <span className="font-medium text-neutral-200">{audit.status}</span>
            {audit.status === "running" && " -- results appear below as each tool finishes"}
          </p>

          <div className="mb-8 flex gap-3">
            {SEVERITY_ORDER.map((sev) => (
              <div
                key={sev}
                className={`flex-1 rounded-lg border px-3 py-2 text-center ${SEVERITY_STYLES[sev]}`}
              >
                <div className="text-lg font-semibold">{counts[sev]}</div>
                <div className="text-xs capitalize">{sev}</div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-4">
            {audit.results.map((result) => (
              <div key={result.tool} className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="font-medium text-neutral-100">{result.tool.replace(/_/g, " ")}</h2>
                  {result.status === "running" ? (
                    <span className="text-sm text-neutral-400">Running...</span>
                  ) : (
                    result.score !== null && (
                      <span className="text-sm text-neutral-400">Score: {result.score}/100</span>
                    )
                  )}
                </div>
                {result.status === "running" && result.progress ? (
                  <div>
                    <div className="mb-1 h-2 w-full overflow-hidden rounded-full bg-neutral-800">
                      <div
                        className="h-full bg-blue-500 transition-all"
                        style={{
                          width: `${Math.min(
                            100,
                            (result.progress.pages_crawled / Math.max(result.progress.pages_total_estimate, 1)) * 100
                          )}%`,
                        }}
                      />
                    </div>
                    <p className="text-xs text-neutral-500">
                      {result.progress.pages_crawled} / {result.progress.pages_total_estimate} pages crawled
                    </p>
                  </div>
                ) : result.findings.length === 0 ? (
                  <p className="text-sm text-neutral-500">No issues found.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {result.findings.map((f, i) => (
                      <li
                        key={i}
                        className={`rounded border px-3 py-1.5 text-sm ${SEVERITY_STYLES[f.severity]}`}
                      >
                        {f.message}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}

            {audit.results.length === 0 && audit.status !== "completed" && (
              <p className="text-sm text-neutral-500">Waiting for the first tool to finish...</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
