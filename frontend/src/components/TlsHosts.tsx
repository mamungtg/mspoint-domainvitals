import { FormEvent, useEffect, useState } from "react";
import { api, CertRow, Domain, errorText, HostScan } from "../lib/api";
import { useApi } from "../lib/useApi";
import { DaysLeft, FindingList } from "./CertTable";
import { IconRefresh } from "./icons";
import { Alert, Button, Card, Field, Input, Spinner, StatusPill, timeAgo } from "./ui";

function Detail({ hostId }: { hostId: string }) {
  const { data } = useApi<HostScan[]>(`/tls-hosts/${hostId}/scans/`);
  const last = data?.find((s) => s.status !== "queued");
  if (!data) return <Spinner label="Loading certificate…" />;
  if (!last) return <p className="text-sm text-muted">The first check is running.</p>;
  if (last.status === "failed") return <FindingList findings={last.findings} />;
  const c = last.certificate;
  const rows: [string, string][] = [
    ["Issued to", c.subject_cn || "–"],
    ["Also covers", (c.sans ?? []).filter((n) => n !== c.subject_cn).join(", ") || "–"],
    ["Issuer", [c.issuer, c.issuer_org].filter(Boolean).join(", ") || "–"],
    ["Valid", c.not_before && c.not_after ? `${new Date(c.not_before).toLocaleDateString()} to ${new Date(c.not_after).toLocaleDateString()}` : "–"],
    ["Key", c.key_type ? `${c.key_type}${c.key_bits ? ` ${c.key_bits}-bit` : ""}, ${c.signature_algorithm?.toUpperCase()}` : "–"],
    ["Protocol", [c.tls_version, c.cipher].filter(Boolean).join(", ") || "–"],
    ["HSTS", c.hsts ?? "Not set"],
    ["Server IP", c.ip || "–"],
  ];
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <dl className="grid grid-cols-[7.5rem_1fr] gap-x-4 gap-y-2 text-sm">
        {rows.map(([k, v]) => <DetailRow key={k} k={k} v={v} />)}
      </dl>
      <div><p className="mb-3 text-sm font-semibold text-heading">Findings</p><FindingList findings={last.findings} /></div>
    </div>
  );
}
const DetailRow = ({ k, v }: { k: string; v: string }) => (<><dt className="text-muted">{k}</dt><dd className="break-words text-ink">{v}</dd></>);

export default function TlsHosts({ domain, writable }: { domain: Domain; writable: boolean }) {
  const { data, error, reload } = useApi<CertRow[]>(`/domains/${domain.id}/tls-hosts/`);
  const [open, setOpen] = useState<string | null>(null);
  const [hostname, setHostname] = useState("");
  const [port, setPort] = useState("443");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const pending = data?.some((h) => h.pending);

  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => { void reload(); }, 3000);
    return () => clearInterval(t);
  }, [pending, reload]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setMsg(null);
    try { await fn(); setMsg({ tone: "success", text: ok }); await reload(); }
    catch (e) { setMsg({ tone: "error", text: errorText(e) }); }
  };

  const add = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    await run(() => api(`/domains/${domain.id}/tls-hosts/`, { method: "POST", json: { hostname, port: Number(port) || 443 } }),
      `${hostname} added. The first check is running.`);
    setHostname(""); setPort("443"); setBusy(false);
  };

  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Card><Spinner /></Card>;
  return (
    <div className="space-y-6">
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      <Card padded={false} title="Certificates" description={`HTTPS certificates for ${domain.name} and its subdomains, checked once a day.`}>
        {data.length === 0 ? <p className="px-5 py-10 text-center text-muted">No host names yet. They are added automatically after verification.</p> : (
          <ul className="divide-y divide-line">
            {data.map((h) => (
              <li key={h.id}>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
                  <StatusPill status={h.pending && !h.status ? "none" : (h.status ?? "none")}
                    label={h.pending && !h.status ? "Checking" : h.status === "error" ? "Unreachable" : undefined} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-heading">{h.label}</p>
                    <p className="text-xs text-muted">{h.issuer ?? "Issuer unknown"} · {h.pending ? "Checking now" : `Checked ${timeAgo(h.scanned_at).toLowerCase()}`}</p>
                  </div>
                  <DaysLeft days={h.days_left} />
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" aria-expanded={open === h.id} onClick={() => setOpen(open === h.id ? null : h.id)}>
                      {open === h.id ? "Hide details" : "Details"}
                    </Button>
                    {writable && <>
                      <Button variant="secondary" size="sm" disabled={h.pending} aria-label={`Check ${h.label} now`}
                        onClick={() => run(() => api(`/tls-hosts/${h.id}/scan/`, { method: "POST" }), `Checking ${h.label}.`)}>
                        <IconRefresh />Check
                      </Button>
                      <Button variant="danger" size="sm" aria-label={`Stop checking ${h.label}`}
                        onClick={() => { if (window.confirm(`Stop checking ${h.label}?`)) void run(() => api(`/tls-hosts/${h.id}/`, { method: "DELETE" }), `${h.label} removed.`); }}>
                        Remove
                      </Button>
                    </>}
                  </div>
                </div>
                {open === h.id && <div className="border-t border-line bg-subtle/50 px-5 py-4"><Detail hostId={h.id} /></div>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {writable && (
        <Card title="Check another host name" description={`Any subdomain of ${domain.name}, for example mail.${domain.name} or portal.${domain.name}.`}>
          <form onSubmit={add} className="grid gap-3 sm:grid-cols-[1fr_7rem_auto] sm:items-end" noValidate>
            <Field label="Host name"><Input value={hostname} onChange={(e) => setHostname(e.target.value)} placeholder={`mail.${domain.name}`} /></Field>
            <Field label="Port"><Input inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value.replace(/\D/g, ""))} /></Field>
            <Button type="submit" busy={busy} disabled={!hostname.trim()}>Add host name</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
