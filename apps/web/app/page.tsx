"use client";

import { Show } from "@clerk/nextjs";
import { Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ScoreBadge } from "./dashboard/_components/ScoreBadge";
import { scanPublicDomain, type ScanResult } from "@/lib/api";

const TOOLS = [
  "Meta Tag Extractor",
  "HTTP Header Test",
  "AI Crawler / llms.txt Checker",
  "Redirect Chain Checker",
  "Sitemap Finder",
  "Website Speed Test",
  "Website Technology Checker",
  "Mobile Support Test",
  "Page Crawl (Site-Wide Audit)",
  "SSL/TLS + DNS Health Checker",
  "hreflang / International SEO Checker",
  "Structured Data / Rich Results Validator",
  "Accessibility Audit",
];

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

export default function Home() {
  const [domain, setDomain] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleScan(e: React.FormEvent) {
    e.preventDefault();
    const normalized = normalizeDomain(domain);
    if (!normalized) return;

    setScanning(true);
    setError(null);
    setScanResult(null);
    try {
      const result = await scanPublicDomain(normalized);
      setScanResult(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-neutral-950">
      <main className="flex w-full max-w-3xl flex-1 flex-col items-center px-6 py-24 text-center">
        <h1 className="text-4xl font-semibold tracking-tight text-neutral-50 sm:text-5xl">
          One audit. Every SEO issue on your site.
        </h1>
        <p className="mt-6 max-w-xl text-lg text-neutral-400">
          SEO Repair Kit runs meta tags, headers, redirects, sitemaps, speed,
          tech stack, and AI-crawler access checks concurrently and merges
          them into one prioritized fix list -- built for developers who ship,
          not marketers who guess.
        </p>

        <Show when="signed-out">
          <form onSubmit={handleScan} className="mx-auto mt-10 flex w-full max-w-md gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
              <input
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                placeholder="Scan any site free -- example.com"
                className="w-full rounded-full border border-neutral-700 bg-neutral-900 py-2.5 pl-10 pr-4 text-neutral-100 placeholder:text-neutral-500 focus:border-neutral-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={scanning}
              className="shrink-0 rounded-full bg-neutral-50 px-6 py-2.5 text-sm font-medium text-neutral-950 hover:bg-neutral-200 disabled:opacity-50"
            >
              {scanning ? "Scanning..." : "Scan free"}
            </button>
          </form>
          {scanning && <p className="mt-3 text-xs text-neutral-500">This can take up to 20 seconds...</p>}
          {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
          <p className="mt-4 text-xs text-neutral-500">
            No account needed. Already have one?{" "}
            <Link href="/sign-in" className="text-neutral-300 hover:text-neutral-100">
              Sign in
            </Link>
          </p>
        </Show>
        <Show when="signed-in">
          <div className="mt-10 flex gap-4">
            <Link
              href="/dashboard"
              className="rounded-full bg-neutral-50 px-6 py-3 text-sm font-medium text-neutral-950 hover:bg-neutral-200"
            >
              Go to dashboard
            </Link>
          </div>
        </Show>

        {scanResult && (
          <div className="mt-12 w-full text-left">
            <div className="mb-6 rounded-lg border border-neutral-800 bg-neutral-900 p-4 text-center">
              <p className="font-medium text-neutral-100">
                Sign up free for the full report, history, comparisons, and AI Visibility
              </p>
              <Link
                href="/sign-up"
                className="mt-3 inline-block rounded-full bg-neutral-50 px-5 py-2 text-sm font-medium text-neutral-950 hover:bg-neutral-200"
              >
                Sign up free
              </Link>
            </div>

            <div className="flex flex-col gap-3">
              {scanResult.results.map((result) => (
                <div key={result.tool} className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h2 className="font-medium text-neutral-100">{result.tool.replace(/_/g, " ")}</h2>
                    <ScoreBadge score={result.score} size="sm" />
                  </div>
                  {result.findings.length === 0 ? (
                    <p className="text-sm text-neutral-500">No issues found.</p>
                  ) : (
                    <div className="relative">
                      <ul className="pointer-events-none flex select-none flex-col gap-2 blur-sm">
                        {result.findings.map((f, i) => (
                          <li key={i} className="rounded border border-neutral-700 bg-neutral-800 px-3 py-1.5 text-sm text-neutral-300">
                            {f.message}
                          </li>
                        ))}
                      </ul>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Link
                          href="/sign-up"
                          className="rounded-full bg-neutral-50 px-4 py-1.5 text-xs font-medium text-neutral-950 hover:bg-neutral-200"
                        >
                          Sign up free to see {result.findings.length} issue{result.findings.length === 1 ? "" : "s"}
                        </Link>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <ul className="mt-16 grid w-full grid-cols-1 gap-3 text-left sm:grid-cols-2">
          {TOOLS.map((tool) => (
            <li
              key={tool}
              className="rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3 text-sm text-neutral-300"
            >
              {tool}
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
