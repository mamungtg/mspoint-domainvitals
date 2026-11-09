import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CheckCard from "../components/CheckCard";
import TlsHosts from "../components/TlsHosts";
import { ScoreLineChart } from "../components/charts";
import { IconRefresh } from "../components/icons";
import {
  Alert, Badge, Button, Card, CopyField, Field, Input, linkCls, PageHeader, ScoreBar, ScoreRing, Spinner, StatusIcon, StatusPill,
  Tabs, timeAgo,
} from "../components/ui";
import { api, CHECK_LABEL, CheckName, Domain, errorText, isManager, ScanDetail, ScanSummary } from "../lib/api";
import { canWrite } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

const CHECKS: CheckName[] = ["dmarc", "spf", "dkim", "mx"];
const TRIGGER: Record<string, string> = { manual: "Manual", schedule: "Scheduled", verification: "After verification", demo: "Sample" };
type Tab = "results" | "tls" | "history" | "settings";

function Verification({ domain, writable, onVerified }: { domain: Domain; writable: boolean; onVerified: (d: Domain) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const verify = async () => {
    setBusy(true); setError("");
    try { onVerified(await api<Domain>(`/domains/${domain.id}/verify/`, { method: "POST" })); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  return (
    <Card title="Prove you control this domain" description="Scans start once DomainVitals finds this record. It only needs to stay in place.">
      <ol className="space-y-5">
        <li className="flex gap-4">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-subtle text-[13px] font-semibold text-heading">1</span>
          <div className="min-w-0 flex-1"><p className="font-medium text-heading">Open the DNS settings for {domain.name}</p>
            <p className="text-sm text-muted">Usually at your registrar or DNS host, such as Cloudflare, GoDaddy or Namecheap.</p></div>
        </li>
        <li className="flex gap-4">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-subtle text-[13px] font-semibold text-heading">2</span>
          <div className="min-w-0 flex-1 space-y-3"><p className="font-medium text-heading">Add this TXT record</p>
            <div className="grid gap-3 sm:grid-cols-[6rem_1fr]">
              <CopyField label="Type" value="TXT" />
              <CopyField label="Host / name" value={domain.verification.host} />
            </div>
            <CopyField label="Value" value={domain.verification.value} />
            <p className="text-xs text-muted">Some DNS hosts add the domain automatically; then enter only <code className="font-mono">_domainvitals</code> as the host.</p>
          </div>
        </li>
        <li className="flex gap-4">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-subtle text-[13px] font-semibold text-heading">3</span>
          <div className="min-w-0 flex-1"><p className="font-medium text-heading">Check the record</p>
            <p className="text-sm text-muted">New records usually appear within a few minutes.</p>
            {error && <div className="mt-3"><Alert>{error}</Alert></div>}
            {writable ? <Button className="mt-3" busy={busy} onClick={verify}>Verify domain</Button>
              : <p className="mt-3 text-sm text-muted">Ask an owner, admin or member of this workspace to verify it.</p>}
          </div>
        </li>
      </ol>
    </Card>
  );
}

function History({ domainId }: { domainId: string }) {
  const { data, error } = useApi<ScanSummary[]>(`/domains/${domainId}/scans/`);
  const points = useMemo(() => (data ?? []).filter((s) => s.status === "completed").slice().reverse()
    .map((s) => ({ label: new Date(s.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" }), value: s.health_score })), [data]);
  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Spinner />;
  if (!data.length) return <Card><p className="text-muted">No scans yet.</p></Card>;
  return (
    <div className="space-y-6">
      <Card title="Health score over time"><ScoreLineChart points={points} /></Card>
      <Card padded={false} title="Scans" description="The last 30 scans">
        <div className="relative overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead><tr className="border-b border-line bg-subtle text-left text-xs text-muted">
              <th className="px-5 py-2.5 font-medium">When</th><th className="px-3 py-2.5 font-medium">Started by</th>
              <th className="px-3 py-2.5 font-medium">Health</th>
              {(["spf", "dkim", "dmarc", "mx"] as CheckName[]).map((c) => <th key={c} className="px-3 py-2.5 text-center font-medium">{CHECK_LABEL[c]}</th>)}
              <th className="px-3 py-2.5 font-medium">Issues</th></tr></thead>
            <tbody className="divide-y divide-line">
              {data.map((s) => (
                <tr key={s.id}>
                  <td className="whitespace-nowrap px-5 py-2.5 text-heading">{new Date(s.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-muted">{TRIGGER[s.trigger] ?? s.trigger}</td>
                  <td className="px-3 py-2.5">{s.status === "completed" ? <ScoreBar score={s.health_score} /> : <Badge>{s.status}</Badge>}</td>
                  {(["spf", "dkim", "dmarc", "mx"] as CheckName[]).map((c) => <td key={c} className="px-3 py-2.5 text-center"><span className="inline-flex"><StatusIcon status={s.summary[c] ?? "none"} /></span></td>)}
                  <td className="px-3 py-2.5 text-muted">{s.critical_count} critical, {s.warning_count} warnings</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Settings({ domain, writable, manager, onChange }: { domain: Domain; writable: boolean; manager: boolean; onChange: (d: Domain) => void }) {
  const navigate = useNavigate();
  const [selectors, setSelectors] = useState(domain.dkim_selectors.join(", "));
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState("");
  const patch = async (body: object, ok: string) => {
    setBusy(Object.keys(body)[0]); setMsg(null);
    try { onChange(await api<Domain>(`/domains/${domain.id}/`, { method: "PATCH", json: body })); setMsg({ tone: "success", text: ok }); }
    catch (e) { setMsg({ tone: "error", text: errorText(e) }); } finally { setBusy(""); }
  };
  const remove = async () => {
    if (!window.confirm(`Remove ${domain.name}? Its scan history will be deleted.`)) return;
    try { await api(`/domains/${domain.id}/`, { method: "DELETE" }); navigate("/domains", { replace: true }); }
    catch (e) { setMsg({ tone: "error", text: errorText(e) }); }
  };
  return (
    <div className="space-y-6">
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
      <Card title="Daily monitoring" description="Scheduled scans run about once a day while monitoring is on.">
        <label className="flex items-center gap-3">
          <input type="checkbox" className="h-4 w-4 accent-[#14508f]" checked={domain.monitoring_enabled} disabled={!writable || busy !== ""}
            onChange={(e) => patch({ monitoring_enabled: e.target.checked }, e.target.checked ? "Monitoring turned on." : "Monitoring paused.")} />
          <span className="text-sm text-heading">Scan {domain.name} automatically</span>
        </label>
      </Card>
      <Card title="DKIM selectors" description="DNS cannot list DKIM keys, so we check common selectors plus any you add here.">
        <form onSubmit={(e) => { e.preventDefault(); patch({ dkim_selectors: selectors.split(/[\s,]+/).filter(Boolean) }, "Selectors saved. They are used from the next scan."); }}
          className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1"><Field label="Your selectors" hint="Separate with commas, for example s2025, mailchimp">
            <Input value={selectors} disabled={!writable} onChange={(e) => setSelectors(e.target.value)} />
          </Field></div>
          {writable && <Button type="submit" variant="secondary" busy={busy === "dkim_selectors"}>Save selectors</Button>}
        </form>
      </Card>
      {domain.is_verified && (
        <Card title="Verification record" description="Keep this record published. If it disappears for three days, monitoring stops.">
          <CopyField label={`TXT at ${domain.verification.host}`} value={domain.verification.value} />
        </Card>
      )}
      {manager && (
        <Card title="Remove domain">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted">Stops monitoring and deletes this domain's scan history.</p>
            <Button variant="danger" onClick={remove}>Remove {domain.name}</Button>
          </div>
        </Card>
      )}
    </div>
  );
}

export default function DomainDetail() {
  const { id = "" } = useParams();
  const { current } = useWorkspace();
  const { data: domain, error, setData: setDomain, reload } = useApi<Domain>(`/domains/${id}/`);
  const latestId = domain?.latest_scan?.status === "completed" ? domain.latest_scan.id : null;
  const { data: scan } = useApi<ScanDetail>(latestId ? `/scans/${latestId}/` : null);
  const [tab, setTab] = useState<Tab>("results");
  const [scanMsg, setScanMsg] = useState("");
  const [scanning, setScanning] = useState(false);
  const writable = canWrite(current);
  const pending = domain?.latest_scan && ["queued", "running"].includes(domain.latest_scan.status);

  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => { void reload(); }, 2500);
    return () => clearInterval(t);
  }, [pending, reload]);

  const scanNow = async () => {
    setScanning(true); setScanMsg("");
    try { await api(`/domains/${id}/scan/`, { method: "POST" }); await reload(); }
    catch (e) { setScanMsg(errorText(e)); } finally { setScanning(false); }
  };

  if (error) return <><PageHeader title="Domain" /><Alert>{error}</Alert><p className="mt-4"><Link className={linkCls} to="/domains">Back to domains</Link></p></>;
  if (!domain) return <Spinner />;
  const ls = domain.latest_scan;

  return (
    <>
      <PageHeader
        eyebrow={<Link to="/domains" className="mb-1 inline-block text-sm text-muted hover:text-heading">Domains /</Link>}
        title={domain.name}
        description={domain.is_verified
          ? <span className="flex flex-wrap items-center gap-2">{ls?.overall_status ? <StatusPill status={ls.overall_status} /> : null}
              <span>{pending ? "Scan in progress…" : `Last checked ${timeAgo(ls?.completed_at)}`}</span>
              {!domain.monitoring_enabled && <Badge>Monitoring paused</Badge>}</span>
          : "Waiting for ownership verification"}
        actions={domain.is_verified && writable &&
          <Button variant="secondary" onClick={scanNow} busy={scanning || !!pending}><IconRefresh />{pending ? "Scanning" : "Scan now"}</Button>}
      />
      {scanMsg && <div className="mb-4"><Alert>{scanMsg}</Alert></div>}

      {!domain.is_verified ? (
        current?.is_demo ? <Alert tone="info">In a real workspace you would publish a TXT record here to prove you control {domain.name}.</Alert>
          : <Verification domain={domain} writable={writable} onVerified={(d) => setDomain(d)} />
      ) : (
        <>
          <Tabs value={tab} onChange={setTab} items={[{ id: "results", label: "Email authentication" }, { id: "tls", label: "SSL/TLS" }, { id: "history", label: "History" }, { id: "settings", label: "Settings" }]} />
          <div className="mt-6">
            {tab === "results" && (!ls || !scan ? (
              <Card><Spinner label={pending ? "Running the first scan…" : "Loading results…"} /></Card>
            ) : (
              <>
                <div className="mb-6 flex flex-wrap items-center gap-6 rounded-lg border border-line bg-surface px-6 py-5">
                  <ScoreRing score={scan.health_score} size={96} />
                  <div className="min-w-0 flex-1">
                    <p className="font-display text-[17px] font-semibold text-heading">
                      {scan.critical_count === 0 && scan.warning_count === 0 ? "Everything checks out" :
                        `${scan.critical_count} critical issue${scan.critical_count === 1 ? "" : "s"} and ${scan.warning_count} warning${scan.warning_count === 1 ? "" : "s"}`}
                    </p>
                    <p className="mt-1 text-sm text-muted">Scanned {new Date(scan.created_at).toLocaleString()}. Each critical issue costs 25 points and each warning 10.</p>
                  </div>
                  <ul className="flex flex-wrap gap-2">
                    {(["spf", "dkim", "dmarc", "mx"] as CheckName[]).map((c) => (
                      <li key={c} className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs font-semibold text-heading">
                        <StatusIcon status={scan.summary[c] ?? "none"} size={16} />{CHECK_LABEL[c]}
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="grid gap-6 xl:grid-cols-2">
                  {CHECKS.map((c) => <CheckCard key={c} name={c} result={scan.results[c]} />)}
                </div>
              </>
            ))}
            {tab === "tls" && <TlsHosts domain={domain} writable={writable} />}
            {tab === "history" && <History domainId={domain.id} />}
            {tab === "settings" && <Settings domain={domain} writable={writable} manager={!current?.is_demo && isManager(current?.role)} onChange={setDomain} />}
          </div>
        </>
      )}
    </>
  );
}
