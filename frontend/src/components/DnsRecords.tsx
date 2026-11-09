import { Fragment, useState } from "react";
import { api, DnsChange, DnsRecords as DnsRecordsData, errorText, Propagation } from "../lib/api";
import { useApi } from "../lib/useApi";
import { Alert, Badge, Button, Card, cls, Spinner, StatusPill, timeAgo } from "./ui";

const KIND: Record<DnsChange["kind"], { label: string; tone: "pass" | "fail" | "warn" | "neutral" }> = {
  added: { label: "Added", tone: "pass" }, removed: { label: "Removed", tone: "fail" },
  changed: { label: "Changed", tone: "warn" }, ttl: { label: "TTL changed", tone: "neutral" },
};

export function ttlText(ttl: number | null | undefined): string {
  if (ttl == null) return "–";
  if (ttl % 86400 === 0) return `${ttl / 86400}d`;
  if (ttl % 3600 === 0) return `${ttl / 3600}h`;
  if (ttl % 60 === 0) return `${ttl / 60}m`;
  return `${ttl}s`;
}

/** Old -> new values with removed values struck through and added ones marked. */
export function ChangeDiff({ c }: { c: DnsChange }) {
  if (c.kind === "ttl") return <p className="text-sm text-ink">TTL {ttlText(c.old_ttl)} → {ttlText(c.new_ttl)}</p>;
  const removed = c.old_values.filter((v) => !c.new_values.includes(v));
  const added = c.new_values.filter((v) => !c.old_values.includes(v));
  return (
    <ul className="space-y-1 font-mono text-[12.5px]">
      {removed.map((v) => <li key={"-" + v} className="break-all text-fail"><span aria-hidden="true">− </span><span className="sr-only">Removed: </span><span className="line-through decoration-fail/50">{v}</span></li>)}
      {added.map((v) => <li key={"+" + v} className="break-all text-pass"><span aria-hidden="true">+ </span><span className="sr-only">Added: </span>{v}</li>)}
    </ul>
  );
}

function PropagationGrid({ domainId, name, type }: { domainId: string; name: string; type: string }) {
  const q = new URLSearchParams({ name, type }).toString();
  const { data, error } = useApi<Propagation>(`/domains/${domainId}/propagation/?${q}`);
  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Spinner label="Asking name servers and public resolvers…" />;
  return <PropagationResult data={data} />;
}

