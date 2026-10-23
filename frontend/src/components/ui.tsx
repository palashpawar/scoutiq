import type { ReactNode } from "react";

export function Badge({ children, tone = "slate", title }: { children: ReactNode; tone?: "slate" | "emerald" | "amber" | "sky" | "rose"; title?: string }) {
  const tones = {
    slate: "border-navy-600 bg-navy-800 text-slate-300",
    emerald: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    amber: "border-amber-500/40 bg-amber-500/10 text-amber-200",
    sky: "border-sky-500/40 bg-sky-500/10 text-sky-200",
    rose: "border-rose-500/40 bg-rose-500/10 text-rose-200",
  };
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M22 12a10 10 0 0 0-10-10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Notice({ tone, children }: { tone: "warn" | "error" | "info"; children: ReactNode }) {
  const styles = {
    warn: "border-amber-500/30 bg-amber-500/10 text-amber-100",
    error: "border-rose-500/40 bg-rose-500/10 text-rose-100",
    info: "border-sky-500/30 bg-sky-500/10 text-sky-100",
  };
  return <div role={tone === "error" ? "alert" : "status"} className={`rounded-lg border px-3 py-2 text-sm ${styles[tone]}`}>{children}</div>;
}

export function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="8" fill="#10b981" fillOpacity="0.15" />
        <circle cx="16" cy="16" r="9" fill="none" stroke="#34d399" strokeWidth="2" />
        <path d="M16 7v18M7 16h18" stroke="#34d399" strokeWidth="1.5" strokeOpacity="0.6" />
        <circle cx="16" cy="16" r="3" fill="#34d399" />
      </svg>
      <span className="text-lg font-semibold tracking-tight text-white">
        Scout<span className="text-emerald-400">IQ</span>
      </span>
    </div>
  );
}
