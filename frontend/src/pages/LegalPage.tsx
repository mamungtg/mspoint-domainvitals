import { Fragment, ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import PublicLayout from "../components/PublicLayout";
import { Block, LEGAL, LEGAL_UPDATED, legalDoc } from "../lib/legal";
import NotFound from "./NotFound";

const LINK = /([\w.+-]+@mspointit\.com|\/legal\/[a-z]+)/g;
const a = "font-medium text-link underline decoration-link/30 underline-offset-2 hover:decoration-link";

/** Turns mailto addresses and /legal/ paths in the text into links. */
function rich(text: string): ReactNode {
  return text.split(LINK).map((part, i) =>
    i % 2 === 0 ? <Fragment key={i}>{part}</Fragment>
      : part.startsWith("/") ? <Link key={i} className={a} to={part}>{part.replace("/legal/", "")}</Link>
        : <a key={i} className={a} href={`mailto:${part}`}>{part}</a>);
}

function BlockView({ b }: { b: Block }) {
  if (typeof b === "string") return <p>{rich(b)}</p>;
  if ("ul" in b) return <ul className="list-disc space-y-2 pl-5">{b.ul.map((li) => <li key={li}>{rich(li)}</li>)}</ul>;
  const [head, ...rows] = b.table;
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[560px] text-left text-sm">
        <thead className="bg-subtle text-heading"><tr>{head.map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => <tr key={r[0]} className="align-top">{r.map((c, i) => <td key={i} className={`px-3 py-2 ${i === 0 ? "font-medium text-heading" : ""}`}>{rich(c)}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

export default function LegalPage() {
  const { slug } = useParams();
  const doc = legalDoc(slug);
  if (!doc) return <NotFound />;
  return (
    <PublicLayout title={doc.title} description={doc.description}>
      <section className="bg-navy-800 pb-12 pt-6">
        <div className="mx-auto max-w-6xl px-4 sm:px-8">
          <h1 className="text-[32px] font-semibold leading-tight text-white sm:text-[40px]">{doc.name}</h1>
          <p className="mt-3 text-navy-100/85">Last updated {LEGAL_UPDATED}</p>
        </div>
      </section>
      <div className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-10 px-4 py-12 sm:px-8 lg:grid-cols-[200px_minmax(0,1fr)]">
        <nav aria-label="Legal documents" className="text-sm lg:sticky lg:top-6 lg:self-start">
          <ul className="flex flex-wrap gap-x-4 gap-y-2 lg:flex-col">
            {LEGAL.map((d) => (
              <li key={d.slug}>
                <Link to={`/legal/${d.slug}`} aria-current={d.slug === doc.slug ? "page" : undefined}
                  className={d.slug === doc.slug ? "font-semibold text-heading" : "text-muted hover:text-heading hover:underline"}>{d.name}</Link>
              </li>
            ))}
          </ul>
        </nav>
        <article className="min-w-0 max-w-3xl space-y-4 leading-relaxed text-ink">
          {doc.intro.map((p) => <p key={p}>{rich(p)}</p>)}
          {doc.sections.map((s) => (
            <section key={s.h} className="space-y-3 pt-4">
              <h2 className="font-display text-[20px] font-semibold text-heading">{s.h}</h2>
              {s.body.map((b, i) => <BlockView key={i} b={b} />)}
            </section>
          ))}
        </article>
      </div>
    </PublicLayout>
  );
}
