"use client";

import { useState } from "react";

const SUGGESTIONS = ["brunette", "content creator", "onlyfans", "link in bio", "girl next door", "soft girl", "lifestyle creator"];

export default function KeywordInput({ value, onChange }: { value: string[]; onChange: (v: string[]) => void }) {
  const [draft, setDraft] = useState("");

  const addMany = (raw: string) => {
    const next = [...value];
    for (const part of raw.split(",")) {
      const k = part.trim();
      if (k && !next.some((x) => x.toLowerCase() === k.toLowerCase())) next.push(k);
    }
    onChange(next.slice(0, 25));
    setDraft("");
  };

  return (
    <div>
      <div className="input flex min-h-[44px] flex-wrap items-center gap-1.5 !py-1.5">
        {value.map((k) => (
          <span key={k} className="inline-flex animate-scale-in items-center gap-1 rounded-lg bg-brand-500/15 px-2 py-0.5 text-sm text-brand-200 ring-1 ring-brand-500/25">
            {k}
            <button type="button" className="text-brand-300/70 transition hover:text-white" onClick={() => onChange(value.filter((x) => x !== k))}>
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-[140px] flex-1 border-0 bg-transparent p-1 text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
          placeholder={value.length ? "Add keyword…" : "brunette, lifestyle creator, …"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if ((e.key === "Enter" || e.key === ",") && draft.trim()) {
              e.preventDefault();
              addMany(draft);
            } else if (e.key === "Backspace" && !draft && value.length) {
              onChange(value.slice(0, -1));
            }
          }}
          onBlur={() => draft.trim() && addMany(draft)}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.filter((s) => !value.includes(s)).map((s) => (
          <button key={s} type="button" onClick={() => addMany(s)}
            className="rounded-full border border-white/10 px-2.5 py-0.5 text-xs text-zinc-400 transition hover:border-brand-400/50 hover:bg-brand-500/10 hover:text-brand-200">
            + {s}
          </button>
        ))}
      </div>
    </div>
  );
}
