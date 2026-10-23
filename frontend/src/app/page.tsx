"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CompareView } from "@/components/CompareView";
import { FilterPanel } from "@/components/FilterPanel";
import { PlayerCard, PlayerCardSkeleton } from "@/components/PlayerCard";
import { PlayerDrawer } from "@/components/PlayerDrawer";
import { Badge, Logo, Notice, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { COMPARE_COLORS, euros } from "@/lib/format";
import type { AppConfig, PlayerResult, SearchResponse, StructuredQuery } from "@/lib/types";

const REFINE_CHIPS = ["Prioritize defensive contribution", "Increase the budget to €25 million", "Only players under 23", "Show five players"];
const MAX_COMPARE = 3;

interface HistoryItem {
  label: string;
  response: SearchResponse;
}

export default function Home() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [refineText, setRefineText] = useState("");
  const [busy, setBusy] = useState<null | "search" | "refine" | "rank">(null);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [summaries, setSummaries] = useState<Record<string, string>>({});
  const [summarySource, setSummarySource] = useState<string>("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryWarning, setSummaryWarning] = useState<string | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);
  const [compare, setCompare] = useState<PlayerResult[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const reqId = useRef(0);

  const loadConfig = useCallback(() => {
    setConfigError(null);
    api.config().then(setConfig).catch((e: ApiError) => setConfigError(e.message));
  }, []);
  useEffect(loadConfig, [loadConfig]);

  const loadSummaries = useCallback((res: SearchResponse) => {
    const id = ++reqId.current;
    setSummaries({});
    setSummaryWarning(null);
    if (!res.results.length) return;
    setSummaryLoading(true);
    api
      .summaries(res.query, res.results.map((r) => r.id))
      .then((s) => {
        if (id !== reqId.current) return;
        setSummaries(s.summaries);
        setSummarySource(s.source);
        setSummaryWarning(s.warnings[0] ?? null);
      })
      .catch(() => id === reqId.current && setSummaryWarning("Summaries unavailable — scores and evidence are unaffected."))
      .finally(() => id === reqId.current && setSummaryLoading(false));
  }, []);

  const run = async (kind: "search" | "refine" | "rank", fn: () => Promise<SearchResponse>, label: string) => {
    setBusy(kind);
    setError(null);
    try {
      const res = await fn();
      setResponse(res);
      setHistory((h) => (kind === "search" ? [{ label, response: res }] : [...h, { label, response: res }]).slice(-8));
      setOpenId(null);
      loadSummaries(res);
      if (kind === "refine") setRefineText("");
      if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  };

  const search = (q: string) => {
    const t = q.trim();
    if (t.length < 3) return setError("Describe the player you're looking for (at least a few words).");
    setText(t);
    run("search", () => api.search(t), t);
  };
  const refine = (t: string) => {
    if (!response || t.trim().length < 2) return;
    run("refine", () => api.refine(response.query, t.trim()), t.trim());
  };
  const applyFilters = (q: StructuredQuery) => run("rank", () => api.rank(q), "Edited filters");

  const toggleCompare = (p: PlayerResult) =>
    setCompare((c) => (c.some((x) => x.id === p.id) ? c.filter((x) => x.id !== p.id) : c.length >= MAX_COMPARE ? c : [...c, p]));

  const openPlayer = response?.results.find((r) => r.id === openId) ?? null;
  const ds = config?.dataset;

  // --------------------------------------------------------------- render
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-navy-700/80 bg-navy-900/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <button onClick={() => { setResponse(null); setHistory([]); setError(null); }} aria-label="ScoutIQ home">
            <Logo />
          </button>
          <div className="flex min-w-0 items-center gap-2">
            {ds && (
              <span className="hidden truncate text-xs text-slate-400 md:inline">
                {ds.league} {ds.season} · StatsBomb Open Data{ds.valuations_enabled ? " · Transfermarkt estimates" : ""}
              </span>
            )}
            {config &&
              (config.mode === "meta" ? (
                <Badge tone="emerald" title="Requests are interpreted by the Meta Model API; ranking is always deterministic Python.">Meta model · {config.model}</Badge>
              ) : (
                <Badge tone="amber" title="No META_API_KEY configured: deterministic parser and template summaries are used.">Demo mode</Badge>
              ))}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 pb-28 sm:px-6">
        {configError && (
          <div className="mt-8">
            <Notice tone="error">
              {configError}{" "}
              <button className="ml-2 underline" onClick={loadConfig}>Retry</button>
            </Notice>
          </div>
        )}

        {!response ? (
          <SearchHero config={config} text={text} setText={setText} busy={busy === "search"} error={error} onSearch={search} />
        ) : (
          <div className="pt-6">
            {/* Prompt + refine */}
            <section className="rounded-2xl border border-navy-700 bg-navy-850/70 p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <p className="text-[11px] font-medium uppercase tracking-wider text-slate-500">Your brief</p>
                  <p className="mt-1 text-sm text-slate-200 sm:text-base">“{text}”</p>
                </div>
                <button onClick={() => { setResponse(null); setHistory([]); }} className="shrink-0 rounded-lg border border-navy-600 px-3 py-1.5 text-sm text-slate-200 hover:border-emerald-400">
                  New search
                </button>
              </div>
              <form className="mt-4 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); refine(refineText); }}>
                <label htmlFor="refine" className="sr-only">Refine the search</label>
                <input
                  id="refine"
                  value={refineText}
                  maxLength={500}
                  onChange={(e) => setRefineText(e.target.value)}
                  placeholder="Refine: e.g. “Prioritize defensive contribution”"
                  className="flex-1 rounded-lg border border-navy-600 bg-navy-900 px-3 py-2.5 text-sm text-white placeholder:text-slate-500 focus:border-emerald-400 focus:outline-none"
                />
                <button disabled={!!busy || refineText.trim().length < 2} className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-navy-950 hover:bg-emerald-400 disabled:opacity-50">
                  {busy === "refine" && <Spinner />} Refine
                </button>
              </form>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {REFINE_CHIPS.map((c) => (
                  <button key={c} disabled={!!busy} onClick={() => refine(c)} className="rounded-full border border-navy-600 bg-navy-900 px-3 py-1 text-xs text-slate-300 hover:border-emerald-400 hover:text-white disabled:opacity-50">
                    {c}
                  </button>
                ))}
              </div>
              {history.length > 1 && (
                <ol className="mt-4 flex flex-wrap items-center gap-1 text-xs text-slate-500" aria-label="Search history">
                  {history.map((h, i) => (
                    <li key={i} className="flex items-center gap-1">
                      {i > 0 && <span aria-hidden>→</span>}
                      <button
                        onClick={() => { setResponse(h.response); setHistory(history.slice(0, i + 1)); loadSummaries(h.response); }}
                        className={`max-w-[14rem] truncate rounded px-1.5 py-0.5 ${i === history.length - 1 ? "bg-navy-700 text-slate-200" : "hover:text-slate-200"}`}
                        title={h.label}
                      >
                        {i === 0 ? "Original search" : h.label}
                      </button>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

            <div className="mt-6 grid gap-6 lg:grid-cols-[18rem_1fr]">
              {/* Filters */}
              <aside className="lg:sticky lg:top-20 lg:self-start">
                <div className="rounded-2xl border border-navy-700 bg-navy-850/70">
                  <button className="flex w-full items-center justify-between px-4 py-3 text-left lg:cursor-default" onClick={() => setFiltersOpen((o) => !o)} aria-expanded={filtersOpen} aria-controls="filters">
                    <span className="text-sm font-semibold text-white">Filters &amp; weights</span>
                    <span className="text-xs text-slate-400 lg:hidden">{filtersOpen ? "Hide" : "Edit"}</span>
                  </button>
                  <div id="filters" className={`${filtersOpen ? "block" : "hidden"} border-t border-navy-700 p-4 lg:block`}>
                    {config && <FilterPanel key={JSON.stringify(response.query)} config={config} query={response.query} busy={!!busy} onApply={applyFilters} />}
                  </div>
                </div>
              </aside>

              {/* Results */}
              <section aria-live="polite" aria-busy={!!busy}>
                <Interpretation response={response} />
                {summaryWarning && <div className="mt-3"><Notice tone="info">{summaryWarning}</Notice></div>}
                {busy ? (
                  <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {Array.from({ length: Math.min(response.query.result_limit, 6) }, (_, i) => <PlayerCardSkeleton key={i} />)}
                  </div>
                ) : response.results.length ? (
                  <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {response.results.map((p) => (
                      <PlayerCard
                        key={p.id}
                        player={p}
                        summary={summaries[String(p.id)]}
                        summaryLoading={summaryLoading}
                        compared={compare.some((c) => c.id === p.id)}
                        compareDisabled={compare.length >= MAX_COMPARE}
                        onOpen={() => setOpenId(p.id)}
                        onToggleCompare={() => toggleCompare(p)}
                      />
                    ))}
                  </div>
                ) : (
                  <EmptyState response={response} onApply={applyFilters} />
                )}
              </section>
            </div>
          </div>
        )}
      </main>

      {ds && <Footer config={config!} />}

      {/* Compare tray */}
      {compare.length > 0 && !compareOpen && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-navy-700 bg-navy-900/95 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-3 sm:px-6">
            <div className="flex min-w-0 flex-1 gap-1.5 overflow-x-auto sm:flex-wrap">
              {compare.map((p, i) => (
                <span key={p.id} className="inline-flex max-w-[9rem] shrink-0 items-center sm:max-w-[11rem] gap-1.5 rounded-full border border-navy-600 bg-navy-800 py-1 pl-2 pr-1 text-xs text-slate-200">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${COMPARE_COLORS[i].dot}`} />
                  <span className="truncate">{p.display_name}</span>
                  <button onClick={() => toggleCompare(p)} className="rounded-full px-1 text-slate-500 hover:text-rose-300" aria-label={`Remove ${p.display_name}`}>✕</button>
                </span>
              ))}
              <span className="self-center text-xs text-slate-500">{compare.length}/{MAX_COMPARE}</span>
            </div>
            <button onClick={() => setCompareOpen(true)} className="shrink-0 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-emerald-400">
              Compare{compare.length > 1 ? ` ${compare.length}` : ""}
            </button>
          </div>
        </div>
      )}

      {openPlayer && response && ds && (
        <PlayerDrawer
          player={openPlayer}
          response={response}
          dataset={ds}
          summary={summaries[String(openPlayer.id)]}
          summarySource={summarySource}
          compared={compare.some((c) => c.id === openPlayer.id)}
          compareDisabled={compare.length >= MAX_COMPARE}
          onToggleCompare={() => toggleCompare(openPlayer)}
          onClose={() => setOpenId(null)}
        />
      )}
      {compareOpen && compare.length > 0 && (
        <CompareView players={compare} onRemove={(id) => setCompare((c) => c.filter((p) => p.id !== id))} onClose={() => setCompareOpen(false)} />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ pieces
function SearchHero({ config, text, setText, busy, error, onSearch }: {
  config: AppConfig | null; text: string; setText: (t: string) => void; busy: boolean; error: string | null; onSearch: (t: string) => void;
}) {
  const ds = config?.dataset;
  return (
    <section className="mx-auto max-w-3xl pt-12 sm:pt-20">
      <p className="text-center text-xs font-semibold uppercase tracking-[0.2em] text-emerald-400">AI scouting assistant</p>
      <h1 className="mt-3 text-center text-3xl font-bold tracking-tight text-white sm:text-5xl">
        Find affordable players who fit your brief.
      </h1>
      <p className="mx-auto mt-4 max-w-xl text-center text-sm text-slate-400 sm:text-base">
        Describe the profile you need. ScoutIQ turns it into transparent filters and weights, ranks players with deterministic
        statistics, and shows the evidence behind every pick.
      </p>

      <form className="mt-8" onSubmit={(e) => { e.preventDefault(); onSearch(text); }}>
        <label htmlFor="prompt" className="sr-only">Scouting request</label>
        <div className="rounded-2xl border border-navy-600 bg-navy-850 p-2 shadow-xl shadow-emerald-950/30 focus-within:border-emerald-400">
          <textarea
            id="prompt"
            rows={3}
            maxLength={config?.limits.max_text ?? 500}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSearch(text); } }}
            placeholder="e.g. Find three midfielders under 25 who progress the ball well and defend, valued below €15M"
            className="w-full resize-none bg-transparent px-3 py-2 text-base text-white placeholder:text-slate-500 focus:outline-none"
          />
          <div className="flex items-center justify-between gap-2 px-2 pb-1">
            <span className="text-xs text-slate-500">{text.length}/{config?.limits.max_text ?? 500}</span>
            <button disabled={busy || !config} className="flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-navy-950 hover:bg-emerald-400 disabled:opacity-50">
              {busy ? <><Spinner /> Scouting…</> : "Scout players"}
            </button>
          </div>
        </div>
      </form>
      {error && <div className="mt-3"><Notice tone="error">{error}</Notice></div>}

      <div className="mt-6">
        <p className="mb-2 text-xs font-medium text-slate-500">Try an example</p>
        <div className="grid gap-2">
          {(config?.examples ?? []).map((ex) => (
            <button key={ex} disabled={busy} onClick={() => onSearch(ex)} className="rounded-xl border border-navy-700 bg-navy-850/60 px-4 py-3 text-left text-sm text-slate-300 transition hover:border-emerald-500/60 hover:text-white disabled:opacity-50">
              <span className="mr-2 text-emerald-400">→</span>{ex}
            </button>
          ))}
          {!config && [0, 1, 2].map((i) => <div key={i} className="skeleton h-12 rounded-xl" />)}
        </div>
      </div>

      {ds && (
        <div className="mt-10 grid gap-3 sm:grid-cols-3">
          {[
            ["1 · Interpret", config!.mode === "meta" ? `Meta model (${config!.model}) converts your request into a validated filter object.` : "Demo mode: a deterministic rule parser converts your request into a validated filter object."],
            ["2 · Rank", "Python filters players and scores them with role-specific weighted percentiles — no AI in the maths."],
            ["3 · Explain", "Every score shows its filters, weights, metric contributions, trade-offs and missing data."],
          ].map(([t, d]) => (
            <div key={t} className="rounded-xl border border-navy-700 bg-navy-850/50 p-4">
              <p className="text-sm font-semibold text-white">{t}</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">{d}</p>
            </div>
          ))}
        </div>
      )}
      {ds && (
        <p className="mt-6 text-center text-xs text-slate-500">
          Dataset: {ds.league} {ds.season} — a historical season ({ds.matches} matches, {ds.players} midfielders, wingers and strikers).
          Real players and real event data, not current form.
        </p>
      )}
    </section>
  );
}

function Interpretation({ response: r }: { response: SearchResponse }) {
  const ex = r.counts.excluded;
  const sourceLabel = {
    meta: "Interpreted by Meta model",
    demo: "Interpreted by demo parser",
    demo_fallback: "Demo parser (model fallback)",
    manual: "Manual filters",
  }[r.parse_source];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={r.parse_source === "meta" ? "emerald" : r.parse_source === "demo_fallback" ? "amber" : "sky"}>{sourceLabel}</Badge>
        {r.profile_label && <Badge tone="emerald">Profile ≈ {r.profile_label}</Badge>}
        {r.applied_filters.map((f) => <Badge key={f}>{f}</Badge>)}
      </div>
      {r.changes && r.changes.length > 0 && (
        <p className="text-xs text-emerald-200">Changed: {r.changes.join(" · ")}</p>
      )}
      {r.warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
      <p className="text-xs text-slate-400">
        {r.counts.eligible} of {r.counts.role_players} players in this role met every filter
        {ex.minutes + ex.age_over_limit + ex.value_over_budget > 0 && (
          <> (excluded: {ex.minutes} under minutes, {ex.age_over_limit} over age{r.budget_active ? `, ${ex.value_over_budget} over budget` : ""})</>
        )}
        {ex.age_unknown + ex.value_unknown > 0 && <>; {ex.age_unknown + ex.value_unknown} excluded for unknown age or value</>}. {r.percentile_note}
      </p>
      <details className="text-xs text-slate-400">
        <summary className="cursor-pointer text-slate-300">Scoring weights</summary>
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {r.weights.map((w) => <li key={w.key}><Badge tone="emerald">{w.label}: {Math.round(w.weight * 100)}%</Badge></li>)}
        </ul>
      </details>
    </div>
  );
}

function EmptyState({ response: r, onApply }: { response: SearchResponse; onApply: (q: StructuredQuery) => void }) {
  const q = r.query;
  const relaxations: { label: string; q: StructuredQuery }[] = [];
  if (q.maximum_market_value_eur) relaxations.push({ label: `Raise budget to ${euros(q.maximum_market_value_eur + 10_000_000)}`, q: { ...q, maximum_market_value_eur: q.maximum_market_value_eur + 10_000_000 } });
  if (q.maximum_age) relaxations.push({ label: `Raise max age to ${Math.min(45, q.maximum_age + 3)}`, q: { ...q, maximum_age: Math.min(45, q.maximum_age + 3) } });
  if (q.minimum_minutes > 450) relaxations.push({ label: "Lower minimum minutes to 450", q: { ...q, minimum_minutes: 450 } });
  return (
    <div className="mt-6 rounded-2xl border border-dashed border-navy-600 p-8 text-center">
      <p className="text-base font-semibold text-white">No players match every filter</p>
      <p className="mt-1 text-sm text-slate-400">This dataset covers one season, so tight combinations can rule everyone out.</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {relaxations.map((x) => (
          <button key={x.label} onClick={() => onApply(x.q)} className="rounded-lg border border-emerald-500/50 px-3 py-1.5 text-sm text-emerald-200 hover:bg-emerald-500/10">
            {x.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Footer({ config }: { config: AppConfig }) {
  const ds = config.dataset;
  return (
    <footer className="border-t border-navy-800 bg-navy-950/60">
      <div className="mx-auto grid max-w-7xl gap-4 px-4 py-6 text-xs text-slate-500 sm:grid-cols-2 sm:px-6">
        <div className="space-y-1">
          <p className="font-medium text-slate-300">Data provenance</p>
          <p>Season: {ds.league} {ds.season} ({ds.matches} matches) — historical, not current form.</p>
          <p>Event statistics: {ds.stats_source}. Data provided by StatsBomb.</p>
          {ds.valuation_source ? (
            <p>Market values &amp; dates of birth: {ds.valuation_source}; {ds.valuation_window}. {ds.players_matched_to_transfermarkt} of {ds.players_matched_to_transfermarkt + ds.players_unmatched} players matched.</p>
          ) : (
            <p>No valuation source loaded — budget filtering disabled.</p>
          )}
        </div>
        <div className="space-y-1">
          <p className="font-medium text-slate-300">How to read this</p>
          <p>Percentiles compare players with role peers who played {ds.percentile_pool_min_minutes}+ minutes in this dataset only.</p>
          <p>Market values are community estimates, not transfer fees. “Potentially undervalued” is a dataset-relative heuristic, not proof of a market inefficiency.</p>
          <p>Statistics cannot establish tactical fit, character or availability. {config.mode === "demo" ? "Demo mode: no AI model is being called." : `Language tasks use ${config.model}; rankings are deterministic.`}</p>
        </div>
      </div>
    </footer>
  );
}
