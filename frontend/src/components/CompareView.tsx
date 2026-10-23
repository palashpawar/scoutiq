"use client";

import { useEffect, useRef } from "react";
import { COMPARE_COLORS, euros, metricValue, ordinal } from "@/lib/format";
import type { PlayerResult } from "@/lib/types";

interface Props {
  players: PlayerResult[];
  onRemove: (id: number) => void;
  onClose: () => void;
}

export function CompareView({ players, onRemove, onClose }: Props) {
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

  const keys: string[] = [];
  const meta = new Map<string, PlayerResult["metrics"][number]>();
  for (const p of players)
    for (const m of p.metrics)
      if (!meta.has(m.key)) {
        meta.set(m.key, m);
        keys.push(m.key);
      }
  const roles = new Set(players.map((p) => p.role));

  // For each metric, who leads on percentile?
  const leader = (key: string) => {
    let best: number | null = null;
    let id: number | null = null;
    for (const p of players) {
      const pct = p.metrics.find((m) => m.key === key)?.percentile ?? null;
      if (pct !== null && (best === null || pct > best)) {
        best = pct;
        id = p.id;
      }
    }
    return id;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-navy-950/80 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="compare-title">
      <div className="mx-auto my-4 w-[calc(100%-2rem)] max-w-5xl rounded-2xl border border-navy-700 bg-navy-900 shadow-2xl sm:my-10">
        <div className="flex items-center justify-between border-b border-navy-700 px-5 py-4">
          <div>
            <h2 id="compare-title" className="text-lg font-semibold text-white">Compare players</h2>
            <p className="text-xs text-slate-400">Bars show dataset-relative percentiles vs. role peers (900+ minutes). Values are per 90 unless marked %.</p>
          </div>
          <button ref={closeRef} onClick={onClose} className="rounded-lg border border-navy-600 px-2.5 py-1 text-sm text-slate-300 hover:border-slate-400" aria-label="Close comparison">
            ✕
          </button>
        </div>

        {players.length < 2 && (
          <p className="px-5 pt-4 text-sm text-amber-200">Add at least two players to make a comparison more useful.</p>
        )}
        {roles.size > 1 && (
          <p className="px-5 pt-4 text-sm text-amber-200">
            These players are in different role groups, so their percentiles are measured against different peers.
          </p>
        )}

        <div className={`grid grid-cols-1 gap-3 px-5 pt-5 ${players.length === 3 ? "md:grid-cols-3" : players.length === 2 ? "sm:grid-cols-2" : ""}`}>
          {players.map((p, i) => (
            <div key={p.id} className="overflow-hidden rounded-xl border border-navy-700 bg-navy-850 p-3">
              <div className={`-mx-3 -mt-3 mb-3 h-1 ${COMPARE_COLORS[i].bar}`} aria-hidden />
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${COMPARE_COLORS[i].dot}`} />
                    <h3 className="truncate text-sm font-semibold text-white sm:text-base">{p.display_name}</h3>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-slate-400">{p.club}</p>
                </div>
                <button onClick={() => onRemove(p.id)} className="text-xs text-slate-500 hover:text-rose-300" aria-label={`Remove ${p.display_name} from comparison`}>
                  ✕
                </button>
              </div>
              <dl className="tabular mt-3 grid grid-cols-4 gap-1.5 text-center">
                {[
                  ["Fit", p.score.toFixed(1)],
                  ["Age", p.age ?? "n/a"],
                  ["Min", p.minutes.toLocaleString()],
                  ["Value", euros(p.market_value_eur)],
                ].map(([k, v], j) => (
                  <div key={k as string} className="flex flex-col-reverse rounded-md bg-navy-800 px-1 py-1.5">
                    <dt className="text-[10px] uppercase tracking-wide text-slate-500">{k}</dt>
                    <dd className={`text-sm font-semibold ${j === 0 ? COMPARE_COLORS[i].text : "text-slate-100"}`}>{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ))}
        </div>

        <div className="space-y-4 px-5 py-5">
          {keys.map((key) => {
            const m = meta.get(key)!;
            const lead = leader(key);
            return (
              <div key={key} className="rounded-xl border border-navy-800 bg-navy-850/60 p-3">
                <div className="mb-2 flex items-baseline justify-between">
                  <h4 className="text-sm font-medium text-slate-200" title={m.description}>{m.label}</h4>
                  <span className="text-[10px] uppercase tracking-wide text-slate-500">{m.group}</span>
                </div>
                <div className="space-y-1.5">
                  {players.map((p, i) => {
                    const pm = p.metrics.find((x) => x.key === key);
                    const pct = pm?.percentile ?? null;
                    return (
                      <div key={p.id} className="grid grid-cols-[minmax(0,7rem)_1fr_auto] items-center gap-2 text-xs sm:grid-cols-[10rem_1fr_7rem]">
                        <span className="truncate text-slate-400">{p.display_name}</span>
                        <div className="relative h-2.5 overflow-hidden rounded-full bg-navy-700" role="meter" aria-label={`${p.display_name} ${m.label} percentile`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct ?? undefined}>
                          <div className={`h-full rounded-full ${COMPARE_COLORS[i].bar}`} style={{ width: `${pct ?? 0}%`, opacity: lead === p.id ? 1 : 0.6 }} />
                          <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300/30" />
                        </div>
                        <span className="tabular text-right text-slate-300">
                          {pm ? metricValue(pm.value, pm.unit) : "n/a"} · <span className="font-semibold text-white">{pct === null ? "n/a" : ordinal(pct)}</span>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
        <p className="border-t border-navy-700 px-5 py-3 text-xs text-slate-500">
          Fit scores reflect the brief that was active when each player was added. Statistics describe one historical season and do not by themselves establish tactical fit.
        </p>
      </div>
    </div>
  );
}
