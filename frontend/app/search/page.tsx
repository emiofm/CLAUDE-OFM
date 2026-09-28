"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import UploadDropzone from "@/components/UploadDropzone";
import KeywordInput from "@/components/KeywordInput";
import ResultCard from "@/components/ResultCard";
import SearchTabs from "@/components/SearchTabs";
import AddToList from "@/components/AddToList";
import { toast } from "@/components/Toaster";
import { Empty, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError, assetUrl, jsonInit } from "@/lib/api";
import type { Account, Job, ReferenceSet, Result, SettingsResponse } from "@/lib/types";

const MIN_REFS = 3;
const MAX_REFS = 20;
type Sort = "best" | "active" | "engagement" | "newest";
const SORTS: { id: Sort; label: string }[] = [
  { id: "best", label: "Best Match" },
  { id: "active", label: "Most Active" },
  { id: "engagement", label: "Highest Engagement" },
  { id: "newest", label: "Newest" },
];
const STAGES = [
  { id: "keyword_search", label: "Keyword search" },
  { id: "profiles", label: "Profiles" },
  { id: "analysing", label: "Image analysis & scoring" },
  { id: "done", label: "Done" },
];

type Filters = Record<
  "min_posts_7d" | "min_posts_30d" | "min_posts_90d" | "min_followers" | "max_followers" | "min_replies" | "min_likes",
  string
> & { strict_unknown_metrics: boolean };

const EMPTY_FILTERS: Filters = {
  min_posts_7d: "", min_posts_30d: "", min_posts_90d: "", min_followers: "",
  max_followers: "", min_replies: "", min_likes: "", strict_unknown_metrics: false,
};

function NumberField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <input className="input tabular-nums" inputMode="numeric" value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ""))} />
    </label>
  );
}

function Progress({ job }: { job: Job }) {
  const p = job.progress || {};
  const stageIdx = Math.max(0, STAGES.findIndex((s) => s.id === p.stage));
  const total = Number(p.creators_total || 0);
  const done = p.stage === "profiles" ? Number(p.profiles_done || 0) : Number(p.creators_done || 0);
  const pctDone = total ? Math.round((done / total) * 100) : 0;
  return (
    <div className="card animate-fade-up p-5">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {STAGES.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2">
            <span className={`grid h-6 w-6 place-items-center rounded-full text-[11px] font-semibold transition duration-500 ${
              i < stageIdx ? "bg-emerald-500/20 text-emerald-300" : i === stageIdx ? "bg-brand-500/25 text-brand-200 ring-2 ring-brand-500/40" : "bg-white/[0.05] text-zinc-500"
            }`}>
              {i < stageIdx ? "✓" : i + 1}
            </span>
            <span className={`text-xs ${i === stageIdx ? "text-zinc-100" : "text-zinc-500"}`}>{s.label}</span>
            {i < STAGES.length - 1 && <span className="mx-1 h-px w-6 bg-white/10" />}
          </div>
        ))}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-[linear-gradient(90deg,#7c3aed,#d946ef,#7c3aed)] bg-[length:200%_100%] animate-shimmer transition-[width] duration-700"
          style={{ width: `${p.stage === "keyword_search" ? 12 : Math.max(pctDone, 15)}%` }}
        />
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-zinc-400">
        <Spinner className="h-3.5 w-3.5" />
        {p.stage === "keyword_search" && "Searching Threads posts…"}
        {p.stage === "profiles" && `Fetching profiles ${done}/${total}`}
        {p.stage === "analysing" && `Analysing creators ${done}/${total}`}
        {!p.stage || p.stage === "queued" ? "Queued…" : null}
        {p.creators_found ? <span className="ml-auto">{p.creators_found} unique creators found</span> : null}
      </div>
    </div>
  );
}

