"use client";

import type { ReactNode } from "react";

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-8 flex animate-fade-up flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-zinc-400">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Checkbox({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`grid h-5 w-5 shrink-0 place-items-center rounded-md border transition duration-200 ${
        checked
          ? "scale-100 border-transparent bg-gradient-to-br from-brand-500 to-accent-500 shadow-[0_0_12px_-2px_rgb(168_85_247/0.8)]"
          : "border-white/20 bg-white/[0.03] hover:border-brand-400/60"
      }`}
    >
      <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="white" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
        <path d="M3.5 8.5l3 3 6-7" strokeDasharray="16" strokeDashoffset={checked ? 0 : 16} style={{ transition: "stroke-dashoffset 220ms ease" }} />
      </svg>
    </button>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return <span className={`${className} inline-block animate-spin rounded-full border-2 border-brand-400 border-t-transparent`} />;
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="card flex animate-fade-up flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-600/30 to-accent-500/20 text-brand-300">
        {icon ?? "✦"}
      </div>
      <div className="font-semibold">{title}</div>
      {children && <div className="mt-1 max-w-sm text-sm text-zinc-400">{children}</div>}
    </div>
  );
}

export function Avatar({ src, name, size = 40 }: { src?: string | null; name: string; size?: number }) {
  const style = { width: size, height: size };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt="" referrerPolicy="no-referrer" style={style} className="shrink-0 rounded-full object-cover ring-1 ring-white/10" />;
  }
  return (
    <div style={style} className="grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-600/40 to-accent-500/30 text-sm font-semibold text-brand-200 ring-1 ring-white/10">
      {name.slice(0, 1).toUpperCase()}
    </div>
  );
}
