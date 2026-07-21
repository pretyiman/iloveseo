"use client";

import { useUser } from "@clerk/nextjs";
import Link from "next/link";
import { use, useEffect, useRef, useState } from "react";
import { DashboardNav } from "../../_components/DashboardNav";
import { ScoreBadge } from "../../_components/ScoreBadge";
import {
  API_URL,
  useApiClient,
  type Audit,
  type AiVisibilityProvider,
  type AuditShare,
  type Finding,
  type MonitoringFrequency,
} from "@/lib/api";

const SEVERITY_ORDER: Finding["severity"][] = ["critical", "high", "medium", "low", "info"];

const SEVERITY_STYLES: Record<Finding["severity"], string> = {
  critical: "bg-red-950 text-red-300 border-red-800",
  high: "bg-orange-950 text-orange-300 border-orange-800",
  medium: "bg-yellow-950 text-yellow-300 border-yellow-800",
  low: "bg-blue-950 text-blue-300 border-blue-800",
  info: "bg-neutral-800 text-neutral-400 border-neutral-700",
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
      <p className="mb-1.5 text-xs font-medium text-neutral-500">Technologies detected</p>
      <div className="flex flex-wrap gap-1.5">
        {detections.map((d) => (
          <span
            key={d.name}
            className="rounded-full border border-neutral-700 bg-neutral-800 px-2.5 py-0.5 text-xs text-neutral-300"
          >
            {d.name} <span className="text-neutral-500">({d.status})</span>
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
      <summary className="cursor-pointer text-neutral-500 hover:text-neutral-300">
        View all {Object.keys(headers).length} response headers
      </summary>
      <div className="mt-2 flex flex-col gap-1 rounded border border-neutral-800 bg-neutral-950 p-3 font-mono">
        {Object.entries(headers).map(([key, value]) => (
          <div key={key} className="break-all text-neutral-400">
            <span className="text-neutral-500">{key}:</span> {value}
          </div>
        ))}
      </div>
    </details>
  );
}

function AiVisibilityRow({ provider }: { provider: AiVisibilityProvider }) {
  let chip: { label: string; className: string };
  if (!provider.configured) {
    chip = { label: "Not integrated", className: "bg-neutral-800 text-neutral-500 border-neutral-700" };
  } else if (provider.status === null) {
    chip = { label: "Not checked yet", className: "bg-neutral-800 text-neutral-400 border-neutral-700" };
  } else if (provider.status === "error") {
    chip = { label: "Not functional", className: "bg-amber-950 text-amber-300 border-amber-800" };
  } else if (provider.cited) {
    chip = {
      label: `Cited${provider.position ? ` (#${provider.position})` : ""}`,
      className: "bg-green-950 text-green-300 border-green-800",
    };
  } else {
    chip = { label: "Not cited", className: "bg-neutral-800 text-neutral-400 border-neutral-700" };
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-neutral-800 px-3 py-2">
      <span className="text-sm text-neutral-300">{PROVIDER_LABELS[provider.provider]}</span>
      <div className="flex flex-col items-end gap-0.5">
        <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${chip.className}`}>
          {chip.label}
        </span>
        {provider.status === "error" && provider.error_message && (
          <span className="max-w-xs truncate text-right text-xs text-neutral-600" title={provider.error_message}>
            {provider.error_message}
          </span>
        )}
      </div>
    </div>
  );
}

function ShareAndExport({ auditId }: { auditId: string }) {
  const api = useApiClient();
  const [share, setShare] = useState<AuditShare | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ensureShared(): Promise<AuditShare> {
    if (share) return share;
    const result = await api.shareAudit(auditId);
    setShare(result);
    return result;
  }

  async function handleCopyLink() {
    setBusy(true);
    setError(null);
    try {
      const result = await ensureShared();
      await navigator.clipboard.writeText(result.share_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleDownloadPdf() {
    setBusy(true);
    setError(null);
    try {
      const result = await ensureShared();
      window.open(`${API_URL}/public/audits/${result.share_token}/pdf`, "_blank");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke() {
    if (!share) return;
    setBusy(true);
    setError(null);
    try {
      await api.revokeAuditShare(auditId);
      setShare(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-8 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <h2 className="mb-3 font-medium text-neutral-100">Share &amp; Export</h2>
      <p className="mb-3 text-xs text-neutral-500">
        Anyone with the link can view this report -- no account needed. Useful for sharing with a client or a
        site's owner.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={handleCopyLink}
          disabled={busy}
          className="rounded-full border border-neutral-700 px-3 py-1.5 text-xs text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
        >
          {copied ? "Copied!" : "Copy share link"}
        </button>
        <button
          onClick={handleDownloadPdf}
          disabled={busy}
          className="rounded-full border border-neutral-700 px-3 py-1.5 text-xs text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
        >
          Download PDF
        </button>
        {share && (
          <button
            onClick={handleRevoke}
            disabled={busy}
            className="rounded-full border border-neutral-800 px-3 py-1.5 text-xs text-neutral-500 hover:border-red-800 hover:text-red-400 disabled:opacity-50"
          >
            Revoke link
          </button>
        )}
      </div>
      {share && <p className="mt-2 truncate text-xs text-neutral-500">{share.share_url}</p>}
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </div>
  );
}

function MonitoringPanel({ projectId }: { projectId: string }) {
  const api = useApiClient();
  const { user } = useUser();
  const [loaded, setLoaded] = useState(false);
  const [enabled, setEnabled] = useState(false);
  const [frequency, setFrequency] = useState<MonitoringFrequency>("weekly");
  const [recipientEmail, setRecipientEmail] = useState("");
  const [message, setMessage] = useState("");
  const [lastSentAt, setLastSentAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getMonitoring(projectId)
      .then((m) => {
        setEnabled(m.monitoring_enabled);
        if (m.monitoring_frequency) setFrequency(m.monitoring_frequency);
        setRecipientEmail(m.monitoring_recipient_email ?? "");
        setMessage(m.monitoring_message ?? "");
        setLastSentAt(m.monitoring_last_sent_at);
        setLoaded(true);
      })
      .catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const googleAccount = user?.externalAccounts.find((a) => a.provider === "google");

  async function handleConnectGmail() {
    if (!googleAccount) return;
    setError(null);
    try {
      await googleAccount.reauthorize({
        additionalScopes: ["https://www.googleapis.com/auth/gmail.send"],
        redirectUrl: window.location.href,
      });
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleSave() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      if (enabled && !recipientEmail) {
        throw new Error("Enter the recipient's email address before enabling monitoring.");
      }
      await api.updateMonitoring(projectId, { enabled, frequency, recipientEmail, message });
      setStatus("Saved.");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleSendNow() {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      if (!recipientEmail) throw new Error("Enter the recipient's email address first.");
      await api.updateMonitoring(projectId, { enabled, frequency, recipientEmail, message });
      await api.sendMonitoringReportNow(projectId);
      setStatus("Report sent.");
      setLastSentAt(new Date().toISOString());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!loaded) return null;

  return (
    <div className="mb-8 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <h2 className="mb-3 font-medium text-neutral-100">Monitoring</h2>
      <p className="mb-3 text-xs text-neutral-500">
        Re-check this site on a schedule and email a comparison report -- sent from your own connected Gmail
        address, so it reads as a personal note to the site owner rather than an automated alert.
      </p>

      <button
        onClick={handleConnectGmail}
        disabled={!googleAccount}
        title={googleAccount ? undefined : "Sign in with Google to enable this"}
        className="mb-4 rounded-full border border-neutral-700 px-3 py-1.5 text-xs text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
      >
        Connect Gmail (grant send permission)
      </button>

      <div className="flex flex-col gap-3">
        <label className="flex items-center gap-2 text-sm text-neutral-300">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          Enable scheduled monitoring
        </label>

        <label className="flex flex-col gap-1 text-xs text-neutral-500">
          Frequency
          <select
            value={frequency}
            onChange={(e) => setFrequency(e.target.value as MonitoringFrequency)}
            className="rounded border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-sm text-neutral-200"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-neutral-500">
          Recipient email (the site owner or prospect)
          <input
            type="email"
            value={recipientEmail}
            onChange={(e) => setRecipientEmail(e.target.value)}
            placeholder="owner@example.com"
            className="rounded border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-sm text-neutral-200"
          />
        </label>

        <label className="flex flex-col gap-1 text-xs text-neutral-500">
          Personal message (optional)
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder="Hi -- I took a look at your site and put together a quick health check..."
            className="rounded border border-neutral-700 bg-neutral-950 px-2 py-1.5 text-sm text-neutral-200"
          />
        </label>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={handleSave}
            disabled={busy}
            className="rounded-full border border-neutral-700 px-3 py-1.5 text-xs text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={handleSendNow}
            disabled={busy}
            className="rounded-full border border-neutral-700 px-3 py-1.5 text-xs text-neutral-100 hover:border-neutral-500 disabled:opacity-50"
          >
            Send report now
          </button>
        </div>

        {lastSentAt && <p className="text-xs text-neutral-600">Last sent {new Date(lastSentAt).toLocaleString()}</p>}
        {status && <p className="text-xs text-green-400">{status}</p>}
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>
    </div>
  );
}

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
      <DashboardNav />
      <h1 className="mb-2 text-2xl font-semibold text-neutral-50">Audit results</h1>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!audit && !error && <p className="text-sm text-neutral-500">Loading...</p>}

      {audit && (
        <>
          <p className="mb-6 text-sm text-neutral-400">
            Status: <span className="font-medium text-neutral-200">{audit.status}</span>
            {audit.status === "running" && " -- results appear below as each tool finishes"}
          </p>

          <ShareAndExport auditId={audit.id} />
          <MonitoringPanel projectId={audit.project_id} />

          {audit.ai_visibility && (
            <div className="mb-8 rounded-lg border border-neutral-800 bg-neutral-900 p-4">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-medium text-neutral-100">AI Visibility</h2>
                <Link
                  href={`/dashboard/projects/${audit.project_id}/geo`}
                  className="text-xs text-neutral-500 hover:text-neutral-300"
                >
                  Manage tracked query
                </Link>
              </div>
              {audit.ai_visibility.query_text && (
                <p className="mb-3 text-xs text-neutral-500">&ldquo;{audit.ai_visibility.query_text}&rdquo;</p>
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
                    <div className="flex items-center gap-2">
                      {result.diff?.score_delta != null && result.diff.score_delta !== 0 && (
                        <span className={`text-xs ${result.diff.score_delta > 0 ? "text-green-400" : "text-red-400"}`}>
                          {result.diff.score_delta > 0 ? "+" : ""}
                          {result.diff.score_delta}
                        </span>
                      )}
                      <ScoreBadge score={result.score} size="sm" />
                    </div>
                  )}
                </div>
                {result.diff && (result.diff.new_finding_codes.length > 0 || result.diff.resolved_finding_codes.length > 0) && (
                  <p className="mb-2 text-xs text-neutral-500">
                    {result.diff.new_finding_codes.length > 0 && (
                      <span className="text-orange-400">{result.diff.new_finding_codes.length} new</span>
                    )}
                    {result.diff.new_finding_codes.length > 0 && result.diff.resolved_finding_codes.length > 0 && " · "}
                    {result.diff.resolved_finding_codes.length > 0 && (
                      <span className="text-green-400">{result.diff.resolved_finding_codes.length} resolved</span>
                    )}
                    {" since last audit"}
                  </p>
                )}
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
                {result.tool === "tech_checker" && <TechDetections raw={result.raw} />}
                {result.tool === "http_headers" && <AllHeadersDisclosure raw={result.raw} />}
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
