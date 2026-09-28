import type { Metric } from "./types";

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v)}%`);

export const num = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat("en-US").format(v);

export const metricText = (m: Metric) => (m.available ? num(m.value) : "Unavailable");

export function dateText(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  const rel = days <= 0 ? "today" : days === 1 ? "yesterday" : `${days}d ago`;
  return `${d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })} · ${rel}`;
}

export const FLAG_LABELS: Record<string, string> = {
  followers_unavailable: "Followers unknown",
  likes_unavailable: "Likes unknown",
  replies_unavailable: "Replies unknown",
  posts_7d_unverified: "7d activity unverified",
  posts_30d_unverified: "30d activity unverified",
  posts_90d_unverified: "90d activity unverified",
};