export function PropagationResult({ data }: { data: Propagation }) {
  const label = { match: "Up to date", different: "Old value", missing: "No record", error: "No answer" } as const;
  const tone = { match: "pass", different: "warn", missing: "fail", error: "none" } as const;
  return (
    <div>
      <p className="mb-3 text-sm text-ink">
        {data.propagated
          ? `Every server that answered (${data.answered} of ${data.total}) returns the same value.`
          : `${data.matched} of ${data.answered} servers return the current value. The others are still serving an older answer from cache.`}
      </p>
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="bg-subtle text-xs text-muted">
            <tr><th className="px-3 py-2 font-medium">Server</th><th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Answer</th><th className="px-3 py-2 font-medium">TTL</th></tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.servers.map((s) => (
              <tr key={s.kind + s.server}>
                <td className="px-3 py-2">
                  <p className="font-medium text-heading">{s.server}</p>
                  <p className="text-xs text-muted">{s.kind === "authoritative" ? "Authoritative" : "Public resolver"} · {s.ip}</p>
                </td>
                <td className="px-3 py-2"><StatusPill status={tone[s.status]} label={label[s.status]} /></td>
                <td className="px-3 py-2 font-mono text-[12.5px] text-ink">
                  {s.status === "error" ? <span className="font-sans text-muted">{s.error}</span> : (s.values ?? []).length ? (s.values ?? []).map((v) => <div key={v} className="break-all">{v}</div>) : <span className="font-sans text-muted">none</span>}
                </td>
                <td className="px-3 py-2 text-muted tabular-nums">{ttlText(s.ttl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DnsRecords({ domainId, domainName }: { domainId: string; domainName: string }) {
  const { data, error } = useApi<DnsRecordsData>(`/domains/${domainId}/records/`);
  const { data: changes } = useApi<DnsChange[]>(`/domains/${domainId}/changes/`);
  const [open, setOpen] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Card><Spinner /></Card>;
  if (!data.scanned_at) return <Card><p className="text-muted">Records appear after the first scan finishes.</p></Card>;

  const rows = data.records.filter((r) => !filter || r.type === filter);
  const types = Array.from(new Set(data.records.map((r) => r.type)));

  return (
    <div className="space-y-6">
      {data.name_servers.length > 0 && (
        <Card title="Name servers" description={data.soa ? `Primary ${data.soa.primary}, zone serial ${data.soa.serial}` : undefined} padded={false}>
          <ul className="divide-y divide-line">
            {data.name_servers.map((n) => (
              <li key={n.ns} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3">
                <StatusPill status={n.authoritative ? "pass" : "warn"} label={n.authoritative ? "Answering" : "Not answering"} />
                <span className="min-w-0 flex-1 truncate font-medium text-heading">{n.ns}</span>
                <span className="text-xs text-muted">{n.ip || "no address"}{n.serial != null && ` · serial ${n.serial}`}</span>
                {n.error && <span className="basis-full text-xs text-muted">{n.error}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card padded={false} title="Records" description={`What ${domainName} publishes, as of ${timeAgo(data.scanned_at).toLowerCase()}. Select a record to check propagation.`}
        actions={
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted">Type</span>
            <select value={filter} onChange={(e) => setFilter(e.target.value)} className="h-8 rounded-md border border-line bg-surface px-2 text-sm text-heading">
              <option value="">All</option>{types.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>}>
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-subtle text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">Name</th><th className="px-3 py-2.5 font-medium">Type</th>
                <th className="px-3 py-2.5 font-medium">TTL</th><th className="px-3 py-2.5 font-medium">Value</th>
                <th className="px-3 py-2.5 font-medium">Last changed</th><th className="px-3 py-2.5"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((r) => {
                const key = `${r.name} ${r.type}`;
                const expanded = open === key;
                return (
                  <Fragment key={key}>
                    <tr className={cls("align-top", expanded && "bg-subtle/60")}>
                      <td className="px-5 py-3 font-medium text-heading">{r.name === domainName ? "@" : r.name.replace(`.${domainName}`, "")}</td>
                      <td className="px-3 py-3"><Badge>{r.type}</Badge></td>
                      <td className="px-3 py-3 text-muted tabular-nums">{ttlText(r.ttl)}</td>
                      <td className="max-w-[28rem] px-3 py-3 font-mono text-[12.5px] text-ink">{r.values.map((v) => <div key={v} className="break-all">{v}</div>)}</td>
                      <td className="px-3 py-3 text-muted">{r.last_changed ? timeAgo(r.last_changed) : "No change seen"}</td>
                      <td className="px-3 py-3 text-right">
                        <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : key)}>
                          {expanded ? "Close" : "Propagation"}
                        </Button>
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="bg-subtle/60"><td colSpan={6} className="px-5 pb-5 pt-1">
                        <PropagationGrid domainId={domainId} name={r.name} type={r.type} />
                      </td></tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <Card padded={false} title="Change history" description="Every record set that changed between two scans.">
        {!changes ? <Spinner /> : changes.length === 0 ? (
          <p className="px-5 py-8 text-center text-muted">No changes detected since monitoring started.</p>
        ) : (
          <ol className="divide-y divide-line">
            {changes.map((c) => (
              <li key={c.id} className="grid gap-2 px-5 py-3.5 sm:grid-cols-[9rem_1fr]">
                <time dateTime={c.detected_at} className="text-xs text-muted">{new Date(c.detected_at).toLocaleString()}</time>
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-sm">
                    <Badge tone={KIND[c.kind].tone}>{KIND[c.kind].label}</Badge>
                    <span className="font-medium text-heading">{c.name}</span><Badge>{c.rtype}</Badge>
                  </p>
                  <div className="mt-1.5"><ChangeDiff c={c} /></div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}

export async function runToolPropagation(name: string, type: string): Promise<Propagation> {
  try { return await api<Propagation>("/tools/propagation/", { method: "POST", json: { name, type } }); }
  catch (e) { throw new Error(errorText(e)); }
}
