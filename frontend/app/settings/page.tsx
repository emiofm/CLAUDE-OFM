"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, API_URL, jsonInit } from "@/lib/api";
import type { AppConfig, SettingsResponse } from "@/lib/types";
import { PageHeader } from "@/components/ui";

const WEIGHT_LABELS: Record<keyof AppConfig["weights"], string> = {
  visual_similarity: "Visual similarity",
  activity: "Activity",
  engagement: "Engagement",
  creator_signal: "Creator signal",
  keyword_relevance: "Keyword relevance",
  audience: "Audience (only if follower count is available)",
};

function Field({ label, value, onChange, step = 1 }: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <input type="number" step={step} className="input" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function SettingsInner() {
  const params = useSearchParams();
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [testQ, setTestQ] = useState("coffee");
  const [testOut, setTestOut] = useState<string | null>(null);

  const load = () =>
    api<SettingsResponse>("/api/settings")
      .then((d) => {
        setData(d);
        setCfg(d.config);
      })
      .catch((e) => setMsg({ ok: false, text: e.message }));

  useEffect(() => {
    load();
    const t = params.get("threads");
    if (t === "connected") setMsg({ ok: true, text: "Threads connected successfully." });
    if (t === "error") setMsg({ ok: false, text: `Threads connection failed: ${params.get("reason") || "unknown error"}` });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!data || !cfg) return <p className="text-sm text-zinc-400">{msg?.text || "Loading…"}</p>;
  const t = data.threads;

  const save = async () => {
    try {
      const r = await api<{ config: AppConfig }>("/api/settings", jsonInit("PUT", cfg));
      setCfg(r.config);
      setMsg({ ok: true, text: "Settings saved." });
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };
  const resetDefaults = async () => {
    const r = await api<{ config: AppConfig }>("/api/settings/reset", { method: "POST" });
    setCfg(r.config);
    setMsg({ ok: true, text: "Defaults restored." });
  };
  const testConnection = async () => {
    const r = await api<{ ok: boolean; username?: string; message?: string }>("/api/settings/test-connection", { method: "POST" });
    setMsg(r.ok ? { ok: true, text: `Connection OK — authenticated as @${r.username}` } : { ok: false, text: r.message || "Failed" });
  };
  const testSearch = async () => {
    setTestOut("Running…");
    const r = await api<{ ok: boolean; count?: number; sample?: { username: string; text: string }[]; message?: string }>(
      "/api/settings/test-keyword-search", jsonInit("POST", { q: testQ }));
    setTestOut(r.ok ? `${r.count} posts on first page:\n` + (r.sample || []).map((s) => `@${s.username}: ${(s.text || "").slice(0, 80)}`).join("\n") : `Error: ${r.message}`);
    load();
  };
  const refresh = async () => {
    try {
      await api("/auth/threads/refresh", { method: "POST" });
      setMsg({ ok: true, text: "Token refreshed." });
      load();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    }
  };
  const disconnect = async () => {
    await api("/auth/threads/disconnect", { method: "POST" });
    load();
  };

  const totalWeight = Object.values(cfg.weights).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Threads API connection, search engine configuration and data availability." />
      {msg && (
        <div className={`rounded-xl border px-4 py-3 text-sm ${msg.ok ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-200" : "border-red-500/30 bg-red-500/10 text-red-300"}`}>
          {msg.text}
        </div>
      )}

      <section className="card animate-fade-up space-y-4 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Threads connection</h2>
            <p className="text-sm text-zinc-400">
              Status:{" "}
              <span className={`inline-flex items-center gap-1.5 ${t.connected ? "font-semibold text-emerald-400" : "font-semibold text-zinc-400"}`}>
                <span className={`h-2 w-2 rounded-full ${t.connected ? "animate-pulse-ring bg-emerald-400" : "bg-zinc-600"}`} />
                {t.connected ? "Connected" : "Not connected"}
              </span>
              {t.username && <> as @{t.username}</>}
              {t.token_source === "env" && " (token from THREADS_ACCESS_TOKEN)"}
            </p>
            {t.expires_at && <p className="text-xs text-zinc-400">Token expires {new Date(t.expires_at).toLocaleString()}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <a href={`${API_URL}/auth/threads`} className={`btn-primary ${t.app_configured ? "" : "pointer-events-none opacity-50"}`}>
              {t.connected ? "Reconnect Threads" : "Connect Threads"}
            </a>
            <button className="btn-secondary" onClick={testConnection} disabled={!t.connected}>Test API connection</button>
            {t.token_source === "oauth" && <button className="btn-secondary" onClick={refresh}>Refresh token</button>}
            {t.token_source === "oauth" && <button className="btn-ghost" onClick={disconnect}>Disconnect</button>}
          </div>
        </div>
        {!t.app_configured && (
          <p className="rounded-lg bg-amber-500/10 p-3 text-sm text-amber-200">
            THREADS_APP_ID and THREADS_APP_SECRET are not set on the server. Add them to <code>.env</code> and restart the backend.
          </p>
        )}
        <div className="grid gap-4 text-sm md:grid-cols-3">
          <div>
            <div className="label">Granted scopes</div>
            {t.granted_scopes ? (
              <div className="flex flex-wrap gap-1">
                {t.granted_scopes.map((s) => <span key={s} className="rounded bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300 ring-1 ring-emerald-500/20">{s}</span>)}
              </div>
            ) : <span className="text-zinc-500">Unknown (connect via OAuth)</span>}
            {t.missing_scopes.length > 0 && (
              <p className="mt-2 text-xs text-amber-300">Missing: {t.missing_scopes.join(", ")}</p>
            )}
          </div>
          <div>
            <div className="label">Local request budget (24h)</div>
            <p>keyword_search: {t.keyword_search_budget_remaining} left</p>
            <p>profile discovery: {t.profile_budget_remaining} left</p>
          </div>
          <div>
            <div className="label">OAuth redirect URI</div>
            <code className="break-all text-xs">{t.redirect_uri}</code>
            <div className="label mt-2">Embedding model</div>
            <code className="text-xs">{data.embedding_model}</code>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-white/[0.05] pt-4">
          <span className="text-sm text-zinc-300">Test keyword search (1 request):</span>
          <input className="input !w-48" value={testQ} onChange={(e) => setTestQ(e.target.value)} />
          <button className="btn-secondary" onClick={testSearch} disabled={!t.connected}>Run</button>
        </div>
        {testOut && <pre className="whitespace-pre-wrap rounded-lg bg-black/40 p-3 font-mono text-xs text-zinc-200 ring-1 ring-white/10 animate-fade-in">{testOut}</pre>}
      </section>

      <section className="card animate-fade-up space-y-5 p-6 [animation-delay:80ms]">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Search configuration</h2>
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={resetDefaults}>Restore defaults</button>
            <button className="btn-primary" onClick={save}>Save settings</button>
          </div>
        </div>
        <label className="block">
          <span className="label">Default keywords (comma separated)</span>
          <input className="input" value={cfg.search.default_keywords.join(", ")}
            onChange={(e) => setCfg({ ...cfg, search: { ...cfg.search, default_keywords: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) } })} />
        </label>

        <div>
          <div className="label">Score weights (normalised; total {totalWeight})</div>
          <div className="grid gap-3 sm:grid-cols-3">
            {(Object.keys(WEIGHT_LABELS) as (keyof AppConfig["weights"])[]).map((k) => (
              <Field key={k} label={WEIGHT_LABELS[k]} value={cfg.weights[k]}
                onChange={(v) => setCfg({ ...cfg, weights: { ...cfg.weights, [k]: v } })} />
            ))}
          </div>
          <p className="mt-2 text-xs text-zinc-400">Components that are unavailable for a creator are excluded and the remaining weights are re-normalised — never counted as zero.</p>
        </div>

        <div>
          <div className="label">Visual similarity</div>
          <div className="grid gap-3 sm:grid-cols-5">
            <Field label="Best image weight" step={0.05} value={cfg.similarity.best_weight} onChange={(v) => setCfg({ ...cfg, similarity: { ...cfg.similarity, best_weight: v } })} />
            <Field label="Top-k avg weight" step={0.05} value={cfg.similarity.top_k_weight} onChange={(v) => setCfg({ ...cfg, similarity: { ...cfg.similarity, top_k_weight: v } })} />
            <Field label="Top k" value={cfg.similarity.top_k} onChange={(v) => setCfg({ ...cfg, similarity: { ...cfg.similarity, top_k: v } })} />
            <Field label="Cosine floor (0%)" step={0.01} value={cfg.similarity.cosine_floor} onChange={(v) => setCfg({ ...cfg, similarity: { ...cfg.similarity, cosine_floor: v } })} />
            <Field label="Cosine ceiling (100%)" step={0.01} value={cfg.similarity.cosine_ceiling} onChange={(v) => setCfg({ ...cfg, similarity: { ...cfg.similarity, cosine_ceiling: v } })} />
          </div>
        </div>

        <div>
          <div className="label">Activity score</div>
          <div className="grid gap-3 sm:grid-cols-4">
            {Object.entries(cfg.activity).map(([k, v]) => (
              <Field key={k} label={k.replace(/_/g, " ")} step={k.includes("per_day") || k.includes("half") ? 0.5 : 1} value={v}
                onChange={(nv) => setCfg({ ...cfg, activity: { ...cfg.activity, [k]: nv } })} />
            ))}
          </div>
        </div>

        <div>
          <div className="label">Search limits</div>
          <div className="grid gap-3 sm:grid-cols-4">
            <label className="block">
              <span className="label">Search type</span>
              <select className="input" value={cfg.search.search_type} onChange={(e) => setCfg({ ...cfg, search: { ...cfg.search, search_type: e.target.value as "TOP" | "RECENT" } })}>
                <option>TOP</option><option>RECENT</option>
              </select>
            </label>
            <label className="block">
              <span className="label">Media type</span>
              <select className="input" value={cfg.search.media_type ?? ""} onChange={(e) => setCfg({ ...cfg, search: { ...cfg.search, media_type: (e.target.value || null) as AppConfig["search"]["media_type"] } })}>
                <option value="">All</option><option>IMAGE</option><option>VIDEO</option><option>TEXT</option>
              </select>
            </label>
            <Field label="Max results" value={cfg.search.max_results} onChange={(v) => setCfg({ ...cfg, search: { ...cfg.search, max_results: v } })} />
            <Field label="Page size (≤100)" value={cfg.search.page_size} onChange={(v) => setCfg({ ...cfg, search: { ...cfg.search, page_size: v } })} />
            <Field label="Max pages / keyword" value={cfg.search.max_pages_per_keyword} onChange={(v) => setCfg({ ...cfg, search: { ...cfg.search, max_pages_per_keyword: v } })} />
            <Field label="Max posts / keyword" value={cfg.search.max_posts_per_keyword} onChange={(v) => setCfg({ ...cfg, search: { ...cfg.search, max_posts_per_keyword: v } })} />
            <Field label="Max images / creator" value={cfg.search.max_images_per_creator} onChange={(v) => setCfg({ ...cfg, search: { ...cfg.search, max_images_per_creator: v } })} />
          </div>
          <div className="mt-3 flex flex-wrap gap-6 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={cfg.search.lookup_profiles} onChange={(e) => setCfg({ ...cfg, search: { ...cfg.search, lookup_profiles: e.target.checked } })} /> Look up profiles (profile_lookup)</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={cfg.search.fetch_profile_posts} onChange={(e) => setCfg({ ...cfg, search: { ...cfg.search, fetch_profile_posts: e.target.checked } })} /> Fetch recent posts (profile_posts)</label>
          </div>
        </div>

        <div>
          <div className="label">Cache TTL (hours)</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Profile lookups" value={cfg.cache.profile_ttl_hours} onChange={(v) => setCfg({ ...cfg, cache: { ...cfg.cache, profile_ttl_hours: v } })} />
            <Field label="Posts" value={cfg.cache.posts_ttl_hours} onChange={(v) => setCfg({ ...cfg, cache: { ...cfg.cache, posts_ttl_hours: v } })} />
            <Field label="Image embeddings" value={cfg.cache.embedding_ttl_hours} onChange={(v) => setCfg({ ...cfg, cache: { ...cfg.cache, embedding_ttl_hours: v } })} />
          </div>
        </div>
      </section>

      <section className="grid animate-fade-up gap-6 [animation-delay:160ms] md:grid-cols-2">
        <div className="card p-6">
          <h2 className="mb-3 font-semibold text-emerald-300">Available from official Threads API</h2>
          <ul className="space-y-3 text-sm">
            {data.data_availability.available.map((a) => (
              <li key={a.metric}>
                <div className="font-medium">{a.metric}</div>
                <div className="text-xs text-zinc-400">{a.endpoint} · {a.permission}</div>
                <div className="text-xs text-zinc-400">{a.notes}</div>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-6">
          <h2 className="mb-3 font-semibold text-zinc-200">Not available from official Threads API</h2>
          <ul className="space-y-3 text-sm">
            {data.data_availability.unavailable.map((a) => (
              <li key={a.metric}>
                <div className="font-medium">{a.metric}</div>
                <div className="text-xs text-zinc-400">{a.notes}</div>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsInner />
    </Suspense>
  );
}
