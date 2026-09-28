"use client";

import { useCallback, useRef, useState } from "react";

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

  const add = useCallback(
    (incoming: FileList | File[]) => {
      const valid = Array.from(incoming).filter((f) => ACCEPT.includes(f.type));
      if (valid.length < Array.from(incoming).length) setError("Only JPG, PNG or WEBP images are accepted.");
      else setError(null);
      const merged = [...files, ...valid].slice(0, max);
      if (files.length + valid.length > max) setError(`Maximum ${max} images.`);
      onChange(merged);
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
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          drag ? "border-brand-500 bg-brand-50" : "border-slate-300 hover:border-brand-500 hover:bg-slate-50"
        }`}
      >
        <svg className="mb-2 h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 16.5V18a2.25 2.25 0 002.25 2.25h13.5A2.25 2.25 0 0021 18v-1.5M16.5 7.5L12 3m0 0L7.5 7.5M12 3v13.5" />
        </svg>
        <p className="text-sm font-medium text-slate-700">Drag & drop reference photos, or click to browse</p>
        <p className="mt-1 text-xs text-slate-500">
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
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {files.length > 0 && (
        <div className="mt-3 grid grid-cols-5 gap-2 sm:grid-cols-8 lg:grid-cols-10">
          {files.map((f, i) => (
            <div key={`${f.name}-${i}`} className="group relative aspect-square overflow-hidden rounded-lg bg-slate-100">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={URL.createObjectURL(f)} alt="" className="h-full w-full object-cover" />
              <button
                type="button"
                onClick={() => onChange(files.filter((_, j) => j !== i))}
                className="absolute right-1 top-1 hidden h-5 w-5 place-items-center rounded-full bg-black/60 text-xs text-white group-hover:grid"
                aria-label="Remove image"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
      <p className={`mt-2 text-xs ${files.length >= min ? "text-emerald-600" : "text-slate-500"}`}>
        {files.length} / {max} selected{files.length < min ? ` · at least ${min} required` : ""}
      </p>
    </div>
  );
}
