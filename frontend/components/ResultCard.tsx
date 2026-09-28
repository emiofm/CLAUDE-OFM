"use client";

import type { Account, Result } from "@/lib/types";
import { dateText, FLAG_LABELS, metricText, num, pct } from "@/lib/format";
import AddToList from "./AddToList";
import { Avatar } from "./ui";

type Props = {
  result: Result;
  index: number;
  accounts: Account[];
  onSave: (id: number) => void;
  onIgnore: (id: number) => void;
  onReset: (id: number) => void;
};

function ScoreBar({ label, value, hint }: { label: string; value: number | null; hint?: string }) {
  return (
    <div title={hint}>
      <div className="flex items-baseline justify-between">
        <span className="text-[11px] font-medium text-zinc-500">{label}</span>
        <span className={`text-sm font-semibold tabular-nums ${value === null ? "text-zinc-600" : "text-zinc-100"}`}>
          {value === null ? "n/a" : pct(value)}
        </span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-accent-500 transition-[width] duration-1000 ease-out"
          style={{ width: `${value ?? 0}%` }}
        />
      </div>
    </div>
  );
}

function Stat({ label, value, available, note }: { label: string; value: string; available: boolean; note?: string | null }) {
  return (
    <div className="rounded-xl bg-white/[0.03] px-3 py-2 ring-1 ring-white/[0.04]" title={note ?? undefined}>
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
        <span className={`h-1.5 w-1.5 rounded-full ${available ? "bg-emerald-400" : "bg-zinc-600"}`} />
        {label}
      </div>
      <div className={`mt-0.5 text-sm font-semibold tabular-nums ${available ? "text-zinc-100" : "text-zinc-600"}`}>{value}</div>
      {note && <div className="mt-0.5 text-[10px] leading-tight text-zinc-500">{note}</div>}
    </div>
  );
}

const SIGNAL_STYLES: Record<string, string> = {
  high: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
  medium: "bg-amber-500/10 text-amber-300 ring-amber-500/25",
  low: "bg-white/[0.05] text-zinc-300 ring-white/10",
  none: "bg-white/[0.03] text-zinc-500 ring-white/10",
};

