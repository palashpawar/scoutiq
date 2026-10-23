"use client";

import { useEffect, useRef } from "react";
import { euros, metricValue, ordinal, POSITION_SHORT } from "@/lib/format";
import type { DatasetMeta, PlayerResult, SearchResponse } from "@/lib/types";
import { PercentileBar } from "./PercentileBar";
import { Badge } from "./ui";

interface Props {
  player: PlayerResult;
  response: SearchResponse;
  dataset: DatasetMeta;
  summary?: string;
  summarySource?: string;
  compared: boolean;
  compareDisabled: boolean;
  onToggleCompare: () => void;
  onClose: () => void;
}

const SEG_COLORS = ["bg-emerald-400", "bg-emerald-600", "bg-teal-400", "bg-teal-600", "bg-sky-500", "bg-sky-700", "bg-cyan-400", "bg-slate-400"];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-navy-700 px-5 py-4 sm:px-6">
      <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">{title}</h3>
      {children}
    </section>
  );
}

export function PlayerDrawer({ player: p, response, dataset, summary, summarySource, compared, compareDisabled, onToggleCompare, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const weighted = p.metrics.filter((m) => m.weight > 0);
  const other = p.metrics.filter((m) => m.weight === 0);
  const vs = p.value_signal;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
      <button className="absolute inset-0 bg-navy-950/70 backdrop-blur-sm" aria-label="Close details" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-navy-700 bg-navy-900 shadow-2xl">
        <div className="sticky top-0 z-10 border-b border-navy-700 bg-navy-900/95 px-5 py-4 backdrop-blur sm:px-6">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wider text-emerald-400">Why this player? · #{p.rank}</p>
              <h2 id="drawer-title" className="mt-1 truncate text-xl font-semibold text-white">{p.display_name}</h2>
              <p className="text-sm text-slate-400">
                {p.club} · {p.role_label} ({POSITION_SHORT[p.primary_position] ?? p.primary_position}) · {p.season}
              </p>
            </div>
            <button ref={closeRef} onClick={onClose} className="rounded-lg border border-navy-600 px-2.5 py-1 text-sm text-slate-300 hover:border-slate-400" aria-label="Close">
              ✕
            </button>
          </div>
          <div className="mt-3 grid grid-cols-4 gap-2 text-center">
            {[
              ["Fit score", p.score.toFixed(1)],
              ["Age", p.age ?? "n/a"],
              ["Minutes", p.minutes.toLocaleString()],
              ["Est. value", euros(p.market_value_eur)],
            ].map(([k, v]) => (
              <div key={k as string} className="rounded-lg bg-navy-800 px-2 py-2">
                <div className="tabular text-sm font-semibold text-white">{v}</div>
                <div className="text-[10px] uppercase tracking-wide text-slate-500">{k}</div>
              </div>
            ))}
          </div>
        </div>

        {summary && (
          <Section title={summarySource === "meta" ? "Scouting summary (Meta model, from computed data)" : "Scouting summary (template)"}>
            <p className="text-sm leading-relaxed text-slate-200">{summary}</p>
          </Section>
        )}

        <Section title="How the score is built">
          <p className="mb-3 text-sm text-slate-400">
            Fit score = Σ (weight × percentile). Each segment below is one metric&apos;s contribution out of 100.
          </p>
          <div className="flex h-4 w-full overflow-hidden rounded-full bg-navy-700" aria-hidden>
            {weighted.map((m, i) =>
              m.contribution ? (
                <div key={m.key} className={`${SEG_COLORS[i % SEG_COLORS.length]} h-full border-r border-navy-900`} style={{ width: `${m.contribution}%` }} title={`${m.short}: ${m.contribution.toFixed(1)}`} />
              ) : null,
            )}
          </div>
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                <th className="pb-2 font-medium">Metric</th>
                <th className="pb-2 text-right font-medium">Value</th>
                <th className="pb-2 text-right font-medium">Pct</th>
                <th className="pb-2 text-right font-medium">Weight</th>
                <th className="pb-2 text-right font-medium">Pts</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {weighted.map((m, i) => (
                <tr key={m.key} className="border-t border-navy-800" title={m.description}>
                  <td className="py-1.5 pr-2 text-slate-200">
                    <span className={`mr-2 inline-block h-2 w-2 rounded-full ${SEG_COLORS[i % SEG_COLORS.length]}`} />
                    {m.label}
                  </td>
                  <td className="py-1.5 text-right text-slate-300">{metricValue(m.value, m.unit)}</td>
                  <td className="py-1.5 text-right text-slate-300">{m.percentile === null ? "n/a" : ordinal(m.percentile)}</td>
                  <td className="py-1.5 text-right text-slate-400">
                    {m.percentile === null ? <s>{Math.round(m.weight * 100)}%</s> : `${Math.round(m.effective_weight * 100)}%`}
                  </td>
                  <td className="py-1.5 text-right font-semibold text-emerald-300">{m.contribution === null ? "—" : m.contribution.toFixed(1)}</td>
                </tr>
              ))}
              <tr className="border-t border-navy-600">
                <td className="py-2 font-semibold text-white" colSpan={4}>Fit score</td>
                <td className="py-2 text-right font-bold text-emerald-300">{p.score.toFixed(1)}</td>
              </tr>
            </tbody>
          </table>
          {p.coverage < 1 && (
            <p className="mt-2 text-xs text-amber-200">
              Reduced coverage: only {Math.round(p.coverage * 100)}% of the requested weight had data; weights were renormalised.
            </p>
          )}
        </Section>

        <Section title="Strengths and trade-offs">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="mb-1.5 text-xs font-medium text-emerald-300">Strengths (≥75th pct)</p>
              {p.strengths.length ? (
                <ul className="space-y-1 text-sm text-slate-200">{p.strengths.map((s) => <li key={s}>▲ {s}</li>)}</ul>
              ) : (
                <p className="text-sm text-slate-500">No metric at or above the 75th percentile.</p>
              )}
            </div>
            <div>
              <p className="mb-1.5 text-xs font-medium text-amber-300">Trade-offs</p>
              {p.tradeoffs.length ? (
                <ul className="space-y-1 text-sm text-slate-200">{p.tradeoffs.map((s) => <li key={s}>▼ {s}</li>)}</ul>
              ) : (
                <p className="text-sm text-slate-500">No weighted metric at or below the 40th percentile.</p>
              )}
            </div>
          </div>
        </Section>

        <Section title="All relevant metrics">
          <p className="mb-3 text-xs text-slate-500">{response.percentile_note}</p>
          <div className="space-y-3">
            {[...weighted, ...other].map((m) => (
              <PercentileBar key={m.key} label={m.label} percentile={m.percentile} value={m.value} unit={m.unit} weight={m.weight > 0 ? m.effective_weight : undefined} title={m.description} />
            ))}
          </div>
        </Section>

        <Section title="Value context">
          {p.market_value_eur !== null ? (
            <div className="space-y-2 text-sm text-slate-300">
              <p>
                Estimated market value <span className="font-semibold text-white">{euros(p.market_value_eur)}</span> as of {p.valuation_date}.
                This is a Transfermarkt community estimate, not a transfer fee or asking price.
              </p>
              {vs ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge>Score rank: {ordinal(vs.score_percentile)} pct</Badge>
                    <Badge>Value rank: {ordinal(vs.value_percentile)} pct</Badge>
                    <Badge tone={vs.potentially_undervalued ? "emerald" : "slate"}>Gap {vs.gap > 0 ? "+" : ""}{vs.gap.toFixed(0)}</Badge>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-400">{vs.explanation}</p>
                </>
              ) : (
                <p className="text-xs text-slate-400">Value comparison not shown: valuation coverage for this pool is too low for a fair comparison.</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-slate-400">No market-value estimate was matched for this player, so no value comparison is made.</p>
          )}
        </Section>

        <Section title="Applied filters and weights">
          <ul className="mb-3 flex flex-wrap gap-1.5">{response.applied_filters.map((f) => <li key={f}><Badge>{f}</Badge></li>)}</ul>
          <ul className="flex flex-wrap gap-1.5">
            {response.weights.map((w) => (
              <li key={w.key}><Badge tone="emerald">{w.label}: {Math.round(w.weight * 100)}%</Badge></li>
            ))}
          </ul>
        </Section>

        <Section title="Missing data">
          {p.missing_data.length ? (
            <ul className="space-y-1 text-sm text-amber-100">{p.missing_data.map((m) => <li key={m}>• {m}</li>)}</ul>
          ) : (
            <p className="text-sm text-slate-400">All scored metrics, age and valuation are available for this player.</p>
          )}
        </Section>

        <Section title="Source and limits">
          <ul className="space-y-1.5 text-xs leading-relaxed text-slate-400">
            <li>Season: {dataset.league} {dataset.season} ({dataset.matches} matches). Historical data — not current form.</li>
            <li>Event statistics: {dataset.stats_source}. Data provided by StatsBomb.</li>
            {dataset.valuation_source && <li>Valuations &amp; dates of birth: {dataset.valuation_source}. Name match confidence {p.valuation_match_confidence ?? "n/a"}.</li>}
            <li>Ages are as of {dataset.age_reference_date}. Totals: {p.goals ?? "n/a"} goals, {p.assists ?? "n/a"} assists in {p.matches} apps ({p.starts} starts).</li>
            <li className="text-slate-300">A handful of per-90 statistics cannot establish tactical fit. Use this shortlist to decide who to watch, not who to sign.</li>
          </ul>
        </Section>

        <div className="sticky bottom-0 mt-auto border-t border-navy-700 bg-navy-900/95 p-4 backdrop-blur">
          <button
            onClick={onToggleCompare}
            disabled={!compared && compareDisabled}
            className="w-full rounded-lg border border-emerald-500/60 py-2 text-sm font-semibold text-emerald-200 hover:bg-emerald-500/10 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {compared ? "Remove from comparison" : compareDisabled ? "Comparison full (3 players)" : "Add to comparison"}
          </button>
        </div>
      </aside>
    </div>
  );
}
