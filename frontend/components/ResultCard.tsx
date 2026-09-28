"use client";

import type { Result } from "@/lib/types";
import { dateText, FLAG_LABELS, metricText, num, pct } from "@/lib/format";

type Props = {
  result: Result;
  onSave: (id: number) => void;
  onIgnore: (id: number) => void;
  onReset: (id: number) => void;
};

function ScoreBar({ label, value, hint }: { label: string; value: number | null; hint?: string }) {
  return (
    <div title={hint}>
      <div className="flex items-baseline justify-between">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        <span className={`text-sm font-semibold ${value === null ? "text-slate-400" : "text-slate-900"}`}>
          {value === null ? "n/a" : pct(value)}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${value ?? 0}%` }} />
      </div>
    </div>
  );
}

function Stat({ label, value, available, note }: { label: string; value: string; available: boolean; note?: string | null }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2" title={note ?? undefined}>
      <div className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        <span className={`h-1.5 w-1.5 rounded-full ${available ? "bg-emerald-500" : "bg-slate-300"}`} />
        {label}
      </div>
      <div className={`mt-0.5 text-sm font-semibold ${available ? "text-slate-900" : "text-slate-400"}`}>{value}</div>
      {note && <div className="mt-0.5 text-[10px] leading-tight text-slate-400">{note}</div>}
    </div>
  );
}

const SIGNAL_STYLES: Record<string, string> = {
  high: "bg-emerald-50 text-emerald-700",
  medium: "bg-amber-50 text-amber-700",
  low: "bg-slate-100 text-slate-600",
  none: "bg-slate-100 text-slate-400",
};

export default function ResultCard({ result: r, onSave, onIgnore, onReset }: Props) {
  const c = r.creator;
  const image = r.best_image_url || r.latest_post?.media_url;
  return (
    <article className="card flex flex-col overflow-hidden">
      <div className="relative aspect-[4/3] bg-slate-100">
        {image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={image} alt="" referrerPolicy="no-referrer" className="h-full w-full object-cover" />
        ) : (
          <div className="grid h-full place-items-center text-sm text-slate-400">No image</div>
        )}
        <div className="absolute left-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-brand-700 shadow">
          Match {Math.round(r.total_score)}
        </div>
        {c.status === "saved" && (
          <div className="absolute right-3 top-3 rounded-full bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white shadow">Saved</div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-4 p-4">
        <div className="flex items-center gap-3">
          {c.profile_picture_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={c.profile_picture_url} alt="" referrerPolicy="no-referrer" className="h-10 w-10 rounded-full object-cover" />
          ) : (
            <div className="grid h-10 w-10 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
              {c.username.slice(0, 1).toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <a href={c.profile_url} target="_blank" rel="noreferrer" className="block truncate font-semibold hover:text-brand-700">
              @{c.username} {c.is_verified && <span className="text-sky-500" title="Verified">✓</span>}
            </a>
            <div className="truncate text-xs text-slate-500">{c.display_name || "Display name unavailable"}</div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
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
          <Stat
            label="Followers"
            value={metricText(c.followers)}
            available={c.followers.available}
            note={c.followers.available ? null : c.followers.note}
          />
          <Stat label="Posts 30d" value={metricText(c.posts_30d)} available={c.posts_30d.available} note={c.posts_30d.note} />
          <Stat label="Posts 7d" value={metricText(c.posts_7d)} available={c.posts_7d.available} />
          <Stat label="Likes (profile)" value={metricText(c.profile_likes)} available={c.profile_likes.available} />
          <Stat label="Replies (profile)" value={metricText(c.profile_replies)} available={c.profile_replies.available} />
          <Stat label="Last post" value={c.last_post_at ? dateText(c.last_post_at).split(" · ")[1] : "—"} available={!!c.last_post_at} />
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded-full px-2 py-0.5 font-medium ${SIGNAL_STYLES[c.creator_signal || "none"]}`}>
            Creator signal: {c.creator_signal ? c.creator_signal[0].toUpperCase() + c.creator_signal.slice(1) : "None"}
          </span>
          {c.monetization_label && (
            <span className="rounded-full bg-rose-50 px-2 py-0.5 font-medium text-rose-700" title={`Terms: ${c.signal_terms.join(", ")}`}>
              {c.monetization_label}
            </span>
          )}
        </div>

        {r.matched_keywords.length > 0 && (
          <div>
            <div className="label">Matched</div>
            <div className="flex flex-wrap gap-1">
              {r.matched_keywords.map((k) => (
                <span key={k} className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700">{k}</span>
              ))}
            </div>
          </div>
        )}

        {r.latest_post && (
          <div className="rounded-lg border border-slate-100 p-3">
            <div className="mb-1 flex justify-between text-[11px] text-slate-500">
              <span>Latest relevant post</span>
              <span>{dateText(r.latest_post.timestamp)}</span>
            </div>
            <p className="line-clamp-3 text-sm text-slate-700">{r.latest_post.text || <em className="text-slate-400">No text</em>}</p>
            {r.latest_post.permalink && (
              <a href={r.latest_post.permalink} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-brand-600 hover:underline">
                View post →
              </a>
            )}
          </div>
        )}

        {r.filter_flags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {r.filter_flags.map((f) => (
              <span key={f} className="rounded bg-amber-50 px-1.5 py-0.5 text-[11px] text-amber-700">{FLAG_LABELS[f] || f}</span>
            ))}
          </div>
        )}

        <div className="mt-auto flex gap-2 pt-1">
          <a href={c.profile_url} target="_blank" rel="noreferrer" className="btn-primary flex-1">Open Threads</a>
          {c.status === "saved" ? (
            <button className="btn-secondary" onClick={() => onReset(c.id)}>Unsave</button>
          ) : (
            <button className="btn-secondary" onClick={() => onSave(c.id)}>Save</button>
          )}
          <button className="btn-ghost" onClick={() => onIgnore(c.id)} title="Hide this creator from results">Ignore</button>
        </div>
        <div className="text-[10px] text-slate-400">Score {num(r.total_score)} · unavailable: {r.score_breakdown?.unavailable.join(", ") || "none"}</div>
      </div>
    </article>
  );
}
