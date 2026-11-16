import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import PublicLayout from "../../components/PublicLayout";
import { DmarcGenerator, SpfGenerator } from "../../components/tools/Generators";
import { DomainCheckWidget, PropagationWidget, SslWidget } from "../../components/tools/Widgets";
import { useAuth } from "../../lib/auth";
import { Tool, toolBySlug, TOOLS } from "../../lib/tools";
import NotFound from "../NotFound";

function Widget({ tool, onResult }: { tool: Tool; onResult: (d: string | null) => void }) {
  const k = tool.kind;
  if (k.type === "check") return <DomainCheckWidget check={k.check} onResult={onResult} />;
  if (k.type === "ssl") return <SslWidget onResult={onResult} />;
  if (k.type === "propagation") return <PropagationWidget onResult={onResult} />;
  if (k.type === "spf-generator") return <SpfGenerator />;
  return <DmarcGenerator />;
}

function Cta({ domain }: { domain: string | null }) {
  const { user } = useAuth();
  const target = user ? "/domains?add=1" : `/register?next=${encodeURIComponent("/domains?add=1")}`;
  return (
    <div className="rounded-lg bg-navy-800 px-6 py-6 text-white sm:flex sm:items-center sm:justify-between sm:gap-6">
      <div>
        <p className="font-display text-lg font-semibold">{domain ? `Keep watching ${domain}` : "Don't check by hand every week"}</p>
        <p className="mt-1 text-sm text-navy-100/85">
          DomainVitals checks SPF, DKIM, DMARC, DNS and SSL every day, reads your DMARC reports and alerts you by mail, Slack or Teams when something breaks.
        </p>
      </div>
      <Link to={target} className="mt-4 inline-block shrink-0 rounded-md bg-orange-500 px-5 py-2.5 text-sm font-semibold text-navy-950 hover:bg-orange-600 sm:mt-0">
        {user ? "Add to my workspace" : "Monitor free for 14 days"}
      </Link>
    </div>
  );
}

export default function ToolPage() {
  const { slug = "" } = useParams();
  const tool = toolBySlug(slug);
  const [checked, setChecked] = useState<string | null>(null);
  if (!tool) return <NotFound />;
  const related = TOOLS.filter((t) => t.slug !== tool.slug).slice(0, 6);

  return (
    <PublicLayout title={tool.title} description={tool.description}>
      <section className="bg-navy-800 pb-24 pt-4">
        <div className="mx-auto max-w-4xl px-4 sm:px-8">
          <nav aria-label="Breadcrumb" className="text-sm text-navy-100/70">
            <Link to="/tools" className="hover:text-white">Free tools</Link> <span aria-hidden="true">/</span> {tool.name}
          </nav>
          <h1 className="mt-3 text-balance text-[30px] font-semibold leading-tight text-white sm:text-[38px]">{tool.h1}</h1>
          <p className="mt-3 max-w-2xl text-[16px] text-navy-100/85">{tool.lead}</p>
        </div>
      </section>
      <div className="mx-auto -mt-16 max-w-4xl space-y-10 px-4 pb-16 sm:px-8">
        <div className="rounded-lg border border-line bg-surface p-5 shadow-sm sm:p-6">
          <Widget tool={tool} onResult={setChecked} />
        </div>
        <Cta domain={checked} />
        <section>
          <h2 className="text-xl font-semibold">About this tool</h2>
          <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-ink">{tool.about.map((p) => <p key={p}>{p}</p>)}</div>
        </section>
        <section>
          <h2 className="text-xl font-semibold">Questions</h2>
          <dl className="mt-3 divide-y divide-line rounded-lg border border-line">
            {tool.faq.map((f) => (
              <div key={f.q} className="px-5 py-4">
                <dt className="font-medium text-heading">{f.q}</dt>
                <dd className="mt-1.5 text-[15px] text-ink">{f.a}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section>
          <h2 className="text-xl font-semibold">More free tools</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((t) => (
              <li key={t.slug}><Link to={`/tools/${t.slug}`} className="block rounded-md border border-line px-4 py-3 text-sm font-medium text-heading hover:border-navy-300">{t.name}</Link></li>
            ))}
          </ul>
        </section>
      </div>
    </PublicLayout>
  );
}
