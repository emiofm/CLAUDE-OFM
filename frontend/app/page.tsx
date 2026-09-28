"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import UploadDropzone from "@/components/UploadDropzone";
import KeywordInput from "@/components/KeywordInput";
import ResultCard from "@/components/ResultCard";
import { api, ApiError, assetUrl, jsonInit, API_URL } from "@/lib/api";
import type { Job, ReferenceSet, Result, SettingsResponse } from "@/lib/types";

const MIN_REFS = 3;
const MAX_REFS = 20;
type Sort = "best" | "active" | "engagement" | "newest";
const SORTS: { id: Sort; label: string }[] = [
  { id: "best", label: "Best Match" },
  { id: "active", label: "Most Active" },
  { id: "engagement", label: "Highest Engagement" },
  { id: "newest", label: "Newest" },
];

type Filters = {
  min_posts_7d: string;
  min_posts_30d: string;
  min_posts_90d: string;
  min_followers: string;
  max_followers: string;
  min_replies: string;
  min_likes: string;
  strict_unknown_metrics: boolean;
};

const EMPTY_FILTERS: Filters = {
  min_posts_7d: "",
  min_posts_30d: "",
  min_posts_90d: "",
  min_followers: "",
  max_followers: "",
  min_replies: "",
  min_likes: "",
  strict_unknown_metrics: false,
};

function NumberField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <input className="input" inputMode="numeric" value={value} placeholder={placeholder}
        onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ""))} />
    </label>
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
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<Result[]>([]);
  const [sort, setSort] = useState<Sort>("best");

  useEffect(() => {
    api<SettingsResponse>("/api/settings")
      .then((s) => {
        setSettings(s);
        setKeywords((k) => (k.length ? k : s.config.search.default_keywords));
      })
      .catch((e) => setError(e.message));
    api<ReferenceSet[]>("/api/reference-sets").then(setRefSets).catch(() => undefined);
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
          await loadResults(jobId, sort);
          return;
        }
      } catch (e) {
        setError((e as Error).message);
        return;
      }
      timer = setTimeout(tick, 1500);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    if (jobId && job && (job.status === "completed" || job.status === "failed")) loadResults(jobId, sort).catch(() => undefined);
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
      const payload = {
        reference_set_id: rsId,
        keywords,
        filters: {
          min_posts_7d: toInt(filters.min_posts_7d),
          min_posts_30d: toInt(filters.min_posts_30d),
          min_posts_90d: toInt(filters.min_posts_90d),
          min_followers: toInt(filters.min_followers),
          max_followers: toInt(filters.max_followers),
          min_replies: toInt(filters.min_replies),
          min_likes: toInt(filters.min_likes),
          strict_unknown_metrics: filters.strict_unknown_metrics,
        },
      };
      const j = await api<Job>("/api/search", jsonInit("POST", payload));
      setJob(j);
      setResults([]);
      router.push(`/?job=${j.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const setStatus = async (creatorId: number, action: "save" | "ignore" | "reset") => {
    try {
      await api(`/api/creators/${creatorId}/${action}`, { method: "POST" });
      if (action === "ignore") setResults((rs) => rs.filter((r) => r.creator.id !== creatorId));
      else
        setResults((rs) =>
          rs.map((r) => (r.creator.id === creatorId ? { ...r, creator: { ...r.creator, status: action === "save" ? "saved" : "new" } } : r)),
        );
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const followersKnown = useMemo(() => results.some((r) => r.creator.followers.available), [results]);
  const selectedSet = refSets.find((s) => s.id === refSetId);
  const running = job && (job.status === "pending" || job.status === "running");
  const p = job?.progress || {};

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Creator Finder</h1>
        <p className="mt-1 text-sm text-slate-500">
          Find active Threads creators whose visual aesthetic matches a reference set — using only the official Threads API.
        </p>
      </div>

      {settings && !settings.threads.connected && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Threads is not connected. <a href="/settings" className="font-semibold underline">Open Settings</a> to connect your account via OAuth.
        </div>
      )}

      <section className="card grid gap-6 p-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <span className="label">Reference images</span>
          <UploadDropzone files={files} onChange={setFiles} min={MIN_REFS} max={MAX_REFS} />
          {refSets.length > 0 && (
            <div className="mt-3">
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
                  {selectedSet.images.slice(0, 10).map((im) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img key={im.id} src={assetUrl(im.url)} alt="" className="h-10 w-10 rounded object-cover" />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-4 lg:col-span-2">
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
          <p className="text-[11px] leading-snug text-slate-500">
            Followers, likes and replies come only from the official <code>profile_lookup</code> endpoint (profile-level totals).
            When Threads doesn&apos;t provide them the filter can&apos;t be verified.
          </p>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={filters.strict_unknown_metrics}
              onChange={(e) => setFilters({ ...filters, strict_unknown_metrics: e.target.checked })} />
            Exclude creators whose filtered metrics are unavailable
          </label>
          <button className="btn-primary w-full py-2.5" disabled={!canSearch} onClick={submit}>
            {submitting ? "Starting…" : "Search"}
          </button>
          {files.length > 0 && files.length < MIN_REFS && (
            <p className="text-xs text-amber-700">Add at least {MIN_REFS} reference images (or remove them to search without visual similarity).</p>
          )}
        </div>
      </section>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {job && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Search results</h2>
              <p className="text-xs text-slate-500">
                Job #{job.id} · {job.keywords.join(", ")} · {job.status}
                {running && ` · ${p.stage ?? ""} ${p.creators_done ?? 0}/${p.creators_total ?? "?"}`}
              </p>
            </div>
            <div className="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
              {SORTS.map((s) => (
                <button key={s.id} onClick={() => setSort(s.id)}
                  className={`rounded-md px-3 py-1 text-sm ${sort === s.id ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {running && (
            <div className="card flex items-center gap-3 p-4 text-sm text-slate-600">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
              Searching Threads and analysing images… (found {p.creators_found ?? 0} creators)
            </div>
          )}
          {job.status === "failed" && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              <strong>Search failed:</strong> {job.error}
            </div>
          )}
          {job.warnings && job.warnings.length > 0 && (
            <ul className="space-y-1 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
              {job.warnings.map((w) => <li key={w}>⚠ {w}</li>)}
            </ul>
          )}
          {job.status === "completed" && results.length > 0 && !followersKnown && (
            <p className="text-xs text-slate-500">Follower count unavailable from official Threads API for these results.</p>
          )}
          {job.status === "completed" && results.length === 0 && (
            <div className="card p-8 text-center text-sm text-slate-500">No creators matched. Try other keywords or relax the filters.</div>
          )}
          <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
            {results.map((r) => (
              <ResultCard key={r.id} result={r}
                onSave={(id) => setStatus(id, "save")}
                onIgnore={(id) => setStatus(id, "ignore")}
                onReset={(id) => setStatus(id, "reset")} />
            ))}
          </div>
        </section>
      )}
      <p className="text-center text-[11px] text-slate-400">API: {API_URL}</p>
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
