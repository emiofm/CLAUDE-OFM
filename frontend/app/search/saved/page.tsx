"use client";

import { useEffect, useState } from "react";
import SearchTabs from "@/components/SearchTabs";
import AddToList from "@/components/AddToList";
import { toast } from "@/components/Toaster";
import { Avatar, Empty, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { dateText, metricText } from "@/lib/format";
import type { Account, Creator, Post } from "@/lib/types";

type Row = { creator: Creator; latest_post: Post | null };

export default function SavedPage() {
  const [tab, setTab] = useState<"saved" | "ignored">("saved");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);

  useEffect(() => {
    api<Account[]>("/api/accounts").then(setAccounts).catch(() => undefined);
  }, []);

  useEffect(() => {
    setRows(null);
    api<Row[]>(`/api/creators?status=${tab}`).then(setRows).catch((e) => toast(e.message, "error"));
  }, [tab]);

  const reset = async (id: number) => {
    await api(`/api/creators/${id}/reset`, { method: "POST" });
    setRows((r) => (r || []).filter((x) => x.creator.id !== id));
    toast(tab === "saved" ? "Removed from saved" : "Restored", "info");
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={<>Profile <span className="text-gradient">Search Engine</span></>}
        subtitle="Creators you saved or ignored from search results."
        actions={<SearchTabs />}
      />
      <div className="flex items-center justify-between">
        <div className="flex gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] p-1">
          {(["saved", "ignored"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-lg px-3 py-1 text-sm capitalize transition ${tab === t ? "bg-white/[0.08] text-white" : "text-zinc-400 hover:text-zinc-100"}`}>
              {t}
            </button>
          ))}
        </div>
        {rows && rows.length > 0 && tab === "saved" && (
          <AddToList usernames={rows.map((r) => r.creator.username)} accounts={accounts} label={`Add all ${rows.length} to list`} className="btn-ghost" />
        )}
      </div>
      {rows === null ? (
        <div className="flex items-center gap-2 text-sm text-zinc-500"><Spinner /> Loading…</div>
      ) : rows.length === 0 ? (
        <Empty title="Nothing here yet">Save creators from search results to see them here.</Empty>
      ) : (
        <div className="card divide-y divide-white/[0.05] overflow-hidden">
          {rows.map(({ creator: c, latest_post: p }, i) => (
            <div key={c.id} style={{ animationDelay: `${Math.min(i, 15) * 40}ms` }}
              className="flex animate-fade-up flex-wrap items-center gap-4 p-4 transition hover:bg-white/[0.02]">
              <Avatar src={c.profile_picture_url} name={c.username} size={48} />
              <div className="min-w-[200px] flex-1">
                <div className="font-semibold">@{c.username}</div>
                <div className="text-xs text-zinc-500">{c.display_name || "—"}</div>
                {p?.text && <p className="mt-1 line-clamp-1 text-sm text-zinc-400">{p.text}</p>}
              </div>
              <div className="grid grid-cols-3 gap-6 text-sm">
                <div><div className="label">Followers</div><span className={c.followers.available ? "" : "text-zinc-600"}>{metricText(c.followers)}</span></div>
                <div><div className="label">Posts 30d</div>{metricText(c.posts_30d)}</div>
                <div><div className="label">Last post</div>{dateText(c.last_post_at).split(" · ")[0]}</div>
              </div>
              <div className="flex gap-2">
                <a href={c.profile_url} target="_blank" rel="noreferrer" className="btn-primary">Open Threads</a>
                <AddToList usernames={[c.username]} accounts={accounts} label="List" />
                <button className="btn-secondary" onClick={() => reset(c.id)}>{tab === "saved" ? "Remove" : "Restore"}</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
