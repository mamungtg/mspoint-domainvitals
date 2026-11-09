import {
  ButtonHTMLAttributes, cloneElement, InputHTMLAttributes, isValidElement, ReactElement, ReactNode,
  SelectHTMLAttributes, useEffect, useId, useRef, useState,
} from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export const cls = cx;
export const linkCls = "font-medium text-link underline decoration-link/30 underline-offset-2 hover:decoration-link";

/* ---------- Buttons ---------- */
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "dark";
  size?: "sm" | "md";
  busy?: boolean;
};
export function Button({ variant = "primary", size = "md", busy, className, children, disabled, ...rest }: ButtonProps) {
  const styles = {
    // Amber fill with deep navy text keeps WCAG AA contrast.
    primary: "bg-orange-500 text-navy-950 font-semibold hover:bg-orange-600",
    dark: "bg-navy-700 text-white font-semibold hover:bg-navy-800",
    secondary: "border border-line bg-surface text-heading font-medium hover:bg-subtle",
    danger: "border border-fail/40 bg-surface text-fail font-medium hover:bg-fail-bg",
    ghost: "text-link font-medium hover:bg-subtle",
  }[variant];
  const sizes = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm" }[size];
  return (
    <button {...rest} disabled={disabled || busy} aria-busy={busy || undefined}
      className={cx("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-55",
        styles, sizes, className)}>
      {busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" />}
      {children}
    </button>
  );
}

/* ---------- Forms ---------- */
type FieldProps = { label: string; hint?: string; error?: string; children: ReactElement };
/** Label + control linked by id (the label never wraps the control). */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined;
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, { id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined })
    : children;
  return (
    <div>
      <label htmlFor={id} className="block text-[13px] font-medium text-heading">{label}</label>
      <div className="mt-1.5">{control}</div>
      {hint && !error && <p id={`${id}-hint`} className="mt-1.5 text-xs text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} className="mt-1.5 text-xs font-medium text-fail">{error}</p>}
    </div>
  );
}
const inputCls = "h-10 w-full rounded-md border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted/70 " +
  "focus:border-navy-700 focus:outline-none focus:ring-2 focus:ring-navy-700/20 disabled:bg-subtle disabled:text-muted aria-[invalid=true]:border-fail";
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputCls, "pr-8", props.className)} />;
}

/* ---------- Feedback ---------- */
export function Alert({ tone = "error", children }: { tone?: "error" | "success" | "info" | "warning"; children: ReactNode }) {
  const styles = {
    error: "border-fail/30 bg-fail-bg text-fail",
    success: "border-pass/30 bg-pass-bg text-pass",
    info: "border-line bg-subtle text-heading",
    warning: "border-warn/30 bg-warn-bg text-warn",
  }[tone];
  return <div role={tone === "error" ? "alert" : "status"} className={cx("rounded-md border px-3 py-2.5 text-sm", styles)}>{children}</div>;
}
export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="flex items-center justify-center gap-2 py-12 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-link border-r-transparent" aria-hidden="true" />{label}
    </p>
  );
}