function SearchPage() {
  const router = useRouter();
  const params = useSearchParams();
  const jobId = params.get("job");

  const [files, setFiles] = useState<File[]>([]);
  const [refSets, setRefSets] = useState<ReferenceSet[]>([]);
  const [refSetId, setRefSetId] = useState<number | null>(null);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [sort, setSort] = useState<Sort>("best");
  const sortRef = useRef<Sort>("best");
  sortRef.current = sort;

  useEffect(() => {
    api<SettingsResponse>("/api/settings")
      .then((s) => {
        setSettings(s);
        setKeywords((k) => (k.length ? k : s.config.search.default_keywords));
      })
      .catch((e) => setError(e.message));
    api<ReferenceSet[]>("/api/reference-sets").then(setRefSets).catch(() => undefined);
    api<Account[]>("/api/accounts").then(setAccounts).catch(() => undefined);
  }, []);

  const loadResults = useCallback(async (id: string, s: Sort) => {
    const body = await api<{ job: Job; results: Result[] }>(`/api/search/${id}/results?sort=${s}`);
    setJob(body.job);
    setResults(body.results);
  }, []);

  // Poll the job until it finishes.
  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const j = await api<Job>(`/api/search/${jobId}`);
        if (stop) return;
        setJob(j);
        if (j.status === "completed" || j.status === "failed") {
          await loadResults(jobId, sortRef.current);
          if (j.status === "completed") toast(`Search #${j.id} finished`, "ok");
          return;
        }
      } catch (e) {
        setError((e as Error).message);
        return;
      }
      timer = setTimeout(tick, 1200);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [jobId, loadResults]);

  useEffect(() => {
    if (jobId && job && (job.status === "completed" || job.status === "failed"))
      loadResults(jobId, sort).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sort]);

  const canSearch = keywords.length > 0 && (files.length === 0 || files.length >= MIN_REFS) && !submitting;

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      let rsId = refSetId;
      if (files.length >= MIN_REFS) {
        const form = new FormData();
        form.append("name", `Reference ${new Date().toLocaleString()}`);
        files.forEach((f) => form.append("files", f));
        const rs = await api<ReferenceSet>("/api/reference-sets", { method: "POST", body: form });
        rsId = rs.id;
        setRefSets((prev) => [rs, ...prev]);
        setRefSetId(rs.id);
        setFiles([]);
      }
      const toInt = (v: string) => (v === "" ? null : parseInt(v, 10));
      const { strict_unknown_metrics, ...nums } = filters;
      const payload = {
        reference_set_id: rsId,
        keywords,
        filters: {
          ...Object.fromEntries(Object.entries(nums).map(([k, v]) => [k, toInt(v)])),
          strict_unknown_metrics,
        },
      };
      const j = await api<Job>("/api/search", jsonInit("POST", payload));
      setJob(j);
      setResults([]);
      router.push(`/search?job=${j.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const setStatus = async (creatorId: number, action: "save" | "ignore" | "reset") => {
    try {
      await api(`/api/creators/${creatorId}/${action}`, { method: "POST" });
      if (action === "ignore") {
        setResults((rs) => rs.filter((r) => r.creator.id !== creatorId));
        toast("Creator ignored", "info");
      } else {
        setResults((rs) =>
          rs.map((r) => (r.creator.id === creatorId ? { ...r, creator: { ...r.creator, status: action === "save" ? "saved" : "new" } } : r)),
        );
        if (action === "save") toast("Creator saved");
      }
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  const followersKnown = useMemo(() => results.some((r) => r.creator.followers.available), [results]);
  const selectedSet = refSets.find((s) => s.id === refSetId);
  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <div className="space-y-8">
      <PageHeader
        title={<>Profile <span className="text-gradient">Search Engine</span></>}
        subtitle="Find active Threads creators whose visual aesthetic matches a reference set — using only the official Threads API."
        actions={<SearchTabs />}
      />

      {settings && !settings.threads.connected && (
        <div className="animate-fade-up rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
          Threads is not connected. <a href="/settings" className="font-semibold underline">Open Settings</a> to connect your account via OAuth.
        </div>
      )}

      <section className="card grid animate-fade-up gap-8 p-6 [animation-delay:80ms] lg:grid-cols-5">
        <div className="lg:col-span-3">
          <span className="label">Reference images</span>
          <UploadDropzone files={files} onChange={setFiles} min={MIN_REFS} max={MAX_REFS} />
          {refSets.length > 0 && (
            <div className="mt-4">
              <label className="label">…or reuse a saved reference set</label>
              <select className="input" value={refSetId ?? ""} disabled={files.length > 0}
                onChange={(e) => setRefSetId(e.target.value ? Number(e.target.value) : null)}>
                <option value="">None (no visual similarity)</option>
                {refSets.map((s) => (
                  <option key={s.id} value={s.id}>
                    #{s.id} {s.name} · {s.images.length} images · {s.embedding_model}
                  </option>
                ))}
              </select>
              {selectedSet && files.length === 0 && (
                <div className="mt-2 flex gap-1.5">
                  {selectedSet.images.slice(0, 10).map((im, i) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img key={im.id} src={assetUrl(im.url)} alt="" style={{ animationDelay: `${i * 40}ms` }}
                      className="h-10 w-10 animate-scale-in rounded-lg object-cover ring-1 ring-white/10" />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-5 lg:col-span-2">
          <div>
            <span className="label">Keywords</span>
            <KeywordInput value={keywords} onChange={setKeywords} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <NumberField label="Min posts 7d" value={filters.min_posts_7d} onChange={(v) => setFilters({ ...filters, min_posts_7d: v })} />
            <NumberField label="Min posts 30d" value={filters.min_posts_30d} placeholder="10" onChange={(v) => setFilters({ ...filters, min_posts_30d: v })} />
            <NumberField label="Min posts 90d" value={filters.min_posts_90d} onChange={(v) => setFilters({ ...filters, min_posts_90d: v })} />
            <NumberField label="Min followers" value={filters.min_followers} placeholder="20000" onChange={(v) => setFilters({ ...filters, min_followers: v })} />
            <NumberField label="Max followers" value={filters.max_followers} onChange={(v) => setFilters({ ...filters, max_followers: v })} />
            <NumberField label="Min replies" value={filters.min_replies} onChange={(v) => setFilters({ ...filters, min_replies: v })} />
            <NumberField label="Min likes" value={filters.min_likes} onChange={(v) => setFilters({ ...filters, min_likes: v })} />
          </div>
          <p className="text-[11px] leading-snug text-zinc-500">
            Followers, likes and replies come only from the official <code className="text-zinc-400">profile_lookup</code> endpoint
            (profile-level totals). When Threads doesn&apos;t provide them the filter can&apos;t be verified.
          </p>
          <label className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300">
            <input type="checkbox" className="accent-violet-500" checked={filters.strict_unknown_metrics}
              onChange={(e) => setFilters({ ...filters, strict_unknown_metrics: e.target.checked })} />
            Exclude creators whose filtered metrics are unavailable
          </label>
          <button className="btn-primary w-full py-3 text-[15px]" disabled={!canSearch} onClick={submit}>
            {submitting ? <><Spinner className="h-4 w-4 border-white border-t-transparent" /> Starting…</> : "Search"}
          </button>
          {files.length > 0 && files.length < MIN_REFS && (
            <p className="text-xs text-amber-300">Add at least {MIN_REFS} reference images (or remove them to search without visual similarity).</p>
          )}
        </div>
      </section>

      {error && <div className="animate-fade-up rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</div>}

      {job && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Search results</h2>
              <p className="text-xs text-zinc-500">
                Job #{job.id} · {job.keywords.join(", ")} · {job.status}
                {job.status === "completed" && ` · ${results.length} creators`}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {results.length > 0 && (
                <AddToList usernames={results.map((r) => r.creator.username)} accounts={accounts}
                  label={`Add all ${results.length} to list`} className="btn-ghost" align="right" />
              )}
              <div className="flex gap-1 rounded-xl border border-white/[0.07] bg-white/[0.02] p-1">
                {SORTS.map((s) => (
                  <button key={s.id} onClick={() => setSort(s.id)}
                    className={`rounded-lg px-3 py-1 text-sm transition ${sort === s.id ? "bg-gradient-to-r from-brand-600 to-accent-500 text-white shadow" : "text-zinc-400 hover:text-zinc-100"}`}>
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {running && <Progress job={job} />}
          {job.status === "failed" && (
            <div className="animate-fade-up rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              <strong>Search failed:</strong> {job.error}
            </div>
          )}
          {job.warnings && job.warnings.length > 0 && (
            <ul className="animate-fade-up space-y-1 rounded-xl border border-amber-500/20 bg-amber-500/[0.07] px-4 py-3 text-xs text-amber-200">
              {job.warnings.map((w) => <li key={w}>⚠ {w}</li>)}
            </ul>
          )}
          {job.status === "completed" && results.length > 0 && !followersKnown && (
            <p className="text-xs text-zinc-500">Follower count unavailable from official Threads API for these results.</p>
          )}
          {job.status === "completed" && results.length === 0 && (
            <Empty title="No creators matched">Try other keywords or relax the filters.</Empty>
          )}
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {results.map((r, i) => (
              <ResultCard key={r.id} result={r} index={i} accounts={accounts}
                onSave={(id) => setStatus(id, "save")}
                onIgnore={(id) => setStatus(id, "ignore")}
                onReset={(id) => setStatus(id, "reset")} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <SearchPage />
    </Suspense>
  );
}
