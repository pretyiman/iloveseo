"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { DashboardNav } from "../_components/DashboardNav";
import { ScoreBadge } from "../_components/ScoreBadge";
import { useApiClient, type AuditCompare } from "@/lib/api";

export default function ComparePage() {
  const api = useApiClient();
  const searchParams = useSearchParams();
  const a = searchParams.get("a");
  const b = searchParams.get("b");
  const [compare, setCompare] = useState<AuditCompare | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!a || !b) {
      setError("Missing audits to compare.");
      setLoading(false);
      return;
    }
    api
      .compareAudits(a, b)
      .then(setCompare)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, b]);

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <DashboardNav />
      <h1 className="mb-2 text-2xl font-semibold text-neutral-50">Comparison</h1>

      {error && <p className="text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-neutral-500">Loading...</p>}

      {compare && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 text-sm text-neutral-400">
            <div>
              <p className="font-medium text-neutral-200">Report A</p>
              <p>{new Date(compare.audit_a.created_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="font-medium text-neutral-200">Report B</p>
              <p>{new Date(compare.audit_b.created_at).toLocaleString()}</p>
            </div>
          </div>

          <div className="flex flex-col gap-3">
            {compare.audit_a.results.map((resultA) => {
              const resultB = compare.audit_b.results.find((r) => r.tool === resultA.tool);
              const diff = compare.diff_by_tool[resultA.tool];
              return (
                <div key={resultA.tool} className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h2 className="font-medium text-neutral-100">{resultA.tool.replace(/_/g, " ")}</h2>
                    <div className="flex items-center gap-3">
                      <ScoreBadge score={resultA.score} size="sm" />
                      <span className="text-xs text-neutral-600">vs</span>
                      <ScoreBadge score={resultB?.score ?? null} size="sm" />
                    </div>
                  </div>
                  {diff && (diff.new_finding_codes.length > 0 || diff.resolved_finding_codes.length > 0) && (
                    <p className="text-xs text-neutral-500">
                      {diff.new_finding_codes.length > 0 && (
                        <span className="text-orange-400">{diff.new_finding_codes.length} only in A</span>
                      )}
                      {diff.new_finding_codes.length > 0 && diff.resolved_finding_codes.length > 0 && " · "}
                      {diff.resolved_finding_codes.length > 0 && (
                        <span className="text-blue-400">{diff.resolved_finding_codes.length} only in B</span>
                      )}
                    </p>
                  )}
                  {!resultB && <p className="text-xs text-neutral-600">Not present in report B.</p>}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
