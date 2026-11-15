import { Fragment, useRef, useState } from "react";
import { api, DmarcDomainRow, DmarcReportRow, DmarcSender, DmarcStatus, DmarcSummary, errorText } from "../lib/api";
import { Alert, Badge, Button, Card, cls, CopyField, Health, KpiTile, StatusPill, timeAgo } from "./ui";

const nf = new Intl.NumberFormat();
export const num = (n: number) => nf.format(n);
export const pct = (r: number | null | undefined) => (r == null ? "–" : `${(r * 100).toFixed(r >= 0.995 || r === 0 ? 0 : 1)}%`);

export const STATUS: Record<DmarcStatus, { label: string; tone: Health }> = {
  receiving: { label: "Receiving reports", tone: "pass" },
  waiting: { label: "Waiting for first report", tone: "none" },
  not_configured: { label: "Not set up", tone: "warn" },
  no_dmarc: { label: "No DMARC record", tone: "fail" },
  unknown: { label: "Not scanned yet", tone: "none" },
};

const VERDICT: Record<DmarcSender["verdict"], { label: string; tone: Health }> = {
  pass: { label: "Authenticated", tone: "pass" },
  warn: { label: "Partly failing", tone: "warn" },
  fail: { label: "Not authenticated", tone: "fail" },
};

export function PeriodSwitch({ value, onChange }: { value: number; onChange: (d: number) => void }) {
  return (
    <div role="group" aria-label="Period" className="inline-flex rounded-md border border-line bg-surface p-0.5">
      {[7, 30, 90].map((d) => (
        <button key={d} type="button" aria-pressed={value === d} onClick={() => onChange(d)}
          className={cls("rounded px-3 py-1 text-sm font-medium", value === d ? "bg-navy-700 text-white" : "text-muted hover:text-heading")}>
          {d} days
        </button>
      ))}
    </div>
  );
}

export function DmarcKpis({ s }: { s: DmarcSummary }) {
  const t = s.totals;
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <KpiTile label="Messages reported" value={num(t.messages)} sub={`Last ${s.days} days`} />
      <KpiTile label="Passing DMARC" value={pct(t.pass_rate)} tone={t.pass_rate == null ? "neutral" : t.pass_rate >= 0.98 ? "pass" : t.pass_rate >= 0.9 ? "warn" : "fail"}
        sub={`${num(t.passed)} aligned with SPF or DKIM`} />
      <KpiTile label="Failing DMARC" value={num(t.failed)} tone={t.failed ? "warn" : "neutral"}
        sub={`${num(t.quarantined)} quarantined, ${num(t.rejected)} rejected`} />
      <KpiTile label="Unauthenticated senders" value={t.unauthenticated_senders} tone={t.unauthenticated_senders ? "fail" : "neutral"}
        sub={`of ${t.senders} sending service${t.senders === 1 ? "" : "s"}`} />
    </div>
  );
}

/** Stacked daily bars: passing (green) under failing (red). HTML rather than a
 *  scaled SVG so axis text stays the same size at every width. */
