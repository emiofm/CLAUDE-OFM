"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function SearchTabs() {
  const path = usePathname();
  const tabs = [
    { href: "/search", label: "Search" },
    { href: "/search/saved", label: "Saved & ignored" },
  ];
  return (
    <div className="flex gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] p-1">
      {tabs.map((t) => (
        <Link key={t.href} href={t.href}
          className={`rounded-lg px-3 py-1.5 text-sm transition ${path === t.href ? "bg-white/[0.08] text-white" : "text-zinc-400 hover:text-zinc-100"}`}>
          {t.label}
        </Link>
      ))}
    </div>
  );
}