/* ---------- Layout ---------- */
export function Card({ title, description, actions, children, padded = true, className }: {
  title?: ReactNode; description?: ReactNode; actions?: ReactNode; children: ReactNode; padded?: boolean; className?: string;
}) {
  return (
    <section className={cx("min-w-0 rounded-lg border border-line bg-surface", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold">{title}</h2>}
            {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
export function PageHeader({ title, description, actions, eyebrow }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow}
        <h1 className="break-words text-[26px] font-semibold leading-tight">{title}</h1>
        {description && <p className="mt-1 text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
export function EmptyState({ title, body, action, icon }: { title: string; body: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      {icon && <div className="mb-4 text-link">{icon}</div>}
      <h3 className="text-[17px] font-semibold">{title}</h3>
      <p className="mt-2 max-w-md text-muted">{body}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

/* ---------- Status ---------- */
export type Health = "pass" | "warn" | "fail" | "error" | "none";
const HEALTH: Record<Health, { label: string; cls: string; icon: string }> = {
  pass: { label: "Pass", cls: "bg-pass-bg text-pass", icon: "M5 10.5l3.2 3L15 7" },
  warn: { label: "Warning", cls: "bg-warn-bg text-warn", icon: "M10 5.5v5.5M10 14.2v.1" },
  fail: { label: "Fail", cls: "bg-fail-bg text-fail", icon: "M6.5 6.5l7 7M13.5 6.5l-7 7" },
  error: { label: "Lookup failed", cls: "bg-subtle text-muted", icon: "M6 10h8" },
  none: { label: "Not checked", cls: "bg-subtle text-muted", icon: "M6 10h8" },
};
export const healthLabel = (h: Health) => HEALTH[h].label;
export function StatusIcon({ status, size = 20 }: { status: Health; size?: number }) {
  const h = HEALTH[status] ?? HEALTH.none;
  return (
    <span className={cx("inline-flex shrink-0 items-center justify-center rounded-full", h.cls)} style={{ width: size, height: size }}>
      <svg viewBox="0 0 20 20" width={size * 0.75} height={size * 0.75} aria-hidden="true">
        <path d={h.icon} fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}
export function StatusPill({ status, label }: { status: Health; label?: string }) {
  const h = HEALTH[status] ?? HEALTH.none;
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full py-0.5 pl-1 pr-2.5 text-xs font-semibold", h.cls)}>
      <StatusIcon status={status} size={16} />{label ?? h.label}
    </span>
  );
}
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "pass" | "warn" | "fail" | "brand" }) {
  const styles = { neutral: "bg-subtle text-heading", pass: "bg-pass-bg text-pass", warn: "bg-warn-bg text-warn", fail: "bg-fail-bg text-fail",
    brand: "bg-orange-500/15 text-accent" }[tone];
  return <span className={cx("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium", styles)}>{children}</span>;
}
export const scoreTone = (s: number | null | undefined): Health => s == null ? "none" : s >= 90 ? "pass" : s >= 60 ? "warn" : "fail";
export function ScoreRing({ score, size = 88, label = "Health score" }: { score: number | null | undefined; size?: number; label?: string }) {
  const r = 42, c = 2 * Math.PI * r, pct = score == null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const tone = { pass: "text-pass", warn: "text-warn", fail: "text-fail", error: "text-muted", none: "text-muted" }[scoreTone(score)];
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={`${label}: ${score ?? "not available"}`}>
      <svg viewBox="0 0 100 100" className="-rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="currentColor" strokeWidth="9" className="text-line" />
        <circle cx="50" cy="50" r={r} fill="none" stroke="currentColor" strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`} className={tone} />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-display font-semibold text-heading" style={{ fontSize: size * 0.28 }}>
        {score ?? "–"}
      </span>
    </div>
  );
}
export function ScoreBar({ score }: { score: number | null | undefined }) {
  const tone = { pass: "bg-pass", warn: "bg-warn", fail: "bg-fail", error: "bg-muted", none: "bg-muted" }[scoreTone(score)];
  return (
    <div className="flex items-center gap-2">
      <span className="w-7 text-right font-display text-sm font-semibold text-heading tabular-nums">{score ?? "–"}</span>
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
        <span className={cx("block h-full rounded-full", tone)} style={{ width: `${score ?? 0}%` }} />
      </span>
    </div>
  );
}

/* ---------- Data display ---------- */
export function KpiTile({ label, value, sub, tone = "neutral" }: {
  label: string; value: ReactNode; sub?: ReactNode; tone?: "neutral" | "pass" | "warn" | "fail";
}) {
  const accent = { neutral: "before:bg-navy-700", pass: "before:bg-pass", warn: "before:bg-warn", fail: "before:bg-fail" }[tone];
  return (
    <div className={cx("relative overflow-hidden rounded-lg border border-line bg-surface px-5 py-4 before:absolute before:inset-y-0 before:left-0 before:w-1", accent)}>
      <p className="text-[13px] font-medium text-muted">{label}</p>
      <p className="mt-1 font-display text-[28px] font-semibold leading-tight text-heading tabular-nums">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  );
}
export function CopyField({ label, value }: { label?: string; value: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };
  return (
    <div>
      {label && <p className="mb-1 text-xs font-medium text-muted">{label}</p>}
      <div className="flex items-stretch overflow-hidden rounded-md border border-line bg-subtle">
        <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap px-3 py-2 font-mono text-[13px] text-ink">{value}</code>
        <button onClick={copy} className="shrink-0 border-l border-line px-3 text-xs font-semibold text-link hover:bg-surface" aria-label={`Copy ${label ?? "value"}`}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: string; count?: number }[] }) {
  return (
    <div role="tablist" className="no-scrollbar flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line">
      {items.map((t) => (
        <button key={t.id} role="tab" aria-selected={value === t.id} onClick={() => onChange(t.id)}
          className={cx("relative whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors",
            value === t.id ? "text-heading after:absolute after:inset-x-2 after:bottom-[-1px] after:h-0.5 after:rounded-full after:bg-orange-500" : "text-muted hover:text-heading")}>
          {t.label}{t.count !== undefined && <span className="ml-1.5 rounded bg-subtle px-1.5 text-xs text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

/* ---------- Modal ---------- */
export function Modal({ open, onClose, title, children, footer }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center p-4 sm:items-center" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-navy-950/55" onClick={onClose} />
      <div ref={ref} className="relative w-full max-w-lg rounded-lg border border-line bg-surface shadow-2xl">
        <div className="border-b border-line px-5 py-4"><h2 className="text-[17px] font-semibold">{title}</h2></div>
        <div className="px-5 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------- Time ---------- */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "Never";
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "Just now";
  const m = Math.round(s / 60); if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60); if (h < 24) return `${h} h ago`;
  const d = Math.round(h / 24); if (d < 30) return `${d} day${d === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString();
}
