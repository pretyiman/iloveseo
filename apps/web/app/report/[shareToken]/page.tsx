"use client";

import { use, useEffect, useState } from "react";
import { API_URL, type Audit, type AiVisibilityProvider, type Finding } from "@/lib/api";

const SEVERITY_ORDER: Finding["severity"][] = ["critical", "high", "medium", "low", "info"];

const SEVERITY_STYLES: Record<Finding["severity"], string> = {
  critical: "bg-red-50 text-red-700 border-red-200",
  high: "bg-orange-50 text-orange-700 border-orange-200",
  medium: "bg-yellow-50 text-yellow-700 border-yellow-200",
  low: "bg-blue-50 text-blue-700 border-blue-200",
  info: "bg-gray-100 text-gray-600 border-gray-200",
};

const PROVIDER_LABELS: Record<AiVisibilityProvider["provider"], string> = {
  perplexity: "Perplexity",
  openai: "OpenAI",
};

type TechDetection = { name: string; category: string; confidence: number; status: "confirmed" | "possible" };

function TechDetections({ raw }: { raw: Record<string, unknown> }) {
  const detections = raw.detections as TechDetection[] | undefined;
  if (!detections || detections.length === 0) return null;

  return (
    <div className="mt-2">
      <p className="mb-1.5 text-xs font-medium text-gray-500">Technologies detected</p>
      <div className="flex flex-wrap gap-1.5">
        {detections.map((d) => (
          <span key={d.name} className="rounded-full border border-gray-200 bg-gray-100 px-2.5 py-0.5 text-xs text-gray-700">
            {d.name} <span className="text-gray-500">({d.status})</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function AllHeadersDisclosure({ raw }: { raw: Record<string, unknown> }) {
  const headers = raw.headers as Record<string, string> | undefined;
  if (!headers || Object.keys(headers).length === 0) return null;

  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
        View all {Object.keys(headers).length} response headers
      </summary>
      <div className="mt-2 flex flex-col gap-1 rounded border border-gray-200 bg-gray-50 p-3 font-mono">
        {Object.entries(headers).map(([key, value]) => (
          <div key={key} className="break-all text-gray-600">
            <span className="text-gray-500">{key}:</span> {value}
          </div>
        ))}
      </div>
    </details>
  );
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-gray-400";
  if (score >= 90) return "text-green-600";
  if (score >= 70) return "text-lime-600";
  if (score >= 50) return "text-orange-600";
  return "text-red-600";
}

function AiVisibilityRow({ provider }: { provider: AiVisibilityProvider }) {
  let chip: { label: string; className: string };
  if (!provider.configured) {
    chip = { label: "Not integrated", className: "bg-gray-100 text-gray-500 border-gray-200" };
  } else if (provider.status === null) {
    chip = { label: "Not checked yet", className: "bg-gray-100 text-gray-500 border-gray-200" };
  } else if (provider.status === "error") {
    chip = { label: "Not functional", className: "bg-amber-50 text-amber-700 border-amber-200" };
  } else if (provider.cited) {
    chip = {
      label: `Cited${provider.position ? ` (#${provider.position})` : ""}`,
      className: "bg-green-50 text-green-700 border-green-200",
    };
  } else {
    chip = { label: "Not cited", className: "bg-gray-100 text-gray-500 border-gray-200" };
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-gray-200 px-3 py-2">
      <span className="text-sm text-gray-700">{PROVIDER_LABELS[provider.provider]}</span>
      <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${chip.className}`}>{chip.label}</span>
    </div>
  );
}

export default function SharedReportPage({ params }: { params: Promise<{ shareToken: string }> }) {
  const { shareToken } = use(params);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/public/audits/${shareToken}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(res.status === 404 ? "This report link is invalid or has been revoked." : `${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(setAudit)
      .catch((e) => setError(String(e.message ?? e)));
  }, [shareToken]);

  const allFindings = audit?.results.flatMap((r) => r.findings.map((f) => ({ ...f, tool: r.tool }))) ?? [];
  const counts = SEVERITY_ORDER.reduce<Record<string, number>>((acc, sev) => {
    acc[sev] = allFindings.filter((f) => f.severity === sev).length;
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto w-full max-w-3xl px-6 py-12">
        <div className="mb-8 flex items-center justify-between border-b border-gray-200 pb-4">
          <span className="text-sm font-semibold tracking-tight text-gray-900">SEO Repair Kit</span>
          <div className="print:hidden flex items-center gap-3">
            <span className="text-xs text-gray-400">Shared report -- view only</span>
            {audit && (
              <a
                href={`${API_URL}/public/audits/${shareToken}/pdf`}
                className="rounded-full border border-gray-300 px-3 py-1 text-xs text-gray-700 hover:border-gray-500"
              >
                Download PDF
              </a>
            )}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {!audit && !error && <p className="text-sm text-gray-500">Loading...</p>}

        {audit && (
          <>
            <h1 className="mb-1 text-2xl font-semibold text-gray-900">Audit report</h1>
            <p className="mb-6 text-sm text-gray-500">
              Generated {new Date(audit.created_at).toLocaleDateString()} -- status: {audit.status}
            </p>

            {audit.ai_visibility && (
              <div className="mb-8 rounded-lg border border-gray-200 p-4">
                <h2 className="mb-3 font-medium text-gray-900">AI Visibility</h2>
                {audit.ai_visibility.query_text && (
                  <p className="mb-3 text-xs text-gray-500">&ldquo;{audit.ai_visibility.query_text}&rdquo;</p>
                )}
                <div className="flex flex-col gap-2">
                  {audit.ai_visibility.providers.map((p) => (
                    <AiVisibilityRow key={p.provider} provider={p} />
                  ))}
                </div>
              </div>
            )}

            <div className="mb-8 flex gap-3">
              {SEVERITY_ORDER.map((sev) => (
                <div key={sev} className={`flex-1 rounded-lg border px-3 py-2 text-center ${SEVERITY_STYLES[sev]}`}>
                  <div className="text-lg font-semibold">{counts[sev]}</div>
                  <div className="text-xs capitalize">{sev}</div>
                </div>
              ))}
            </div>

            <div className="flex flex-col gap-4">
              {audit.results.map((result) => (
                <div key={result.tool} className="rounded-lg border border-gray-200 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h2 className="font-medium text-gray-900">{result.tool.replace(/_/g, " ")}</h2>
                    <span className={`text-sm font-semibold ${scoreColor(result.score)}`}>
                      {result.score === null ? "--" : `${result.score}/100`}
                    </span>
                  </div>
                  {result.findings.length === 0 ? (
                    <p className="text-sm text-gray-500">No issues found.</p>
                  ) : (
                    <ul className="flex flex-col gap-2">
                      {result.findings.map((f, i) => (
                        <li key={i} className={`rounded border px-3 py-1.5 text-sm ${SEVERITY_STYLES[f.severity]}`}>
                          {f.message}
                        </li>
                      ))}
                    </ul>
                  )}
                  {result.tool === "tech_checker" && <TechDetections raw={result.raw} />}
                  {result.tool === "http_headers" && <AllHeadersDisclosure raw={result.raw} />}
                </div>
              ))}
            </div>

            <p className="mt-10 text-center text-xs text-gray-400">
              Generated by SEO Repair Kit -- an all-in-one SEO and site-health audit tool.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
