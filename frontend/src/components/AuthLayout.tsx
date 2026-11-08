import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "./Logo";

const POINTS = [
  "SPF, DKIM, DMARC and MX checked on a schedule",
  "SSL/TLS certificate expiry tracked before it bites",
  "Every client domain in one workspace, with roles for your team",
];

export default function AuthLayout({ title, subtitle, children, footer }: {
  title: string; subtitle?: string; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden overflow-hidden bg-navy-900 px-12 py-10 text-white lg:flex lg:flex-col">
        <Link to="/" aria-label="DomainVitals home"><Logo inverse /></Link>
        <div className="my-auto max-w-md">
          <p className="font-display text-[30px] font-semibold leading-snug text-white">
            Domain health for the agencies and IT teams who keep mail flowing.
          </p>
          <ul className="mt-8 space-y-4">
            {POINTS.map((p) => (
              <li key={p} className="flex gap-3 text-navy-100">
                <svg viewBox="0 0 20 20" className="mt-0.5 h-5 w-5 shrink-0 text-orange-500" aria-hidden="true">
                  <path d="m5 10.5 3.2 3L15 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-navy-100/60">© {new Date().getFullYear()} MSPoint LLC</p>
        <svg className="pointer-events-none absolute -right-24 bottom-24 h-64 w-[36rem] text-orange-500/15" viewBox="0 0 560 120" aria-hidden="true">
          <path d="M0 60h170l26-44 38 96 30-70 22 18h274" fill="none" stroke="currentColor" strokeWidth="6" strokeLinejoin="round" strokeLinecap="round" />
        </svg>
      </aside>

      <main className="flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-[400px]">
          <Link to="/" className="mb-10 inline-block lg:hidden" aria-label="DomainVitals home"><Logo /></Link>
          <h1 className="text-[26px] font-semibold leading-tight">{title}</h1>
          {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-8 border-t border-line pt-6 text-sm text-muted">{footer}</div>}
        </div>
      </main>
    </div>
  );
}
