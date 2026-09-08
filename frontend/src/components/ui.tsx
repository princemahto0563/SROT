import type { ReactNode } from "react";
import { AlertTriangle, Info, ShieldCheck } from "lucide-react";

/* ── Panel ────────────────────────────────────────────────────────────────── */
export function Panel({
  title, hint, right, children, className = "", pad = true,
}: { title?: string; hint?: string; right?: ReactNode; children: ReactNode; className?: string; pad?: boolean }) {
  return (
    <section className={`panel shadow-panel ${className}`}>
      {(title || right) && (
        <header className={`flex items-start justify-between gap-4 border-b border-lineSoft ${pad ? "px-5 py-3.5" : "px-4 py-3"}`}>
          <div>
            {title && <h2 className="lbl font-bold">{title}</h2>}
            {hint && <p className="mt-0.5 text-[11px] leading-relaxed text-muted max-w-[70ch]">{hint}</p>}
          </div>
          {right}
        </header>
      )}
      <div className={pad ? "p-5" : "p-4"}>{children}</div>
    </section>
  );
}

/* ── Chip / badge ─────────────────────────────────────────────────────────── */
type Tone = "accent" | "amber" | "danger" | "ok" | "muted" | "violet";
const toneMap: Record<Tone, string> = {
  accent: "text-accent border-accent/40 bg-accent/10 font-semibold",
  amber:  "text-amber border-amber/40 bg-amber/10 font-semibold",
  danger: "text-danger border-danger/40 bg-danger/10 font-semibold",
  ok:     "text-ok border-ok/40 bg-ok/10 font-semibold",
  muted:  "text-ink2 border-line bg-s2",
  violet: "text-violet border-violet/40 bg-violet/10 font-semibold",
};
export function Chip({ tone = "muted", children, dot = true, title, className = "" }: { tone?: Tone; children: ReactNode; dot?: boolean; title?: string; className?: string }) {
  return (
    <span title={title} className={`chip ${toneMap[tone]} ${className}`}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

/* ── Stat tile ────────────────────────────────────────────────────────────── */
export function Stat({ label, value, sub, tone = "ink" }: { label: string; value: string; sub?: string; tone?: "ink" | "danger" | "amber" | "ok" | "accent" }) {
  const c = tone === "danger" ? "text-danger" : tone === "amber" ? "text-amber" : tone === "ok" ? "text-ok" : tone === "accent" ? "text-accent" : "text-ink";
  return (
    <div className="panel shadow-panel px-4 py-3.5">
      <div className="lbl text-[9.5px]">{label}</div>
      <div className={`mt-1.5 text-[26px] font-bold tracking-tight leading-none tabular-nums ${c}`}>{value}</div>
      {sub && <div className="mt-1.5 text-[11px] text-muted">{sub}</div>}
    </div>
  );
}

/* ── Notices ──────────────────────────────────────────────────────────────── */
export function Notice({
  kind = "info", children,
}: { kind?: "info" | "warn" | "safe"; children: ReactNode }) {
  const cfg = {
    info: { c: "text-ink2 border-line bg-s2/70", I: Info },
    warn: { c: "text-amber border-amber/35 bg-amber/[0.08]", I: AlertTriangle },
    safe: { c: "text-ok border-ok/35 bg-ok/[0.08]", I: ShieldCheck },
  }[kind];
  const I = cfg.I;
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-[11.5px] leading-relaxed ${cfg.c}`}>
      <I size={14} className="mt-[2px] shrink-0" />
      <span>{children}</span>
    </div>
  );
}

/* ── Signal / meter bar ───────────────────────────────────────────────────── */
export function Meter({ value, tone = "accent" }: { value: number; tone?: Tone }) {
  const bar = { accent: "bg-accent", amber: "bg-amber", danger: "bg-danger", ok: "bg-ok", muted: "bg-muted", violet: "bg-violet" }[tone];
  return (
    <div className="h-[6px] w-full overflow-hidden rounded-full bg-s3">
      <div className={`bar-grow h-full rounded-full ${bar}`} style={{ width: `${Math.max(value, 2)}%` }} />
    </div>
  );
}

/* ── Section heading ──────────────────────────────────────────────────────── */
export function PageHead({
  eyebrow, title, sub, right,
}: { eyebrow: string; title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4 border-b border-line/60 pb-4">
      <div>
        <div className="lbl text-accent font-semibold">{eyebrow}</div>
        <h1 className="mt-1 text-[21px] font-bold tracking-tight text-ink">{title}</h1>
        {sub && <p className="mt-1 max-w-[84ch] text-[12px] leading-relaxed text-ink2">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Mono({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`font-mono text-[11px] tracking-tight ${className}`}>{children}</span>;
}

/* ── Async states ─────────────────────────────────────────────────────────── */
export function Skeleton({ h = 14, w = "100%", className = "" }: { h?: number; w?: string; className?: string }) {
  return <div className={`skeleton rounded ${className}`} style={{ height: h, width: w }} />;
}

export function LoadingPanel({ rows = 4, label }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-2.5 p-5 panel" role="status" aria-busy="true">
      {label && <div className="text-[11px] font-medium text-muted">{label}</div>}
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} h={i === 0 ? 18 : 12} w={i === 0 ? "38%" : `${94 - i * 8}%`} />
      ))}
    </div>
  );
}

export function EmptyState({
  title, detail, action,
}: { title: string; detail?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2.5 rounded-xl border border-line bg-surface p-6 shadow-sm">
      <div className="text-[13px] font-bold text-ink">{title}</div>
      {detail && <p className="max-w-[76ch] text-[11.5px] leading-relaxed text-muted">{detail}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rounded-xl border border-danger/35 bg-danger/[0.08] p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle size={15} className="mt-[2px] shrink-0 text-danger" />
        <div className="min-w-0">
          <div className="text-[13px] font-bold text-danger">Could not load this view</div>
          <p className="mt-1 break-words text-[11.5px] leading-relaxed text-ink2">{message}</p>
          {onRetry && (
            <button onClick={onRetry} className="btn btn-ghost mt-3 text-[11px]">Try again</button>
          )}
        </div>
      </div>
    </div>
  );
}

/** One wrapper for every remote view: loading, error and empty handled once. */
export function Async<T>({
  state, empty, children, rows = 4,
}: {
  state: { data: T | null; error: string | null; loading: boolean; reload: () => void };
  empty?: ReactNode;
  children: (data: T) => ReactNode;
  rows?: number;
}) {
  if (state.loading && !state.data) return <LoadingPanel rows={rows} />;
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (!state.data) return <>{empty ?? <EmptyState title="No data available yet." />}</>;
  return <>{children(state.data)}</>;
}

/* ── Table ────────────────────────────────────────────────────────────────── */
export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full border-collapse text-[11.5px]">
        <thead>
          <tr className="border-b border-line bg-s2/40">
            {head.map((h, i) => (
              <th key={i} className="whitespace-nowrap px-3 py-2 text-left text-[9.5px] font-semibold uppercase tracking-[0.09em] text-muted">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-lineSoft">{children}</tbody>
      </table>
    </div>
  );
}

export function Row({ children, tone = "" }: { children: ReactNode; tone?: string }) {
  return <tr className={`border-b border-lineSoft last:border-0 hover:bg-s2/40 transition-colors ${tone}`}>{children}</tr>;
}

export function Cell({ children, className = "", mono = false }: { children?: ReactNode; className?: string; mono?: boolean }) {
  return (
    <td className={`px-3 py-2 align-middle text-ink2 ${mono ? "font-mono text-[11px]" : ""} ${className}`}>
      {children ?? "—"}
    </td>
  );
}

/* ── Key/value field ──────────────────────────────────────────────────────── */
export function Field({ label, children, mono = false }: { label: string; children?: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <div className="lbl text-[9.5px]">{label}</div>
      <div className={`mt-0.5 break-words text-[12px] text-ink font-medium ${mono ? "font-mono text-[11px]" : ""}`}>
        {children ?? <span className="text-muted font-normal">Not available</span>}
      </div>
    </div>
  );
}

/* ── Button ───────────────────────────────────────────────────────────────── */
export function Button({
  children, onClick, disabled, tone = "primary", type = "button", className = "", title,
}: {
  children: ReactNode; onClick?: () => void; disabled?: boolean;
  tone?: "primary" | "ghost"; type?: "button" | "submit"; className?: string; title?: string;
}) {
  return (
    <button
      type={type} onClick={onClick} disabled={disabled} title={title}
      className={`btn ${tone === "primary" ? "btn-primary" : "btn-ghost"} ${className}`}
    >
      {children}
    </button>
  );
}
