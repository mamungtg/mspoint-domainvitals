import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";
import { VitalsPanel, Vital } from "../components/Vitals";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

const SAMPLE: Vital[] = [
  { check: "SPF", status: "Pass", detail: "6 of 10 DNS lookups used", tone: "pass" },
  { check: "DKIM", status: "Pass", detail: "Keys found for google and selector1", tone: "pass" },
  { check: "DMARC", status: "Warning", detail: "Policy is p=none, so spoofed mail is still delivered", tone: "warn" },
  { check: "MX", status: "Pass", detail: "2 mail servers answer on port 25", tone: "pass" },
  { check: "TLS", status: "Action needed", detail: "Certificate expires in 6 days", tone: "fail" },
];

const CHECKS = [
  { name: "SPF", what: "One record, under the 10-lookup limit, ending in a sensible all mechanism." },
  { name: "DKIM", what: "Published keys for the selectors your mail services use, with sane key lengths." },
  { name: "DMARC", what: "A valid policy, where reports go, and how far you are from enforcement." },
  { name: "MX", what: "Mail servers that exist, resolve and accept connections." },
  { name: "SSL/TLS", what: "Certificate validity, hostname match, chain and days until expiry." },
];

const FOR_TEAMS = [
  { title: "One workspace per team", body: "Keep every client domain in one place, and give colleagues owner, admin, member or read-only access." },
  { title: "Checks run on their own", body: "Domains are scanned on a schedule and the history is kept, so you can see when something changed." },
  { title: "Findings you can act on", body: "Each problem comes with what is wrong, why it matters and the record to change." },
];

export default function Home() {
  const { user } = useAuth();
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  useEffect(() => { api<{ status: string }>("/health/").then((h) => setApiUp(h.status === "ok")).catch(() => setApiUp(false)); }, []);

  return (
    <div className="min-h-screen bg-white">
      <div className="bg-navy-900">
        <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-8">
          <Link to="/" aria-label="DomainVitals home"><Logo inverse /></Link>
          <nav className="flex shrink-0 items-center gap-2 whitespace-nowrap">
            {user ? (
              <Link to="/dashboard" className="rounded-md bg-orange-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-orange-600">Open dashboard</Link>
            ) : (
              <>
                <Link to="/login" className="hidden rounded-md px-3 py-2 text-sm font-medium text-white hover:bg-white/10 sm:inline-block">Sign in</Link>
                <Link to="/register" className="rounded-md bg-orange-500 px-4 py-2 text-sm font-semibold text-navy-950 hover:bg-orange-600">Create account</Link>
              </>
            )}
          </nav>
        </header>

        <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-10 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)] lg:pb-28 lg:pt-16">
          <div className="max-w-xl">
            <h1 className="text-balance text-[34px] font-semibold leading-[1.15] text-white sm:text-[44px]">
              Find the client domains that are about to break mail, before your clients do.
            </h1>
            <p className="mt-6 text-[17px] leading-relaxed text-navy-100/85">
              DomainVitals checks SPF, DKIM, DMARC, MX and SSL/TLS for every domain you manage,
              keeps the history, and tells you exactly which record to fix.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={user ? "/dashboard" : "/register"} className="rounded-md bg-orange-500 px-5 py-3 font-semibold text-navy-950 hover:bg-orange-600">
                {user ? "Open dashboard" : "Start monitoring"}
              </Link>
              {!user && <Link to="/login" className="rounded-md border border-white/20 px-5 py-3 font-medium text-white hover:bg-white/10">Sign in</Link>}
            </div>
          </div>
          <VitalsPanel domain="harbourdental.co.uk" checkedAt="Checked 4 minutes ago" vitals={SAMPLE} />
        </section>
      </div>

      <section className="mx-auto max-w-6xl px-4 py-20 sm:px-8">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
          <div>
            <h2 className="text-[26px] font-semibold leading-tight">What each scan looks at</h2>
            <p className="mt-3 text-muted">The same checks a careful engineer would run by hand, on every domain, every day.</p>
          </div>
          <dl className="divide-y divide-line border-y border-line">
            {CHECKS.map((c) => (
              <div key={c.name} className="grid gap-1 py-5 sm:grid-cols-[8rem_1fr] sm:gap-6">
                <dt className="font-display font-semibold text-navy-900">{c.name}</dt>
                <dd className="text-muted">{c.what}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section className="border-t border-line bg-canvas">
        <div className="mx-auto max-w-6xl px-4 py-20 sm:px-8">
          <h2 className="max-w-xl text-balance text-[26px] font-semibold leading-tight">Made for agencies and IT providers who look after many domains</h2>
          <div className="mt-10 grid gap-10 md:grid-cols-3">
            {FOR_TEAMS.map((f) => (
              <div key={f.title} className="border-t-2 border-orange-500 pt-5">
                <h3 className="text-[17px] font-semibold">{f.title}</h3>
                <p className="mt-2 text-muted">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="bg-navy-950 text-navy-100/70">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm sm:px-8">
          <span>© {new Date().getFullYear()} MSPoint LLC</span>
          <span className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${apiUp === null ? "bg-navy-100/40" : apiUp ? "bg-[#3fbf86]" : "bg-[#ff6b5e]"}`} aria-hidden="true" />
            {apiUp === null ? "Checking service status" : apiUp ? "All systems operational" : "Service unavailable"}
          </span>
          <a href="mailto:support@mspointit.com" className="hover:text-white">support@mspointit.com</a>
        </div>
      </footer>
    </div>
  );
}
