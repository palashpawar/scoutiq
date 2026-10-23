export function euros(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  if (v >= 1_000_000) return `€${(v / 1_000_000).toFixed(v % 1_000_000 === 0 ? 0 : 1)}M`;
  if (v >= 1_000) return `€${Math.round(v / 1_000)}K`;
  return `€${v}`;
}

export function ordinal(n: number): string {
  const r = Math.round(n);
  const s = r % 100 >= 11 && r % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[r % 10] ?? "th";
  return `${r}${s}`;
}

export function metricValue(v: number | null, unit: string): string {
  if (v === null) return "n/a";
  return unit === "%" ? `${v.toFixed(1)}%` : v.toFixed(2);
}

export function pctTone(p: number | null): string {
  if (p === null) return "bg-slate-600";
  if (p >= 80) return "bg-emerald-400";
  if (p >= 60) return "bg-emerald-500/80";
  if (p >= 40) return "bg-teal-600/70";
  return "bg-slate-500";
}

export const POSITION_SHORT: Record<string, string> = {
  "Center Defensive Midfield": "CDM",
  "Left Defensive Midfield": "LDM",
  "Right Defensive Midfield": "RDM",
  "Center Midfield": "CM",
  "Left Center Midfield": "LCM",
  "Right Center Midfield": "RCM",
  "Center Attacking Midfield": "CAM",
  "Left Attacking Midfield": "LAM",
  "Right Attacking Midfield": "RAM",
  "Left Wing": "LW",
  "Right Wing": "RW",
  "Left Midfield": "LM",
  "Right Midfield": "RM",
  "Center Forward": "CF",
  "Left Center Forward": "LCF",
  "Right Center Forward": "RCF",
  "Secondary Striker": "SS",
};

export const COMPARE_COLORS = [
  { bar: "bg-emerald-400", dot: "bg-emerald-400", text: "text-emerald-300", ring: "ring-emerald-400" },
  { bar: "bg-sky-400", dot: "bg-sky-400", text: "text-sky-300", ring: "ring-sky-400" },
  { bar: "bg-amber-400", dot: "bg-amber-400", text: "text-amber-300", ring: "ring-amber-400" },
];
