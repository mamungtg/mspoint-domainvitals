import { ReactNode, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { LEGAL } from "../lib/legal";
import { TOOLS } from "../lib/tools";
import { Logo } from "./Logo";

/** Light, public shell for the free tools (outside the signed-in app). */
export default function PublicLayout({ children, title, description }: { children: ReactNode; title: string; description: string }) {
  const { user } = useAuth();
  useEffect(() => {
    document.title = title.includes("DomainVitals") ? title : `${title} | DomainVitals`;
    document.querySelector('meta[name="description"]')?.setAttribute("content", description);
  }, [title, description]);

  return (
    <div className="flex min-h-screen flex-col bg-white text-ink" data-theme="light">
      <header className="bg-navy-800">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-8">
          <Link to="/" aria-label="DomainVitals home"><Logo inverse /></Link>
          <nav className="flex shrink-0 items-center gap-1 whitespace-nowrap text-sm">
            <Link to="/tools" className="hidden rounded-md px-3 py-2 font-medium text-white hover:bg-white/10 sm:inline-block">Free tools</Link>
            {user ? (
              <Link to="/dashboard" className="rounded-md bg-orange-500 px-4 py-2 font-semibold text-navy-950 hover:bg-orange-600">Open dashboard</Link>
            ) : (
              <>
                <Link to="/login" className="hidden rounded-md px-3 py-2 font-medium text-white hover:bg-white/10 sm:inline-block">Sign in</Link>
                <Link to="/register" className="rounded-md bg-orange-500 px-4 py-2 font-semibold text-navy-950 hover:bg-orange-600">Start free</Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-line bg-subtle">
        <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 text-sm sm:px-8 md:grid-cols-[1fr_2fr]">
          <div>
            <Logo />
            <p className="mt-3 max-w-xs text-muted">Domain, mail authentication and certificate monitoring for agencies, MSPs and IT teams.</p>
          </div>
          <div>
            <p className="mb-3 font-semibold text-heading">Free tools</p>
            <ul className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
              {TOOLS.map((t) => <li key={t.slug}><Link className="text-muted hover:text-heading hover:underline" to={`/tools/${t.slug}`}>{t.name}</Link></li>)}
            </ul>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2 border-t border-line px-4 py-4 text-xs text-muted">
          <span>© {new Date().getFullYear()} MSPoint LLC · DomainVitals</span>
          {LEGAL.map((d) => <Link key={d.slug} to={`/legal/${d.slug}`} className="hover:text-heading hover:underline">{d.name}</Link>)}
          <a href="mailto:support@mspointit.com" className="hover:text-heading hover:underline">support@mspointit.com</a>
        </div>
      </footer>
    </div>
  );
}
