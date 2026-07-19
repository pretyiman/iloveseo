"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/dashboard", label: "Audit" },
  { href: "/dashboard/history", label: "History & Compare" },
];

export function DashboardNav() {
  const pathname = usePathname();

  return (
    <div className="mb-10 flex items-center justify-between">
      <nav className="flex gap-1 rounded-full border border-neutral-800 bg-neutral-900 p-1">
        {TABS.map((tab) => {
          const active = tab.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
                active ? "bg-neutral-50 text-neutral-950" : "text-neutral-400 hover:text-neutral-100"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
      <UserButton />
    </div>
  );
}
