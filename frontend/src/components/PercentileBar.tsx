import { metricValue, ordinal, pctTone } from "@/lib/format";

interface Props {
  label: string;
  percentile: number | null;
  value: number | null;
  unit: string;
  weight?: number;
  compact?: boolean;
  barClass?: string;
  title?: string;
}

/** Horizontal, dataset-relative percentile bar with a median tick. */
export function PercentileBar({ label, percentile, value, unit, weight, compact, barClass, title }: Props) {
  const pct = percentile ?? 0;
  return (
    <div className={compact ? "space-y-1" : "space-y-1.5"} title={title}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="truncate text-slate-300">
          {label}
          {weight !== undefined && weight > 0 && (
            <span className="ml-1.5 rounded bg-navy-700 px-1 py-px text-[10px] font-medium text-emerald-300">
              {Math.round(weight * 100)}%
            </span>
          )}
        </span>
        <span className="tabular shrink-0 text-slate-400">
          <span className="text-slate-200">{metricValue(value, unit)}</span>
          {unit !== "%" && value !== null && <span className="text-slate-500"> /90</span>}
          <span className="ml-2 inline-block w-10 text-right font-semibold text-slate-100">
            {percentile === null ? "n/a" : ordinal(percentile)}
          </span>
        </span>
      </div>
      <div
        className={`relative w-full overflow-hidden rounded-full bg-navy-700/80 ${compact ? "h-1.5" : "h-2"}`}
        role="meter"
        aria-label={`${label} percentile`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percentile ?? undefined}
        aria-valuetext={percentile === null ? "No data" : `${ordinal(percentile)} percentile`}
      >
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${barClass ?? pctTone(percentile)}`}
          style={{ width: `${Math.max(pct, percentile === null ? 0 : 2)}%` }}
        />
        <div className="absolute inset-y-0 left-1/2 w-px bg-slate-400/40" aria-hidden />
      </div>
    </div>
  );
}
