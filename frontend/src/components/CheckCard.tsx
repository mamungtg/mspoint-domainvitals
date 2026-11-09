import { CHECK_LABEL, CHECK_LONG, CheckName, CheckResult, Finding } from "../lib/api";
import { Badge, CopyField, StatusIcon, StatusPill } from "./ui";

const SEV: Record<Finding["severity"], { tone: "fail" | "warn" | "neutral"; label: string }> = {
  critical: { tone: "fail", label: "Critical" }, warning: { tone: "warn", label: "Warning" }, info: { tone: "neutral", label: "Note" },
};

function FindingItem({ f }: { f: Finding }) {
  return (
    <li className="py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={SEV[f.severity].tone}>{SEV[f.severity].label}</Badge>
        <p className="font-medium text-heading">{f.title}</p>
      </div>
      <p className="mt-1 text-sm text-muted">{f.detail}</p>
      {f.fix && <p className="mt-1.5 text-sm text-ink"><span className="font-medium">How to fix: </span>{f.fix}</p>}
    </li>
  );
}

function Details({ r }: { r: CheckResult }) {
  const d = r.data as Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  if (r.check === "spf" && typeof d.lookups === "number") {
    const pct = Math.min(100, (d.lookups / d.lookup_limit) * 100);
    const tone = d.lookups > d.lookup_limit ? "bg-fail" : d.lookups >= d.lookup_limit - 1 ? "bg-warn" : "bg-pass";
    return (
      <div>
        <div className="flex justify-between text-xs text-muted"><span>DNS lookups</span><span className="font-semibold text-heading">{d.lookups} of {d.lookup_limit}</span></div>
        <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-subtle"><div className={`h-full ${tone}`} style={{ width: `${pct}%` }} /></div>
        {d.includes?.length > 0 && <p className="mt-2 text-xs text-muted">Includes: {d.includes.join(", ")}</p>}
      </div>
    );
  }
  if (r.check === "dmarc" && d.policy !== undefined) {
    const items: [string, string][] = [["Policy", d.policy ?? "missing"], ["Subdomains", d.subdomain_policy ?? "same as policy"],
      ["Applies to", `${d.pct ?? 100}% of mail`], ["Reports to", d.rua?.length ? d.rua.join(", ").replace(/mailto:/g, "") : "nobody"]];
    return (
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        {items.map(([k, v]) => <div key={k} className="min-w-0"><dt className="text-xs text-muted">{k}</dt><dd className="truncate font-medium text-heading">{v}</dd></div>)}
      </dl>
    );
  }
  if (r.check === "dkim" && Array.isArray(d.selectors)) {
    return d.selectors.length ? (
      <ul className="divide-y divide-line rounded-md border border-line text-sm">
        {d.selectors.map((s: { selector: string; bits: number | null; key_type: string; revoked: boolean }) => (
          <li key={s.selector} className="flex items-center justify-between gap-3 px-3 py-2">
            <code className="font-mono text-[13px] text-heading">{s.selector}._domainkey</code>
            <span className="text-xs text-muted">{s.revoked ? "Revoked" : `${s.key_type.toUpperCase()} ${s.bits ?? "?"}-bit`}</span>
          </li>
        ))}
      </ul>
    ) : <p className="text-xs text-muted">Selectors checked: {(d.selectors_checked ?? []).join(", ")}</p>;
  }
  if (r.check === "mx" && Array.isArray(d.hosts) && d.hosts.length) {
    return (
      <ul className="divide-y divide-line rounded-md border border-line text-sm">
        {d.hosts.map((h: { preference: number; host: string; resolves: boolean }) => (
          <li key={h.host} className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="min-w-0 truncate"><span className="mr-2 text-xs text-muted">{h.preference}</span><span className="text-heading">{h.host}</span></span>
            <StatusPill status={h.resolves ? "pass" : "fail"} label={h.resolves ? "Resolves" : "No address"} />
          </li>
        ))}
      </ul>
    );
  }
  if (r.check === "dns" && Array.isArray(d.name_servers)) {
    return d.name_servers.length ? (
      <ul className="divide-y divide-line rounded-md border border-line text-sm">
        {d.name_servers.map((n: { ns: string; authoritative: boolean; serial: number | null; error: string }) => (
          <li key={n.ns} className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="min-w-0 truncate text-heading">{n.ns}{n.serial != null && <span className="ml-2 text-xs text-muted">serial {n.serial}</span>}</span>
            <StatusPill status={n.authoritative ? "pass" : "warn"} label={n.authoritative ? "Answering" : "Not answering"} />
          </li>
        ))}
      </ul>
    ) : null;
  }
  return null;
}

export default function CheckCard({ name, result }: { name: CheckName; result?: CheckResult }) {
  const status = result?.status ?? "none";
  const problems = (result?.findings ?? []).filter((f) => f.severity !== "info");
  const notes = (result?.findings ?? []).filter((f) => f.severity === "info");
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-line bg-surface" aria-labelledby={`check-${name}`}>
      <header className="flex items-start gap-3 border-b border-line px-5 py-4">
        <StatusIcon status={status} size={36} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 id={`check-${name}`} className="text-[17px] font-semibold">{CHECK_LABEL[name]}</h3>
            <StatusPill status={status} />
          </div>
          <p className="truncate text-xs text-muted">{CHECK_LONG[name]}</p>
        </div>
      </header>
      <div className="flex-1 space-y-4 px-5 py-4">
        <p className="text-sm text-ink">{result?.summary ?? "Not checked yet."}</p>
        {result?.record && <CopyField label={name === "mx" ? "Published records" : "Published record"} value={result.record} />}
        {result && <Details r={result} />}
        {problems.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold text-muted">{problems.length} issue{problems.length > 1 ? "s" : ""} to fix</p>
            <ul className="divide-y divide-line">{problems.map((f) => <FindingItem key={f.code + f.title} f={f} />)}</ul>
          </div>
        )}
        {notes.length > 0 && <ul className="divide-y divide-line border-t border-line pt-3">{notes.map((f) => <FindingItem key={f.code + f.title} f={f} />)}</ul>}
      </div>
    </section>
  );
}
