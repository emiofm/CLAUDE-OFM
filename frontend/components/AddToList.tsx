"use client";

import { useEffect, useRef, useState } from "react";
import { api, jsonInit } from "@/lib/api";
import type { Account, AddProfilesResponse } from "@/lib/types";
import { toast } from "./Toaster";

/** Popover to add one or more usernames to an account's profile list (Models/Accs). */
export default function AddToList({
  usernames,
  accounts,
  label = "Add to list",
  className = "btn-secondary",
  align = "right",
  title,
}: {
  usernames: string[];
  accounts: Account[];
  label?: string;
  className?: string;
  align?: "left" | "right";
  title?: string;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const add = async (acc: Account) => {
    setBusy(acc.id);
    try {
      const r = await api<AddProfilesResponse>(
        `/api/accounts/${acc.id}/profiles`,
        jsonInit("POST", { usernames, source: "search" }),
      );
      const parts = [];
      if (r.added.length) parts.push(`${r.added.length} added`);
      if (r.duplicates.length) parts.push(`${r.duplicates.length} already in list`);
      toast(`@${acc.username}: ${parts.join(", ") || "nothing to add"}`, r.added.length ? "ok" : "info");
      setOpen(false);
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(null);
    }
  };

  const groups = accounts.reduce<Record<string, Account[]>>((acc, a) => {
    (acc[a.talent_name || "—"] ||= []).push(a);
    return acc;
  }, {});

  return (
    <div className="relative" ref={ref}>
      <button type="button" className={className} title={title} aria-label={title || label} onClick={() => setOpen((o) => !o)} disabled={!usernames.length}>
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
        </svg>
        {label}
      </button>
      {open && (
        <div className={`absolute bottom-full z-40 mb-2 w-64 origin-bottom animate-scale-in rounded-xl border border-white/10 bg-ink-800/95 p-1.5 shadow-2xl backdrop-blur-xl ${align === "right" ? "right-0" : "left-0"}`}>
          {accounts.length === 0 ? (
            <div className="p-3 text-xs text-zinc-400">
              No accounts yet. Create a model and its accounts in <a href="/models" className="text-brand-300 underline">Models/Accs</a>.
            </div>
          ) : (
            <div className="max-h-72 overflow-y-auto">
              {Object.entries(groups).map(([model, accs]) => (
                <div key={model} className="py-1">
                  <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">{model}</div>
                  {accs.map((a) => (
                    <button key={a.id} onClick={() => add(a)} disabled={busy !== null}
                      className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm text-zinc-200 transition hover:bg-white/[0.07]">
                      <span className="truncate">@{a.username}</span>
                      <span className="text-[11px] text-zinc-500">{busy === a.id ? "…" : `${a.profiles_total} in list`}</span>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
