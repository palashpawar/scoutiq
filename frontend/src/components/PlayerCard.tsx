import { euros, POSITION_SHORT } from "@/lib/format";
import type { PlayerResult } from "@/lib/types";
import { PercentileBar } from "./PercentileBar";
import { Badge } from "./ui";

interface Props {
  player: PlayerResult;
  summary?: string;
  summaryLoading: boolean;
  compared: boolean;
  compareDisabled: boolean;
  onOpen: () => void;
  onToggleCompare: () => void;
}

export function PlayerCard({ player: p, summary, summaryLoading, compared, compareDisabled, onOpen, onToggleCompare }: Props) {
  const weighted = p.metrics.filter((m) => m.weight > 0).slice(0, 5);
  return (
    <article className="group flex flex-col rounded-2xl border border-navy-700 bg-navy-850/80 p-4 shadow-lg shadow-black/20 transition hover:border-emerald-500/40 sm:p-5">
      <header className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-navy-700 text-sm font-bold text-emerald-300">
          {p.rank}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-white sm:text-lg">{p.display_name}</h3>
          <p className="truncate text-sm text-slate-400">
            {p.club} · {POSITION_SHORT[p.primary_position] ?? p.primary_position} · {p.age ?? "age n/a"}
          </p>
        </div>
        <div className="text-right">
          <div className="tabular text-2xl font-bold leading-none text-emerald-300">{p.score.toFixed(0)}</div>
          <div className="mt-1 text-[10px] uppercase tracking-wide text-slate-500">fit score</div>
        </div>
      </header>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge title="League minutes in the season">{p.minutes.toLocaleString()} min</Badge>
        <Badge title={p.valuation_date ? `Transfermarkt estimate as of ${p.valuation_date}` : "No valuation matched"}>
          {p.market_value_eur !== null ? `Est. ${euros(p.market_value_eur)}` : "Value n/a"}
        </Badge>
        {p.coverage < 1 && <Badge tone="amber">{Math.round(p.coverage * 100)}% weight coverage</Badge>}
        {p.minutes < 1500 && <Badge tone="amber">Small sample</Badge>}
        {p.value_signal?.potentially_undervalued && (
          <Badge tone="emerald" title={p.value_signal.explanation}>
            Potentially undervalued*
          </Badge>
        )}
      </div>

      <div className="mt-4 space-y-2.5">
        {weighted.map((m) => (
          <PercentileBar key={m.key} label={m.short} percentile={m.percentile} value={m.value} unit={m.unit} weight={m.effective_weight} compact />
        ))}
      </div>

      <div className="mt-4 min-h-[3.5rem] text-sm leading-relaxed text-slate-300">
        {summary ? (
          <p>{summary}</p>
        ) : summaryLoading ? (
          <div className="space-y-2" aria-label="Loading summary">
            <div className="skeleton h-3 w-full rounded" />
            <div className="skeleton h-3 w-4/5 rounded" />
          </div>
        ) : null}
      </div>

      <footer className="mt-auto flex gap-2 pt-4">
        <button
          onClick={onOpen}
          className="flex-1 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-navy-950 transition hover:bg-emerald-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-300"
        >
          Why this player?
        </button>
        <button
          onClick={onToggleCompare}
          disabled={!compared && compareDisabled}
          aria-pressed={compared}
          title={!compared && compareDisabled ? "You can compare up to three players" : undefined}
          className={`rounded-lg border px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
            compared ? "border-emerald-400 bg-emerald-500/15 text-emerald-200" : "border-navy-600 text-slate-200 hover:border-emerald-500/60"
          }`}
        >
          {compared ? "✓ Comparing" : "+ Compare"}
        </button>
      </footer>
    </article>
  );
}

export function PlayerCardSkeleton() {
  return (
    <div className="rounded-2xl border border-navy-700 bg-navy-850/80 p-5">
      <div className="flex gap-3">
        <div className="skeleton h-9 w-9 rounded-xl" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-4 w-2/3 rounded" />
          <div className="skeleton h-3 w-1/2 rounded" />
        </div>
      </div>
      <div className="mt-5 space-y-3">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton h-3 w-full rounded" />
        ))}
      </div>
      <div className="skeleton mt-6 h-9 w-full rounded-lg" />
    </div>
  );
}
