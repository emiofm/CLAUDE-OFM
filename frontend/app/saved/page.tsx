"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { dateText, metricText } from "@/lib/format";
import type { Creator, Post } from "@/lib/types";

type Row = { creator: Creator; latest_post: Post | null };

export default function SavedPage() {
  const [tab, setTab] = useState<"saved" | "ignored">("saved");
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRows(null);
    api<Row[]>(`/api/creators?status=${tab}`).then(setRows).catch((e) => setError(e.message));
  }, [tab]);

  const reset = async (id: number) => {
    await api(`/api/creators/${id}/reset`, { method: "POST" });
    setRows((r) => (r || []).filter((x) => x.creator.id !== id));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Saved creators</h1>
          <p className="mt-1 text-sm text-slate-500">Creators you saved or ignored from search results.</p>
        </div>
        <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
          {(["saved", "ignored"] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`rounded-md px-3 py-1 text-sm capitalize ${tab === t ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
              {t}
            </button>
          ))}
        </div>
      </div>
      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {rows === null ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="card p-8 text-center text-sm text-slate-500">Nothing here yet.</div>
      ) : (
        <div className="card divide-y divide-slate-100">
          {rows.map(({ creator: c, latest_post: p }) => (
            <div key={c.id} className="flex flex-wrap items-center gap-4 p-4">
              {c.profile_picture_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c.profile_picture_url} alt="" referrerPolicy="no-referrer" className="h-12 w-12 rounded-full object-cover" />
              ) : (
                <div className="grid h-12 w-12 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700">
                  {c.username[0].toUpperCase()}
                </div>
              )}
              <div className="min-w-[200px] flex-1">
                <div className="font-semibold">@{c.username}</div>
                <div className="text-xs text-slate-500">{c.display_name || "—"}</div>
                {p?.text && <p className="mt-1 line-clamp-1 text-sm text-slate-600">{p.text}</p>}
              </div>
              <div className="grid grid-cols-3 gap-6 text-sm">
                <div><div className="label">Followers</div>{metricText(c.followers)}</div>
                <div><div className="label">Posts 30d</div>{metricText(c.posts_30d)}</div>
                <div><div className="label">Last post</div>{dateText(c.last_post_at).split(" · ")[0]}</div>
              </div>
              <div className="flex gap-2">
                <a href={c.profile_url} target="_blank" rel="noreferrer" className="btn-primary">Open Threads</a>
                <button className="btn-secondary" onClick={() => reset(c.id)}>{tab === "saved" ? "Remove" : "Restore"}</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
