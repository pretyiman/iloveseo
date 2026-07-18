"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { useApiClient, type GeoCheck, type TrackedQuery } from "@/lib/api";

export default function ProjectGeoPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: projectId } = use(params);
  const api = useApiClient();
  const [queries, setQueries] = useState<TrackedQuery[]>([]);
  const [checksByQuery, setChecksByQuery] = useState<Record<string, GeoCheck[]>>({});
  const [queryText, setQueryText] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [runningFor, setRunningFor] = useState<string | null>(null);

  useEffect(() => {
    api
      .listTrackedQueries(projectId)
      .then(async (qs) => {
        setQueries(qs);
        const entries = await Promise.all(
          qs.map(async (q) => [q.id, await api.listGeoChecks(q.id)] as const)
        );
        setChecksByQuery(Object.fromEntries(entries));
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  async function handleAddQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!queryText.trim()) return;
    try {
      const competitorDomains = competitors
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean);
      const q = await api.createTrackedQuery(projectId, queryText.trim(), competitorDomains);
      setQueries((prev) => [q, ...prev]);
      setChecksByQuery((prev) => ({ ...prev, [q.id]: [] }));
      setQueryText("");
      setCompetitors("");
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleDelete(queryId: string) {
    try {
      await api.deleteTrackedQuery(queryId);
      setQueries((prev) => prev.filter((q) => q.id !== queryId));
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleRunCheck(queryId: string) {
    setRunningFor(queryId);
    try {
      const results = await api.runGeoCheck(queryId);
      setChecksByQuery((prev) => ({ ...prev, [queryId]: [...results, ...(prev[queryId] ?? [])] }));
    } catch (e) {
      setError(String(e));
    } finally {
      setRunningFor(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-12">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-neutral-50">AI Visibility (GEO)</h1>
        <Link href="/dashboard" className="text-sm text-neutral-400 hover:text-neutral-200">
          Back to projects
        </Link>
      </div>

      <p className="mb-6 text-sm text-neutral-400">
        Track whether this domain gets cited when AI engines answer questions your customers
        actually ask. Each check queries Perplexity and OpenAI and looks for your domain in the
        citation URLs or the answer text.
      </p>

      <form onSubmit={handleAddQuery} className="mb-8 flex flex-col gap-3">
        <input
          value={queryText}
          onChange={(e) => setQueryText(e.target.value)}
          placeholder="e.g. best SEO audit tool for developers"
          className="rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-2 text-neutral-100 placeholder:text-neutral-500"
        />
        <input
          value={competitors}
          onChange={(e) => setCompetitors(e.target.value)}
          placeholder="Competitor domains to compare against, comma-separated (optional)"
          className="rounded-lg border border-neutral-700 bg-neutral-900 px-4 py-2 text-sm text-neutral-100 placeholder:text-neutral-500"
        />
        <button
          type="submit"
          className="self-start rounded-lg bg-neutral-50 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-200"
        >
          Track this query
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
      {loading && <p className="text-sm text-neutral-500">Loading...</p>}

      <ul className="flex flex-col gap-4">
        {queries.map((q) => {
          const checks = checksByQuery[q.id] ?? [];
          const latestByProvider = new Map<string, GeoCheck>();
          for (const c of checks) {
            if (!latestByProvider.has(c.provider)) latestByProvider.set(c.provider, c);
          }

          return (
            <li key={q.id} className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
              <div className="mb-3 flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-neutral-100">{q.query_text}</p>
                  {q.competitor_domains.length > 0 && (
                    <p className="text-xs text-neutral-500">vs. {q.competitor_domains.join(", ")}</p>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    onClick={() => handleRunCheck(q.id)}
                    disabled={runningFor === q.id}
                    className="rounded-full border border-neutral-700 px-3 py-1 text-xs text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
                  >
                    {runningFor === q.id ? "Checking..." : "Check now"}
                  </button>
                  <button
                    onClick={() => handleDelete(q.id)}
                    className="rounded-full border border-neutral-800 px-3 py-1 text-xs text-neutral-500 hover:border-red-800 hover:text-red-400"
                  >
                    Remove
                  </button>
                </div>
              </div>

              {latestByProvider.size === 0 ? (
                <p className="text-xs text-neutral-500">No checks run yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {Array.from(latestByProvider.values()).map((c) => (
                    <div key={c.provider} className="flex items-center justify-between rounded border border-neutral-800 px-3 py-2 text-sm">
                      <span className="capitalize text-neutral-300">{c.provider}</span>
                      {c.status === "error" ? (
                        <span className="text-xs text-neutral-500">{c.error_message}</span>
                      ) : (
                        <span className={c.cited ? "text-green-400" : "text-neutral-500"}>
                          {c.cited ? `Cited${c.position ? ` (#${c.position})` : ""}` : "Not cited"}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </li>
          );
        })}
        {!loading && queries.length === 0 && (
          <p className="text-sm text-neutral-500">No tracked queries yet -- add one above.</p>
        )}
      </ul>
    </div>
  );
}
