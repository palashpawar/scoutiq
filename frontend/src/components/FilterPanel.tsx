"use client";

import { useState } from "react";
import type { AppConfig, Role, StructuredQuery } from "@/lib/types";

interface Props {
  config: AppConfig;
  query: StructuredQuery;
  busy: boolean;
  onApply: (q: StructuredQuery) => void;
}

const DEFAULT_PROFILE: Record<Role, string> = {
  central_midfielder: "ball_progressing_midfielder",
  winger: "creative_winger",
  striker: "goal_scoring_striker",
};

const toPercents = (w: Record<string, number>) => {
  const total = Object.values(w).reduce((a, b) => a + b, 0) || 1;
  return Object.fromEntries(Object.entries(w).map(([k, v]) => [k, Math.round((v / total) * 100)]));
};

const inputCls =
  "w-full rounded-lg border border-navy-600 bg-navy-900 px-3 py-2 text-sm text-white placeholder:text-slate-500 focus:border-emerald-400 focus:outline-none disabled:opacity-50";

export function FilterPanel({ config, query, busy, onApply }: Props) {
  const [draft, setDraft] = useState<StructuredQuery>(() => ({ ...query, metric_weights: toPercents(query.metric_weights) }));
  const [budgetText, setBudgetText] = useState(query.maximum_market_value_eur ? String(query.maximum_market_value_eur / 1e6) : "");
  const [ageText, setAgeText] = useState(query.maximum_age ? String(query.maximum_age) : "");
  const [error, setError] = useState<string | null>(null);
  const metricLabel = Object.fromEntries(config.metrics.map((m) => [m.key, m]));
  const valuations = config.dataset.valuations_enabled;
  const unused = config.metrics.filter((m) => !(m.key in draft.metric_weights));

  const set = (patch: Partial<StructuredQuery>) => setDraft((d) => ({ ...d, ...patch }));
  const setWeight = (k: string, v: number) => set({ metric_weights: { ...draft.metric_weights, [k]: v } });
  const removeWeight = (k: string) => {
    const w = { ...draft.metric_weights };
    delete w[k];
    set({ metric_weights: w });
  };
  const applyProfile = (key: string) => {
    const p = config.profiles.find((x) => x.key === key)!;
    set({ role: p.role, metric_weights: toPercents(p.weights) });
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const age = ageText.trim() === "" ? null : Number(ageText);
    if (age !== null && (!Number.isInteger(age) || age < 16 || age > 45)) return setError("Max age must be a whole number between 16 and 45.");
    const budget = budgetText.trim() === "" ? null : Number(budgetText);
    if (budget !== null && (!Number.isFinite(budget) || budget < 0.1 || budget > 300)) return setError("Budget must be between €0.1M and €300M.");
    const weights = Object.fromEntries(Object.entries(draft.metric_weights).filter(([, v]) => v > 0));
    if (!Object.keys(weights).length) return setError("Give at least one metric a weight above zero.");
    onApply({ ...draft, maximum_age: age, maximum_market_value_eur: budget === null ? null : Math.round(budget * 1e6), metric_weights: weights });
  };

  const totalPct = Object.values(draft.metric_weights).reduce((a, b) => a + b, 0) || 1;

  return (
    <form onSubmit={submit} className="space-y-5" aria-label="Edit filters">
      <div>
        <label className="mb-1.5 block text-xs font-medium text-slate-400" htmlFor="f-role">Role</label>
        <select
          id="f-role"
          className={inputCls}
          value={draft.role}
          onChange={(e) => {
            const role = e.target.value as Role;
            const p = config.profiles.find((x) => x.key === DEFAULT_PROFILE[role])!;
            set({ role, metric_weights: toPercents(p.weights) });
          }}
        >
          {Object.entries(config.roles).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-400" htmlFor="f-age">Max age</label>
          <input id="f-age" inputMode="numeric" className={inputCls} placeholder="No limit" value={ageText} onChange={(e) => setAgeText(e.target.value.replace(/[^\d]/g, "").slice(0, 2))} />
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium text-slate-400" htmlFor="f-budget">Budget (€M)</label>
          <input
            id="f-budget"
            inputMode="decimal"
            className={inputCls}
            placeholder={valuations ? "No cap" : "Unavailable"}
            disabled={!valuations}
            value={budgetText}
            onChange={(e) => setBudgetText(e.target.value.replace(/[^\d.]/g, "").slice(0, 6))}
          />
        </div>
      </div>
      {!valuations && <p className="-mt-3 text-xs text-amber-200">No market-value data in this dataset, so budget filtering is off.</p>}

      <div>
        <div className="mb-1.5 flex justify-between text-xs font-medium text-slate-400">
          <label htmlFor="f-min">Minimum minutes</label>
          <span className="tabular text-slate-200">{draft.minimum_minutes.toLocaleString()}</span>
        </div>
        <input id="f-min" type="range" min={0} max={3000} step={90} value={draft.minimum_minutes} onChange={(e) => set({ minimum_minutes: Number(e.target.value) })} className="w-full" />
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-medium text-slate-400" htmlFor="f-limit">Players to show</label>
        <select id="f-limit" className={inputCls} value={draft.result_limit} onChange={(e) => set({ result_limit: Number(e.target.value) })}>
          {Array.from({ length: config.limits.max_results }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>

      <fieldset>
        <legend className="mb-2 text-xs font-medium text-slate-400">Profile presets</legend>
        <div className="flex flex-wrap gap-1.5">
          {config.profiles.filter((p) => p.role === draft.role).map((p) => (
            <button type="button" key={p.key} onClick={() => applyProfile(p.key)} title={p.blurb} className="rounded-full border border-navy-600 px-2.5 py-1 text-xs text-slate-200 hover:border-emerald-400">
              {p.label}
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-xs font-medium text-slate-400">Scoring weights</legend>
        <div className="space-y-3">
          {Object.entries(draft.metric_weights).map(([k, v]) => (
            <div key={k}>
              <div className="flex items-center justify-between text-xs">
                <label htmlFor={`w-${k}`} className="text-slate-200" title={metricLabel[k]?.description}>{metricLabel[k]?.label ?? k}</label>
                <span className="flex items-center gap-2">
                  <span className="tabular w-9 text-right text-emerald-300">{Math.round((v / totalPct) * 100)}%</span>
                  <button type="button" onClick={() => removeWeight(k)} className="text-slate-500 hover:text-rose-300" aria-label={`Remove ${metricLabel[k]?.label ?? k}`}>✕</button>
                </span>
              </div>
              <input id={`w-${k}`} type="range" min={0} max={100} value={v} onChange={(e) => setWeight(k, Number(e.target.value))} className="w-full" />
            </div>
          ))}
        </div>
        {unused.length > 0 && (
          <select aria-label="Add a metric" className={`${inputCls} mt-3`} value="" onChange={(e) => e.target.value && setWeight(e.target.value, 15)}>
            <option value="">+ Add a metric…</option>
            {unused.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        )}
      </fieldset>

      {error && <p role="alert" className="text-xs text-rose-300">{error}</p>}
      <button type="submit" disabled={busy} className="w-full rounded-lg bg-emerald-500 py-2.5 text-sm font-semibold text-navy-950 hover:bg-emerald-400 disabled:opacity-50">
        Apply filters
      </button>
    </form>
  );
}
