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
      <div className="input flex min-h-[42px] flex-wrap items-center gap-1.5 !py-1.5">
        {value.map((k) => (
          <span key={k} className="inline-flex items-center gap-1 rounded-md bg-brand-50 px-2 py-0.5 text-sm text-brand-700">
            {k}
            <button type="button" className="text-brand-500 hover:text-brand-700" onClick={() => onChange(value.filter((x) => x !== k))}>
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-[140px] flex-1 border-0 bg-transparent p-1 text-sm outline-none"
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
            className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-brand-500 hover:text-brand-700">
            + {s}
          </button>
        ))}
      </div>
    </div>
  );
}
