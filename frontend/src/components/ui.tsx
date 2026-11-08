import {
  ButtonHTMLAttributes, cloneElement, InputHTMLAttributes, isValidElement, ReactElement, ReactNode,
  SelectHTMLAttributes, useId,
} from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export const cls = cx;

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "dark";
  size?: "sm" | "md";
  busy?: boolean;
};

export function Button({ variant = "primary", size = "md", busy, className, children, disabled, ...rest }: ButtonProps) {
  const styles = {
    // Orange fill with navy text keeps WCAG AA contrast (white on orange does not).
    primary: "bg-orange-500 text-navy-950 font-semibold hover:bg-orange-600",
    dark: "bg-navy-900 text-white font-semibold hover:bg-navy-800",
    secondary: "border border-line bg-white text-navy-900 font-medium hover:bg-canvas",
    danger: "border border-fail/30 bg-white text-fail font-medium hover:bg-fail-bg",
    ghost: "text-navy-700 font-medium hover:bg-navy-100",
  }[variant];
  const sizes = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm" }[size];
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={cx("inline-flex items-center justify-center gap-2 rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        styles, sizes, className)}
    >
      {busy && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" aria-hidden="true" />}
      {children}
    </button>
  );
}

type FieldProps = { label: string; hint?: string; error?: string; children: ReactElement };
/** Label + control linked by id (the label never wraps the control). */
export function Field({ label, hint, error, children }: FieldProps) {
  const id = useId();
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined;
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined,
      })
    : children;
  return (
    <div>
      <label htmlFor={id} className="block text-[13px] font-medium text-navy-900">{label}</label>
      <div className="mt-1.5">{control}</div>
      {hint && !error && <p id={`${id}-hint`} className="mt-1.5 text-xs text-muted">{hint}</p>}
      {error && <p id={`${id}-err`} className="mt-1.5 text-xs font-medium text-fail">{error}</p>}
    </div>
  );
}

const inputCls = "h-10 w-full rounded-md border border-line bg-white px-3 text-sm text-ink placeholder:text-muted/70 " +
  "focus:border-navy-700 focus:outline-none focus:ring-2 focus:ring-navy-100 disabled:bg-canvas disabled:text-muted aria-[invalid=true]:border-fail";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputCls, "pr-8", props.className)} />;
}

export function Alert({ tone = "error", children }: { tone?: "error" | "success" | "info" | "warning"; children: ReactNode }) {
  const styles = {
    error: "border-fail/25 bg-fail-bg text-fail",
    success: "border-pass/25 bg-pass-bg text-pass",
    info: "border-navy-700/20 bg-navy-100 text-navy-900",
    warning: "border-warn/25 bg-warn-bg text-warn",
  }[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={cx("rounded-md border px-3 py-2.5 text-sm", styles)}>
      {children}
    </div>
  );
}

export function Card({ title, description, actions, children, padded = true }: {
  title?: string; description?: string; actions?: ReactNode; children: ReactNode; padded?: boolean;
}) {
  return (
    <section className="rounded-lg border border-line bg-white">
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
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

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-semibold leading-tight">{title}</h1>
        {description && <p className="mt-1 text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="flex items-center justify-center gap-2 py-12 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-navy-700 border-r-transparent" aria-hidden="true" />
      {label}
    </p>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "pass" | "warn" | "fail" | "brand" }) {
  const styles = {
    neutral: "bg-navy-100 text-navy-900",
    pass: "bg-pass-bg text-pass",
    warn: "bg-warn-bg text-warn",
    fail: "bg-fail-bg text-fail",
    brand: "bg-orange-50 text-orange-700",
  }[tone];
  return <span className={cx("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium", styles)}>{children}</span>;
}

export const linkCls = "font-medium text-navy-700 underline decoration-navy-700/30 underline-offset-2 hover:decoration-navy-700";
