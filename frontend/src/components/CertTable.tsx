import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { CertRow, Finding } from "../lib/api";
import { IconChevron } from "./icons";
import { Badge, cls, StatusPill, timeAgo } from "./ui";

export function daysLabel(d: number | null): string {
  if (d === null) return "–";
  if (d < 0) return `Expired ${-d} day${d === -1 ? "" : "s"} ago`;
  if (d === 0) return "Expires today";
  return `${d} day${d === 1 ? "" : "s"}`;
}

export function DaysLeft({ days }: { days: number | null }) {
  const tone = days === null ? "text-muted" : days < 0 || days <= 7 ? "text-fail" : days <= 30 ? "text-warn" : "text-heading";
  return <span className={cls("font-semibold tabular-nums", tone)}>{daysLabel(days)}</span>;
}

export function FindingList({ findings }: { findings: Finding[] }) {
  if (!findings.length) return <p className="text-sm text-muted">No problems found.</p>;
  const tone = { critical: "fail", warning: "warn", info: "neutral" } as const;
  const label = { critical: "Critical", warning: "Warning", info: "Note" };
  return (
    <ul className="space-y-3">
      {findings.map((f) => (
        <li key={f.code}>
          <p className="flex flex-wrap items-center gap-2 font-medium text-heading"><Badge tone={tone[f.severity]}>{label[f.severity]}</Badge>{f.title}</p>
          <p className="mt-1 text-sm text-muted">{f.detail}</p>
          {f.fix && <p className="mt-1 text-sm"><span className="font-semibold text-heading">How to fix:</span> {f.fix}</p>}
        </li>
      ))}
    </ul>
  );
}

/** Certificates table with an expandable findings row. */
export default function CertTable({ rows, showDomain = true, empty }: { rows: CertRow[]; showDomain?: boolean; empty: string }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!rows.length) return <p className="px-5 py-10 text-center text-muted">{empty}</p>;
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="bg-subtle text-xs text-muted">
          <tr>
            <th className="px-5 py-2.5 font-medium">Status</th>
            <th className="px-3 py-2.5 font-medium">Host</th>
            <th className="px-3 py-2.5 font-medium">Time left</th>
            <th className="px-3 py-2.5 font-medium">Issuer</th>
            <th className="px-3 py-2.5 font-medium">Valid until</th>
            <th className="px-3 py-2.5 font-medium">Checked</th>
            <th className="w-10 px-3 py-2.5"><span className="sr-only">Details</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => {
            const expanded = open === r.id;
            const status = r.pending && !r.status ? "none" : (r.status ?? "none");
            return (
              <Fragment key={r.id}>
                <tr className={cls("align-middle", expanded && "bg-subtle/60")}>
                  <td className="px-5 py-3"><StatusPill status={status} label={r.pending && !r.status ? "Checking" : r.status === "error" ? "Unreachable" : undefined} /></td>
                  <td className="px-3 py-3">
                    <p className="font-medium text-heading">{r.label}</p>
                    {showDomain && <Link to={`/domains/${r.domain_id}`} className="text-xs text-muted hover:text-heading">{r.domain}</Link>}
                  </td>
                  <td className="px-3 py-3"><DaysLeft days={r.days_left} /></td>
                  <td className="px-3 py-3 text-ink">{r.issuer ?? "–"}</td>
                  <td className="px-3 py-3 text-ink tabular-nums">{r.not_after ? new Date(r.not_after).toLocaleDateString() : "–"}</td>
                  <td className="px-3 py-3 text-muted">{r.pending ? "In progress" : timeAgo(r.scanned_at)}</td>
                  <td className="px-3 py-3">
                    <button type="button" onClick={() => setOpen(expanded ? null : r.id)} aria-expanded={expanded}
                      aria-label={`${expanded ? "Hide" : "Show"} details for ${r.label}`}
                      className={cls("rounded p-1 text-muted hover:bg-subtle hover:text-heading", expanded && "rotate-90")}><IconChevron /></button>
                  </td>
                </tr>
                {expanded && (
                  <tr className="bg-subtle/60">
                    <td colSpan={7} className="px-5 pb-5 pt-1">
                      {r.error ? <p className="text-sm text-muted">{r.error}</p> : <FindingList findings={r.findings} />}
                      {r.tls_version && <p className="mt-3 text-xs text-muted">Negotiated {r.tls_version}</p>}
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
