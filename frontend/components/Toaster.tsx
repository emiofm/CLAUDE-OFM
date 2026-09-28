"use client";

import { useSyncExternalStore } from "react";

type Toast = { id: number; text: string; kind: "ok" | "error" | "info" };
let toasts: Toast[] = [];
let seq = 0;
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function toast(text: string, kind: Toast["kind"] = "ok") {
  const id = ++seq;
  toasts = [...toasts, { id, text, kind }];
  emit();
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emit();
  }, 3800);
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};
const EMPTY: Toast[] = [];

export default function Toaster() {
  const items = useSyncExternalStore(subscribe, () => toasts, () => EMPTY);
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          className={`pointer-events-auto animate-slide-in rounded-xl border px-4 py-3 text-sm shadow-2xl backdrop-blur-xl ${
            t.kind === "error"
              ? "border-red-500/30 bg-red-950/80 text-red-200"
              : t.kind === "info"
                ? "border-white/10 bg-ink-800/90 text-zinc-200"
                : "border-emerald-500/25 bg-emerald-950/80 text-emerald-200"
          }`}
        >
          {t.text}
        </div>
      ))}
    </div>
  );
}
