"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  {
    href: "/search",
    label: "Profile Search Engine",
    icon: "M21 21l-4.35-4.35M11 18a7 7 0 100-14 7 7 0 000 14z",
  },
  {
    href: "/models",
    label: "Models/Accs",
    icon: "M17 20h5v-2a3 3 0 00-5.36-1.86M17 20H7m10 0v-2c0-.66-.13-1.28-.36-1.86M7 20H2v-2a3 3 0 015.36-1.86M7 20v-2c0-.66.13-1.28.36-1.86m0 0a5 5 0 019.28 0M15 7a3 3 0 11-6 0 3 3 0 016 0z",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: "M10.3 4.3c.4-1.7 2.9-1.7 3.4 0a1.7 1.7 0 002.6 1.1c1.5-.9 3.3.8 2.4 2.4a1.7 1.7 0 001 2.5c1.8.5 1.8 3 0 3.5a1.7 1.7 0 00-1 2.5c.9 1.6-.9 3.3-2.4 2.4a1.7 1.7 0 00-2.6 1.1c-.5 1.7-3 1.7-3.4 0a1.7 1.7 0 00-2.6-1.1c-1.5.9-3.3-.8-2.4-2.4a1.7 1.7 0 00-1-2.5c-1.8-.5-1.8-3 0-3.5a1.7 1.7 0 001-2.5c-.9-1.6.9-3.3 2.4-2.4a1.7 1.7 0 002.6-1.1zM15 12a3 3 0 11-6 0 3 3 0 016 0z",
  },
];

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-9 w-9 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-brand-600 via-accent-500 to-brand-500 bg-[length:200%_200%] animate-gradient shadow-[0_8px_24px_-6px_rgb(168_85_247/0.6)]">
        <span className="text-lg font-black leading-none text-white">@</span>
      </div>
      <div className="leading-tight">
        <div className="text-[15px] font-bold tracking-tight">Threads <span className="text-gradient">Purge</span></div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">control panel</div>
      </div>
    </div>
  );
}

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sticky top-0 z-30 border-b border-white/[0.06] bg-ink-950/80 backdrop-blur-xl md:h-screen md:w-64 md:shrink-0 md:border-b-0 md:border-r">
      <div className="flex items-center justify-between gap-4 px-4 py-3 md:flex-col md:items-stretch md:px-4 md:py-6">
        <Link href="/search" className="md:px-2"><Logo /></Link>
        <nav className="flex gap-1 overflow-x-auto md:mt-8 md:flex-col">
          {NAV.map((item, i) => {
            const active = path.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{ animationDelay: `${80 + i * 60}ms` }}
                className={`group relative flex animate-fade-up items-center gap-3 whitespace-nowrap rounded-xl px-3 py-2 text-sm font-medium transition ${
                  active ? "bg-white/[0.07] text-white" : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100"
                }`}
              >
                {active && (
                  <span className="absolute inset-y-2 left-0 hidden w-0.5 rounded-full bg-gradient-to-b from-brand-400 to-accent-500 md:block" />
                )}
                <svg className={`h-4 w-4 shrink-0 transition ${active ? "text-brand-400" : "text-zinc-500 group-hover:text-zinc-300"}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                </svg>
                <span className="hidden sm:inline">{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto hidden px-2 text-[11px] text-zinc-600 md:block">v0.2 · official Threads API</div>
      </div>
    </aside>
  );
}