export function DailyVolumeChart({ days }: { days: DmarcSummary["by_day"] }) {
  const max = Math.max(1, ...days.map((d) => d.passed + d.failed));
  const every = days.length > 31 ? 14 : days.length > 8 ? 5 : 1;
  const fmt = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
  const total = days.reduce((a, d) => a + d.passed + d.failed, 0);
  return (
    <div role="img" aria-label={`Messages per day over ${days.length} days, ${num(total)} in total. Green passed DMARC, red failed.`}>
      <div className="flex gap-2">
        <div className="flex h-48 w-10 shrink-0 flex-col justify-between text-right text-[11px] text-muted tabular-nums" aria-hidden="true">
          <span>{num(max)}</span><span>{num(Math.round(max / 2))}</span><span>0</span>
        </div>
        <div className="relative h-48 flex-1 border-b border-line">
          <div className="absolute inset-x-0 top-0 border-t border-dashed border-line" aria-hidden="true" />
          <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-line" aria-hidden="true" />
          <div className={cls("relative flex h-full items-end", days.length > 31 ? "gap-px" : "gap-[3px] sm:gap-1")}>
            {days.map((d) => (
              <div key={d.day} className="flex h-full min-w-0 flex-1 flex-col justify-end" title={`${fmt(d.day)}: ${num(d.passed)} passed, ${num(d.failed)} failed`}>
                <span className="block rounded-t-sm bg-fail" style={{ height: `${(d.failed / max) * 100}%` }} />
                <span className={cls("block bg-pass", !d.failed && "rounded-t-sm")} style={{ height: `${(d.passed / max) * 100}%` }} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="ml-12 mt-1.5 flex text-[11px] text-muted" aria-hidden="true">
        {days.map((d, i) => (
          <span key={d.day} className="relative min-w-0 flex-1">
            {(days.length - 1 - i) % every === 0 && <span className="absolute right-0 whitespace-nowrap">{fmt(d.day)}</span>}
          </span>
        ))}
      </div>
      <div className="h-4" />
    </div>
  );
}

function AlignBar({ n, of }: { n: number; of: number }) {
  const r = of ? n / of : 0;
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
        <span className={cls("block h-full", r >= 0.95 ? "bg-pass" : r > 0 ? "bg-warn" : "bg-fail")} style={{ width: `${r * 100}%` }} />
      </span>
      <span className="tabular-nums text-ink">{pct(of ? r : null)}</span>
    </span>
  );
}

export function SenderTable({ senders }: { senders: DmarcSender[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!senders.length) return <p className="px-5 py-8 text-center text-muted">No messages reported in this period.</p>;
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="bg-subtle text-xs text-muted">
          <tr>
            <th className="px-5 py-2.5 font-medium">Sending service</th>
            <th className="px-3 py-2.5 font-medium">Status</th>
            <th className="px-3 py-2.5 text-right font-medium">Messages</th>
            <th className="px-3 py-2.5 font-medium">DMARC pass</th>
            <th className="px-3 py-2.5 font-medium">SPF aligned</th>
            <th className="px-3 py-2.5 font-medium">DKIM aligned</th>
            <th className="px-3 py-2.5"><span className="sr-only">Details</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {senders.map((s) => {
            const expanded = open === s.name;
            return (
              <Fragment key={s.name}>
                <tr className={cls(expanded && "bg-subtle/60")}>
                  <td className="px-5 py-3">
                    <p className="font-medium text-heading">{s.name}</p>
                    <p className="text-xs text-muted">{s.ips.length} IP address{s.ips.length === 1 ? "" : "es"}</p>
                  </td>
                  <td className="px-3 py-3"><StatusPill status={VERDICT[s.verdict].tone} label={VERDICT[s.verdict].label} /></td>
                  <td className="px-3 py-3 text-right font-medium text-heading tabular-nums">{num(s.messages)}</td>
                  <td className="px-3 py-3"><AlignBar n={s.passed} of={s.messages} /></td>
                  <td className="px-3 py-3"><AlignBar n={s.spf_aligned} of={s.messages} /></td>
                  <td className="px-3 py-3"><AlignBar n={s.dkim_aligned} of={s.messages} /></td>
                  <td className="px-3 py-3 text-right">
                    <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : s.name)}>{expanded ? "Hide" : "IPs"}</Button>
                  </td>
                </tr>
                {expanded && (
                  <tr className="bg-subtle/60">
                    <td colSpan={7} className="px-5 pb-4 pt-1">
                      <SenderAdvice s={s} />
                      <ul className="mt-3 divide-y divide-line rounded-md border border-line bg-surface">
                        {s.ips.map((ip) => (
                          <li key={ip.ip} className="grid gap-1 px-3 py-2 text-[13px] sm:grid-cols-[12rem_1fr_6rem_6rem] sm:items-center sm:gap-4">
                            <span className="font-mono text-heading">{ip.ip}</span>
                            <span className="min-w-0 truncate text-muted">
                              {ip.ptr || "No reverse DNS"}{ip.dkim_domains.length > 0 && ` · signed by ${ip.dkim_domains.join(", ")}`}
                            </span>
                            <span className="tabular-nums text-ink sm:text-right">{num(ip.messages)} msgs</span>
                            <span className="tabular-nums text-muted sm:text-right">{pct(ip.messages ? ip.passed / ip.messages : null)} pass</span>
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SenderAdvice({ s }: { s: DmarcSender }) {
  if (s.verdict === "pass") return <p className="text-sm text-ink">This service is set up correctly: its mail passes DMARC.</p>;
  if (s.verdict === "fail" && !s.known)
    return <p className="text-sm text-ink">None of this mail passed SPF or DKIM for your domain and the sender is not a recognised service. If you don't know this sender, it is probably someone spoofing your domain; a p=quarantine or p=reject policy stops it.</p>;
  const dkimLow = s.dkim_aligned < s.messages * 0.95;
  return (
    <p className="text-sm text-ink">
      Some of this mail fails DMARC. {dkimLow
        ? `Turn on DKIM signing with your own domain in ${s.name} (most services call this "domain authentication") so its mail aligns even when it is forwarded.`
        : "Add this service to your SPF record or check its DKIM setup."}
    </p>
  );
}

export function SetupPanel({ row, rua }: { row: DmarcDomainRow; rua: string }) {
  if (row.status === "receiving") return null;
  return (
    <div className="space-y-3 text-sm text-ink">
      {row.status === "waiting" ? (
        <p>Your DMARC record already sends reports to DomainVitals. Mail providers send reports once a day, so the first one usually arrives within 24 to 48 hours.</p>
      ) : (
        <>
          <p>
            {row.status === "no_dmarc"
              ? <>{row.name} has no DMARC record yet. Publish this TXT record to start receiving reports. <b>p=none</b> only monitors; nothing is blocked.</>
              : <>Add <b>{rua}</b> to the <b>rua=</b> tag of your DMARC record. Everything else in your record stays the same, including any reporting address you already use.</>}
          </p>
          <CopyField label={`TXT record at _dmarc.${row.name}`} value={row.suggested_record} />
          <p className="text-xs text-muted">Reports start arriving within one or two days of the change.</p>
        </>
      )}
    </div>
  );
}

export function DomainStatusTable({ rows, rua }: { rows: DmarcDomainRow[]; rua: string }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <ul className="divide-y divide-line">
      {rows.map((r) => {
        const expanded = open === r.id;
        return (
          <li key={r.id} className="px-5 py-3">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="min-w-0 flex-1 truncate font-medium text-heading max-sm:basis-full">{r.name}</span>
              {r.policy && <Badge>p={r.policy}</Badge>}
              <span className="w-28 text-right text-sm tabular-nums text-ink">{r.messages ? `${pct(r.pass_rate)} pass` : "–"}</span>
              <StatusPill status={STATUS[r.status].tone} label={STATUS[r.status].label} />
              {r.status !== "receiving"
                ? <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : r.id)}>{expanded ? "Close" : "Set up"}</Button>
                : <span className="w-[4.5rem] text-right text-xs text-muted">{timeAgo(r.last_report)}</span>}
            </div>
            {expanded && <div className="mt-3 rounded-md bg-subtle p-4"><SetupPanel row={r} rua={rua} /></div>}
          </li>
        );
      })}
    </ul>
  );
}

export function ReportList({ reports }: { reports: DmarcReportRow[] }) {
  if (!reports.length) return <p className="px-5 py-8 text-center text-muted">No reports received yet.</p>;
  const day = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" });
  return (
    <ul className="divide-y divide-line">
      {reports.map((r) => (
        <li key={r.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-2.5 text-sm">
          <span className="min-w-0 flex-1 truncate font-medium text-heading">{r.reporter}</span>
          <span className="text-muted">{day(r.date_begin)}{day(r.date_end) !== day(r.date_begin) && ` – ${day(r.date_end)}`}</span>
          <span className="w-24 text-right tabular-nums text-ink">{num(r.messages)} msgs</span>
          {r.source === "upload" && <Badge>Uploaded</Badge>}
        </li>
      ))}
    </ul>
  );
}

export function UploadReport({ domainId, onDone }: { domainId: string; onDone: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  async function upload(file: File) {
    setBusy(true); setMsg(null);
    const body = new FormData();
    body.append("file", file);
    try {
      const r = await api<{ stored: number; duplicates: number }>(`/domains/${domainId}/dmarc/upload/`, { method: "POST", body });
      setMsg(r.stored ? { tone: "success", text: "Report imported." } : { tone: "success", text: "This report was already imported." });
      onDone();
    } catch (e) {
      setMsg({ tone: "error", text: errorText(e) });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }
  return (
    <div className="space-y-3">
      <input ref={input} type="file" accept=".xml,.gz,.zip,application/xml,text/xml,application/gzip,application/zip" className="sr-only" id={`dmarc-upload-${domainId}`}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); }} />
      <Button variant="secondary" busy={busy} onClick={() => input.current?.click()}>Import a report file</Button>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
    </div>
  );
}

export function VolumeCard({ s }: { s: DmarcSummary }) {
  return (
    <Card title="Mail volume" description="Messages reported per day by Google, Microsoft, Yahoo and other receivers">
      <DailyVolumeChart days={s.by_day} />
      <ul className="mt-3 flex gap-4 text-xs text-muted">
        <li className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-pass" aria-hidden="true" />Passed DMARC</li>
        <li className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-fail" aria-hidden="true" />Failed DMARC</li>
      </ul>
    </Card>
  );
}