export default function ResultCard({ result: r, index, accounts, onSave, onIgnore, onReset }: Props) {
  const c = r.creator;
  const image = r.best_image_url || r.latest_post?.media_url;
  return (
    <article
      style={{ animationDelay: `${Math.min(index, 12) * 60}ms` }}
      className="card card-hover group flex animate-fade-up flex-col overflow-hidden"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-ink-800">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt="" referrerPolicy="no-referrer" className="h-full w-full object-cover transition duration-700 group-hover:scale-[1.04]" />
        ) : (
          <div className="grid h-full place-items-center text-sm text-zinc-600">No image</div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-ink-950/90 via-transparent to-transparent" />
        <div className="absolute left-3 top-3 rounded-full bg-black/60 px-2.5 py-1 text-xs font-semibold text-white ring-1 ring-white/15 backdrop-blur">
          <span className="text-gradient">Match {Math.round(r.total_score)}</span>
        </div>
        {c.status === "saved" && (
          <div className="absolute right-3 top-3 animate-scale-in rounded-full bg-emerald-500/90 px-2.5 py-1 text-xs font-semibold text-white shadow">Saved</div>
        )}
        <div className="absolute inset-x-3 bottom-3 flex items-center gap-3">
          <Avatar src={c.profile_picture_url} name={c.username} />
          <div className="min-w-0">
            <a href={c.profile_url} target="_blank" rel="noreferrer" className="block truncate font-semibold text-white hover:text-brand-200">
              @{c.username} {c.is_verified && <span className="text-sky-400" title="Verified">✓</span>}
            </a>
            <div className="truncate text-xs text-zinc-300/80">{c.display_name || "Display name unavailable"}</div>
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="grid grid-cols-2 gap-x-4 gap-y-3">
          <ScoreBar
            label="Visual similarity"
            value={r.visual_similarity}
            hint={`Best image ${pct(r.best_image_similarity)} · top-k avg ${pct(r.top_k_avg_similarity)} · ${r.images_analyzed} images`}
          />
          <ScoreBar label="Activity" value={r.activity_score} />
          <ScoreBar
            label="Engagement"
            value={r.engagement_score}
            hint={r.engagement_score === null ? "Not available from official Threads API" : `Source: ${r.score_breakdown?.engagement_source}`}
          />
          <ScoreBar label="Keyword relevance" value={r.keyword_relevance} />
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Stat label="Followers" value={metricText(c.followers)} available={c.followers.available}
            note={c.followers.available ? null : c.followers.note} />
          <Stat label="Posts 30d" value={metricText(c.posts_30d)} available={c.posts_30d.available} note={c.posts_30d.note} />
          <Stat label="Posts 7d" value={metricText(c.posts_7d)} available={c.posts_7d.available} />
          <Stat label="Likes (profile)" value={metricText(c.profile_likes)} available={c.profile_likes.available} />
          <Stat label="Replies (profile)" value={metricText(c.profile_replies)} available={c.profile_replies.available} />
          <Stat label="Last post" value={c.last_post_at ? dateText(c.last_post_at).split(" · ")[1] : "—"} available={!!c.last_post_at} />
        </div>

        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className={`rounded-full px-2 py-0.5 font-medium ring-1 ${SIGNAL_STYLES[c.creator_signal || "none"]}`}>
            Creator signal: {c.creator_signal ? c.creator_signal[0].toUpperCase() + c.creator_signal.slice(1) : "None"}
          </span>
          {c.monetization_label && (
            <span className="rounded-full bg-fuchsia-500/10 px-2 py-0.5 font-medium text-fuchsia-300 ring-1 ring-fuchsia-500/25"
              title={`Terms: ${c.signal_terms.join(", ")}`}>
              {c.monetization_label}
            </span>
          )}
          {r.matched_keywords.map((k) => <span key={k} className="chip">{k}</span>)}
        </div>

        {r.latest_post && (
          <div className="rounded-xl bg-white/[0.02] p-3 ring-1 ring-white/[0.05]">
            <div className="mb-1 flex justify-between text-[11px] text-zinc-500">
              <span>Latest relevant post</span>
              <span>{dateText(r.latest_post.timestamp)}</span>
            </div>
            <p className="line-clamp-3 text-sm text-zinc-300">{r.latest_post.text || <em className="text-zinc-600">No text</em>}</p>
            {r.latest_post.permalink && (
              <a href={r.latest_post.permalink} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-brand-300 hover:underline">
                View post →
              </a>
            )}
          </div>
        )}

        {r.filter_flags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {r.filter_flags.map((f) => (
              <span key={f} className="rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] text-amber-300">{FLAG_LABELS[f] || f}</span>
            ))}
          </div>
        )}

        <div className="mt-auto flex items-center gap-2 pt-1">
          <a href={c.profile_url} target="_blank" rel="noreferrer" className="btn-primary flex-1">Open Threads</a>
          <AddToList usernames={[c.username]} accounts={accounts} label="" className="btn-secondary !px-2.5" title="Add to an account's profile list" />
          <button
            className={`btn-secondary !px-2.5 ${c.status === "saved" ? "!border-emerald-500/40 !text-emerald-300" : ""}`}
            onClick={() => (c.status === "saved" ? onReset(c.id) : onSave(c.id))}
            title={c.status === "saved" ? "Unsave" : "Save creator"}
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              fill={c.status === "saved" ? "currentColor" : "none"}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
          </button>
          <button className="btn-ghost !px-2.5" onClick={() => onIgnore(c.id)} title="Ignore — hide this creator from results">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.1A9.8 9.8 0 0112 5c5 0 9 4.5 10 7-.4 1-1.2 2.3-2.4 3.5M6.6 6.6C4.4 8 2.8 10.2 2 12c1 2.5 5 7 10 7 1.6 0 3.1-.4 4.4-1.1" />
            </svg>
          </button>
        </div>
        <div className="text-[10px] text-zinc-600">
          Score {num(r.total_score)} · unavailable: {r.score_breakdown?.unavailable.join(", ") || "none"}
        </div>
      </div>
    </article>
  );
}
