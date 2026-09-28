"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "@/components/Toaster";
import { Avatar, Checkbox, Empty, PageHeader, Spinner } from "@/components/ui";
import { api, jsonInit } from "@/lib/api";
import { num } from "@/lib/format";
import type { Account, AddProfilesResponse, Talent, TargetProfile } from "@/lib/types";

const COLORS = ["#8b5cf6", "#d946ef", "#ec4899", "#f43f5e", "#f59e0b", "#10b981", "#06b6d4", "#3b82f6"];

function Ring({ value, total, color }: { value: number; total: number; color: string }) {
  const r = 9;
  const c = 2 * Math.PI * r;
  const frac = total ? value / total : 0;
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6 -rotate-90">
      <circle cx="12" cy="12" r={r} fill="none" stroke="rgb(255 255 255 / 0.08)" strokeWidth="3" />
      <circle cx="12" cy="12" r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={c * (1 - frac)} style={{ transition: "stroke-dashoffset 500ms ease" }} />
    </svg>
  );
}

function ProfileRow({ p, index, onToggle, onRemove }: {
  p: TargetProfile; index: number; onToggle: (v: boolean) => void; onRemove: () => void;
}) {
  const c = p.creator;
  return (
    <div style={{ animationDelay: `${Math.min(index, 20) * 25}ms` }}
      className={`group flex animate-fade-up items-center gap-3 rounded-xl px-3 py-2 transition ${p.selected ? "bg-brand-500/[0.08] ring-1 ring-brand-500/20" : "hover:bg-white/[0.03]"}`}>
      <Checkbox checked={p.selected} onChange={onToggle} label={`Select @${p.username}`} />
      <Avatar src={c?.profile_picture_url} name={p.username} size={30} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">@{p.username}</div>
        <div className="truncate text-[11px] text-zinc-500">
          {c?.display_name || (c ? "—" : "Not analysed yet")}
          {c?.followers.available && <> · {num(c.followers.value)} followers</>}
        </div>
      </div>
      {p.source === "search" && <span className="chip hidden !text-[10px] sm:inline-flex">from search</span>}
      <a href={p.profile_url} target="_blank" rel="noreferrer" title="Open in Threads"
        className="rounded-lg p-1.5 text-zinc-500 opacity-0 transition hover:bg-white/[0.06] hover:text-zinc-100 group-hover:opacity-100">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M14 5h5v5M19 5l-8 8M10 5H6a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1v-4" />
        </svg>
      </a>
      <button onClick={onRemove} title="Remove from list"
        className="rounded-lg p-1.5 text-zinc-500 opacity-0 transition hover:bg-red-500/10 hover:text-red-400 group-hover:opacity-100">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

function AccountCard({ account, color, index, onChange, onDelete }: {
  account: Account; color: string; index: number; onChange: (a: Account) => void; onDelete: () => void;
}) {
  const [open, setOpen] = useState(index === 0);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");
  const profiles = useMemo(() => account.profiles ?? [], [account.profiles]);
  const shown = profiles.filter((p) => p.username.includes(filter.trim().toLowerCase().replace(/^@/, "")));

  const setProfiles = (next: TargetProfile[]) =>
    onChange({ ...account, profiles: next, profiles_total: next.length, profiles_selected: next.filter((p) => p.selected).length });

  const addProfiles = async () => {
    if (!draft.trim()) return;
    setBusy(true);
    try {
      const r = await api<AddProfilesResponse>(`/api/accounts/${account.id}/profiles`, jsonInit("POST", { usernames: draft }));
      onChange(r.account);
      const msg = [`${r.added.length} added`];
      if (r.duplicates.length) msg.push(`${r.duplicates.length} duplicate`);
      if (r.invalid.length) msg.push(`invalid: ${r.invalid.join(", ")}`);
      toast(msg.join(" · "), r.invalid.length ? "error" : "ok");
      setDraft(r.invalid.join(" "));
    } catch (e) {
      toast((e as Error).message, "error");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (p: TargetProfile, selected: boolean) => {
    setProfiles(profiles.map((x) => (x.id === p.id ? { ...x, selected } : x)));
    try {
      await api(`/api/profiles/${p.id}`, jsonInit("PATCH", { selected }));
    } catch (e) {
      setProfiles(profiles);
      toast((e as Error).message, "error");
    }
  };

  const bulk = async (selected: boolean) => {
    const ids = filter ? shown.map((p) => p.id) : undefined;
    try {
      onChange(await api<Account>(`/api/accounts/${account.id}/profiles/select`, jsonInit("POST", { selected, ids })));
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  const remove = async (p: TargetProfile) => {
    setProfiles(profiles.filter((x) => x.id !== p.id));
    try {
      await api(`/api/profiles/${p.id}`, { method: "DELETE" });
    } catch (e) {
      setProfiles(profiles);
      toast((e as Error).message, "error");
    }
  };

  return (
    <div style={{ animationDelay: `${index * 60}ms` }} className="card animate-fade-up overflow-hidden">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition hover:bg-white/[0.02]">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-sm font-bold text-white" style={{ background: `linear-gradient(135deg, ${color}, ${color}99)` }}>
          {account.username[0]?.toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-semibold">@{account.username}</span>
            {account.label && <span className="chip !text-[10px]">{account.label}</span>}
          </div>
          <div className="text-xs text-zinc-500">{account.profiles_total} profiles in list</div>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-400" title="Selected profiles">
          <Ring value={account.profiles_selected} total={account.profiles_total} color={color} />
          <span className="tabular-nums"><span className="font-semibold text-zinc-100">{account.profiles_selected}</span>/{account.profiles_total}</span>
        </div>
        <svg className={`h-4 w-4 text-zinc-500 transition duration-300 ${open ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      <div className={`grid transition-[grid-template-rows] duration-300 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        <div className="overflow-hidden">
          <div className="space-y-4 border-t border-white/[0.05] p-4">
            <div className="flex flex-col gap-2 sm:flex-row">
              <textarea
                className="input min-h-[44px] flex-1 resize-y"
                rows={1}
                placeholder="Add profiles: @user1, user2 or threads.net/@user3 (comma, space or new line)"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    addProfiles();
                  }
                }}
              />
              <button className="btn-primary sm:self-start" onClick={addProfiles} disabled={busy || !draft.trim()}>
                {busy ? <Spinner className="h-4 w-4 border-white border-t-transparent" /> : "Add"}
              </button>
            </div>

            {profiles.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <input className="input !w-44 !py-1.5" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} />
                <button className="btn-ghost !px-2.5 !py-1.5 text-xs" onClick={() => bulk(true)}>Select all{filter && " shown"}</button>
                <button className="btn-ghost !px-2.5 !py-1.5 text-xs" onClick={() => bulk(false)}>Select none</button>
                <span className="ml-auto text-xs text-zinc-500">{account.profiles_selected} selected of {account.profiles_total}</span>
              </div>
            )}

            {profiles.length === 0 ? (
              <p className="py-4 text-center text-sm text-zinc-500">No profiles yet. Add them above or from the Profile Search Engine.</p>
            ) : (
              <div className="max-h-[420px] space-y-1 overflow-y-auto pr-1">
                {shown.map((p, i) => (
                  <ProfileRow key={p.id} p={p} index={i} onToggle={(v) => toggle(p, v)} onRemove={() => remove(p)} />
                ))}
                {shown.length === 0 && <p className="py-3 text-center text-xs text-zinc-500">No profiles match “{filter}”.</p>}
              </div>
            )}

            <div className="flex justify-end gap-2 border-t border-white/[0.05] pt-3">
              <a href={account.profile_url} target="_blank" rel="noreferrer" className="btn-ghost text-xs">Open @{account.username}</a>
              <button className="btn-danger text-xs" onClick={onDelete}>Delete account</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModelDetail({ modelId, onUpdated, onDeleted }: { modelId: number; onUpdated: () => void; onDeleted: () => void }) {
  const [model, setModel] = useState<Talent | null>(null);
  const [acc, setAcc] = useState({ username: "", label: "" });
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState("");

  const load = useCallback(() => {
    api<Talent>(`/api/models/${modelId}`).then((m) => {
      setModel(m);
      setName(m.name);
    }).catch((e) => toast(e.message, "error"));
  }, [modelId]);
  useEffect(() => {
    setModel(null);
    load();
  }, [load]);

  if (!model) return <div className="flex items-center gap-2 p-6 text-sm text-zinc-500"><Spinner /> Loading…</div>;
  const color = model.color || COLORS[model.id % COLORS.length];

  const patch = async (data: Partial<Talent>) => {
    try {
      const m = await api<Talent>(`/api/models/${model.id}`, jsonInit("PATCH", data));
      setModel({ ...model, ...m, accounts: model.accounts });
      onUpdated();
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  const addAccount = async () => {
    if (!acc.username.trim()) return;
    try {
      const a = await api<Account>(`/api/models/${model.id}/accounts`, jsonInit("POST", { username: acc.username, label: acc.label || null }));
      setModel({ ...model, accounts: [...model.accounts, a] });
      setAcc({ username: "", label: "" });
      toast(`Account @${a.username} added`);
      onUpdated();
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  const updateAccount = (a: Account) => {
    setModel((m) => (m ? { ...m, accounts: m.accounts.map((x) => (x.id === a.id ? a : x)) } : m));
    onUpdated();
  };

  const deleteAccount = async (a: Account) => {
    if (!confirm(`Delete @${a.username} and its ${a.profiles_total} saved profiles?`)) return;
    await api(`/api/accounts/${a.id}`, { method: "DELETE" });
    setModel({ ...model, accounts: model.accounts.filter((x) => x.id !== a.id) });
    toast(`@${a.username} deleted`, "info");
    onUpdated();
  };

  const deleteModel = async () => {
    if (!confirm(`Delete model "${model.name}" with ${model.accounts.length} accounts?`)) return;
    await api(`/api/models/${model.id}`, { method: "DELETE" });
    toast(`${model.name} deleted`, "info");
    onDeleted();
  };

  return (
    <div key={model.id} className="animate-slide-in space-y-5">
      <div className="card relative overflow-hidden p-5">
        <div className="absolute inset-x-0 top-0 h-1" style={{ background: `linear-gradient(90deg, ${color}, transparent)` }} />
        <div className="flex flex-wrap items-center gap-4">
          <div className="grid h-12 w-12 place-items-center rounded-2xl text-lg font-bold text-white shadow-lg transition-colors duration-500"
            style={{ background: `linear-gradient(135deg, ${color}, ${color}88)`, boxShadow: `0 10px 30px -10px ${color}` }}>
            {model.name[0]?.toUpperCase()}
          </div>
          <div className="min-w-[160px] flex-1">
            {editingName ? (
              <input autoFocus className="input !py-1 text-lg font-semibold" value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => { setEditingName(false); if (name.trim() && name !== model.name) patch({ name: name.trim() }); }}
                onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()} />
            ) : (
              <button onClick={() => setEditingName(true)} className="text-left text-xl font-bold tracking-tight hover:text-brand-200" title="Rename">
                {model.name}
              </button>
            )}
            <div className="text-xs text-zinc-500">
              {model.accounts.length} accounts · {model.accounts.reduce((s, a) => s + a.profiles_total, 0)} profiles ·{" "}
              {model.accounts.reduce((s, a) => s + a.profiles_selected, 0)} selected
            </div>
          </div>
          <div className="order-last flex w-full items-center gap-1.5 sm:order-none sm:w-auto">
            {COLORS.map((c) => (
              <button key={c} onClick={() => patch({ color: c })} title={c}
                className={`h-5 w-5 rounded-full transition hover:scale-125 ${c === color ? "ring-2 ring-white/70 ring-offset-2 ring-offset-ink-900" : ""}`}
                style={{ background: c }} />
            ))}
          </div>
          <button className="btn-danger text-xs" onClick={deleteModel}>Delete model</button>
        </div>

        <div className="mt-5 flex flex-col gap-2 border-t border-white/[0.05] pt-4 sm:flex-row">
          <input className="input sm:max-w-xs" placeholder="@threads_account" value={acc.username}
            onChange={(e) => setAcc({ ...acc, username: e.target.value })} onKeyDown={(e) => e.key === "Enter" && addAccount()} />
          <input className="input sm:max-w-[200px]" placeholder="Label (optional)" value={acc.label}
            onChange={(e) => setAcc({ ...acc, label: e.target.value })} onKeyDown={(e) => e.key === "Enter" && addAccount()} />
          <button className="btn-primary" onClick={addAccount} disabled={!acc.username.trim()}>Add account</button>
        </div>
      </div>

      {model.accounts.length === 0 ? (
        <Empty title="No accounts yet" icon="@">Add the Threads accounts that belong to {model.name}. Each account gets its own profile list.</Empty>
      ) : (
        <div className="space-y-3">
          {model.accounts.map((a, i) => (
            <AccountCard key={a.id} account={a} color={color} index={i} onChange={updateAccount} onDelete={() => deleteAccount(a)} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ModelsPage() {
  const [models, setModels] = useState<Talent[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [newName, setNewName] = useState("");

  const load = useCallback(async () => {
    try {
      const m = await api<Talent[]>("/api/models");
      setModels(m);
      setSelected((s) => (s && m.some((x) => x.id === s) ? s : m[0]?.id ?? null));
    } catch (e) {
      toast((e as Error).message, "error");
      setModels([]);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    if (!newName.trim()) return;
    try {
      const m = await api<Talent>("/api/models", jsonInit("POST", { name: newName.trim(), color: COLORS[(models?.length ?? 0) % COLORS.length] }));
      setNewName("");
      await load();
      setSelected(m.id);
      toast(`Model ${m.name} created`);
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  return (
    <div>
      <PageHeader
        title={<>Models<span className="text-gradient">/Accs</span></>}
        subtitle="Your models, their Threads accounts, and each account's list of profiles. Tick the profiles you want active for an account."
        actions={
          <div className="flex gap-2">
            <input className="input !w-56" placeholder="New model name" value={newName}
              onChange={(e) => setNewName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && create()} />
            <button className="btn-primary" onClick={create} disabled={!newName.trim()}>New model</button>
          </div>
        }
      />

      {models === null ? (
        <div className="flex items-center gap-2 text-sm text-zinc-500"><Spinner /> Loading…</div>
      ) : models.length === 0 ? (
        <Empty title="Create your first model" icon="✦">Add a model above, then add her Threads accounts and their profile lists.</Empty>
      ) : (
        <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
          <div className="space-y-2">
            {models.map((m, i) => {
              const color = m.color || COLORS[m.id % COLORS.length];
              const active = m.id === selected;
              const profiles = m.accounts.reduce((s, a) => s + a.profiles_total, 0);
              return (
                <button key={m.id} onClick={() => setSelected(m.id)} style={{ animationDelay: `${i * 50}ms` }}
                  className={`card group flex w-full animate-fade-up items-center gap-3 p-3 text-left transition duration-300 ${
                    active ? "!border-brand-500/40 !bg-brand-500/[0.07] shadow-[0_10px_40px_-20px_rgb(139_92_246/0.8)]" : "hover:!border-white/15 hover:!bg-white/[0.04]"
                  }`}>
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl text-sm font-bold text-white transition group-hover:scale-105"
                    style={{ background: `linear-gradient(135deg, ${color}, ${color}88)` }}>
                    {m.name[0]?.toUpperCase()}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{m.name}</span>
                    <span className="block text-xs text-zinc-500">{m.accounts.length} accs · {profiles} profiles</span>
                  </span>
                  {active && <span className="h-2 w-2 rounded-full bg-brand-400 shadow-[0_0_10px_2px_rgb(167_139_250/0.7)]" />}
                </button>
              );
            })}
          </div>
          {selected !== null && (
            <ModelDetail key={selected} modelId={selected} onUpdated={load}
              onDeleted={() => { setSelected(null); load(); }} />
          )}
        </div>
      )}
    </div>
  );
}
