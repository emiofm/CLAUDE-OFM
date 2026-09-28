"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type Props = {
  files: File[];
  onChange: (files: File[]) => void;
  min: number;
  max: number;
};

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];

export default function UploadDropzone({ files, onChange, min, max }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // One object URL per file, revoked when the selection changes (no leaks).
  const previews = useMemo(() => files.map((f) => URL.createObjectURL(f)), [files]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const add = useCallback(
    (incoming: FileList | File[]) => {
      const all = Array.from(incoming);
      const valid = all.filter((f) => ACCEPT.includes(f.type));
      let msg: string | null = null;
      if (valid.length < all.length) msg = "Only JPG, PNG or WEBP images are accepted.";
      if (files.length + valid.length > max) msg = `Maximum ${max} images.`;
      setError(msg);
      onChange([...files, ...valid].slice(0, max));
    },
    [files, max, onChange],
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          add(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border border-dashed px-6 py-9 text-center transition duration-300 ${
          drag
            ? "scale-[1.01] border-brand-400 bg-brand-500/10"
            : "border-white/15 bg-white/[0.02] hover:border-brand-400/60 hover:bg-white/[0.04]"
        }`}
      >
        <div className={`mb-3 grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-brand-600/40 to-accent-500/30 text-brand-200 transition duration-300 ${drag ? "-translate-y-1 scale-110" : "group-hover:-translate-y-0.5"}`}>
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5V18a2.25 2.25 0 002.25 2.25h13.5A2.25 2.25 0 0021 18v-1.5M16.5 7.5L12 3m0 0L7.5 7.5M12 3v13.5" />
          </svg>
        </div>
        <p className="text-sm font-medium text-zinc-200">Drop reference photos, or click to browse</p>
        <p className="mt-1 text-xs text-zinc-500">
          {min}–{max} images · compares overall visual style, not identity (no face recognition)
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT.join(",")}
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files) add(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {error && <p className="mt-2 animate-fade-in text-xs text-red-400">{error}</p>}
      {files.length > 0 && (
        <div className="mt-3 grid grid-cols-5 gap-2 sm:grid-cols-8 lg:grid-cols-10">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${f.size}-${i}`}
              style={{ animationDelay: `${i * 30}ms` }}
              className="group relative aspect-square animate-scale-in overflow-hidden rounded-xl ring-1 ring-white/10"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previews[i]} alt="" className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
              <button
                type="button"
                onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-black/70 text-xs text-white opacity-0 transition group-hover:opacity-100"
                aria-label="Remove image"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="mt-3 flex items-center gap-3">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className={`h-full rounded-full transition-all duration-500 ${files.length >= min ? "bg-gradient-to-r from-emerald-500 to-emerald-400" : "bg-gradient-to-r from-brand-600 to-accent-500"}`}
            style={{ width: `${(files.length / max) * 100}%` }}
          />
        </div>
        <span className={`text-xs tabular-nums ${files.length >= min ? "text-emerald-400" : "text-zinc-500"}`}>
          {files.length}/{max}
          {files.length > 0 && files.length < min ? ` · need ${min - files.length} more` : ""}
        </span>
      </div>
    </div>
  );
}
