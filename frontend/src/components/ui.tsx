import {
  ButtonHTMLAttributes, cloneElement, InputHTMLAttributes, isValidElement, ReactElement, ReactNode,
  SelectHTMLAttributes, useId,
} from "react";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  busy?: boolean;
};

export function Button({ variant = "primary", busy, className, children, disabled, ...rest }: ButtonProps) {
  const styles = {
    primary: "bg-slate-900 text-white hover:bg-slate-700",
    secondary: "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50",
    danger: "border border-red-300 bg-white text-red-700 hover:bg-red-50",
    ghost: "text-slate-600 hover:bg-slate-100",
  }[variant];
  return (
    <button
      {...rest}
      disabled={disabled || busy}
      className={cx("inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium",
        "focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-60", styles, className)}
    >
      {busy ? "Please wait…" : children}
    </button>
  );
}

type FieldProps = { label: string; hint?: string; error?: string; children: ReactElement };
/** Label + control linked by id (label never wraps the control, so a select's
 *  options don't leak into its accessible name). */
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
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="mt-1">{control}</div>
      {hint && !error && <span id={`${id}-hint`} className="mt-1 block text-xs text-slate-500">{hint}</span>}
      {error && <span id={`${id}-err`} className="mt-1 block text-xs text-red-700">{error}</span>}
    </div>
  );
}

const inputCls = "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputCls, props.className)} />;
}

export function Alert({ tone = "error", children }: { tone?: "error" | "success" | "info" | "warning"; children: ReactNode }) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
  }[tone];
  return <div role={tone === "error" ? "alert" : "status"} className={cx("rounded-md border px-3 py-2 text-sm", styles)}>{children}</div>;
}

export function Card({ title, actions, children }: { title?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      {(title || actions) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <p className="py-10 text-center text-sm text-slate-500" role="status">{label}</p>;
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">{children}</span>;
}

export const cls = cx;
