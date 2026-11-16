import { Link } from "react-router-dom";
import PublicLayout from "../../components/PublicLayout";
import { TOOLS } from "../../lib/tools";

export default function ToolsIndex() {
  return (
    <PublicLayout title="Free DNS, Email Authentication and SSL Tools" description="Free tools to check SPF, DKIM, DMARC, MX, DNS health, DNS propagation and SSL certificates, plus SPF and DMARC record generators.">
      <section className="bg-navy-800 pb-14 pt-6">
        <div className="mx-auto max-w-6xl px-4 sm:px-8">
          <h1 className="max-w-3xl text-balance text-[32px] font-semibold leading-tight text-white sm:text-[40px]">Free tools for mail authentication, DNS and SSL</h1>
          <p className="mt-4 max-w-2xl text-[17px] text-navy-100/85">Check any domain in seconds. No sign-up, nothing stored, and every problem comes with the record to fix.</p>
        </div>
      </section>
      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-8">
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map((t) => (
            <li key={t.slug}>
              <Link to={`/tools/${t.slug}`} className="block h-full rounded-lg border border-line bg-surface p-5 transition hover:border-navy-300 hover:shadow-sm">
                <p className="font-display text-[17px] font-semibold text-heading">{t.name}</p>
                <p className="mt-2 text-sm text-muted">{t.lead}</p>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </PublicLayout>
  );
}
