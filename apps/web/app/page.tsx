import Link from "next/link";
import { Show } from "@clerk/nextjs";

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

export default function Home() {
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

        <div className="mt-10 flex gap-4">
          <Show when="signed-out">
            <Link
              href="/sign-up"
              className="rounded-full bg-neutral-50 px-6 py-3 text-sm font-medium text-neutral-950 hover:bg-neutral-200"
            >
              Get started free
            </Link>
            <Link
              href="/sign-in"
              className="rounded-full border border-neutral-700 px-6 py-3 text-sm font-medium text-neutral-100 hover:border-neutral-500"
            >
              Sign in
            </Link>
          </Show>
          <Show when="signed-in">
            <Link
              href="/dashboard"
              className="rounded-full bg-neutral-50 px-6 py-3 text-sm font-medium text-neutral-950 hover:bg-neutral-200"
            >
              Go to dashboard
            </Link>
          </Show>
        </div>

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
