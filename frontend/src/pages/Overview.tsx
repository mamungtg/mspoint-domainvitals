import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { DaysLeft } from "../components/CertTable";
import { ChangeDiff } from "../components/DnsRecords";
import { ExpiryChart, Legend, ScoreLineChart, Segment, StackedBar } from "../components/charts";
import { IconGlobe, IconPlus } from "../components/icons";
import { Alert, Badge, Button, Card, EmptyState, KpiTile, linkCls, PageHeader, ScoreRing, Spinner, StatusPill, timeAgo } from "../components/ui";
import { api, canWrite, CHECK_LABEL, CheckName, errorText, Organization, Overview as OverviewData } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

const day = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });

function SampleDataButton() {
  const { reload, select, orgs } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const demo = orgs.find((o) => o.is_demo);
  const open = async () => {
    if (demo) { select(demo.id); return; }
    setBusy(true);
    try { const o = await api<Organization>("/organizations/demo/", { method: "POST" }); await reload(); select(o.id); }
    catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  };
  return <>{err && <Alert>{err}</Alert>}<Button variant="secondary" busy={busy} onClick={open}>Explore sample data</Button></>;
}

export default function Overview() {
  const { current } = useWorkspace();
  const navigate = useNavigate();
  const { data, error, loading } = useApi<OverviewData>(current ? `/organizations/${current.id}/overview/` : null);
  const writable = canWrite(current);

  const header = (
    <PageHeader title="Overview" description={`Domain health across ${current?.name ?? "this workspace"}.`}
      actions={writable && <Button onClick={() => navigate("/domains?add=1")}><IconPlus />Add domain</Button>} />
  );
  if (error) return <>{header}<Alert>{error}</Alert></>;
  if (loading || !data) return <>{header}<Spinner /></>;

  if (data.domains.total === 0) {
    return (
      <>{header}
        <Card>
          <EmptyState icon={<IconGlobe />} title="Add the first domain you look after"
            body="DomainVitals checks SPF, DKIM, DMARC and MX every day and tells you what to fix. You can also look around a workspace with sample domains first."
            action={<div className="flex flex-wrap justify-center gap-3">
              {writable && <Button onClick={() => navigate("/domains?add=1")}><IconPlus />Add domain</Button>}
              <SampleDataButton />
            </div>} />
        </Card>
      </>
    );
  }

  const policySegs: Segment[] = [
    { label: "Reject", value: data.dmarc_policies.reject, tone: "pass" },
    { label: "Quarantine", value: data.dmarc_policies.quarantine, tone: "brand" },
    { label: "None", value: data.dmarc_policies.none, tone: "warn" },
    { label: "Missing", value: data.dmarc_policies.missing, tone: "fail" },
  ];
  const enforced = data.dmarc_policies.reject + data.dmarc_policies.quarantine;
  const trend = data.score_trend.map((p) => ({ label: day(p.date), value: p.score }));

  return (
    <>
      {header}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <div className="col-span-2 flex items-center gap-4 rounded-lg border border-line bg-surface px-5 py-4 lg:col-span-1">
          <ScoreRing score={data.health.average_score} size={72} label="Average health score" />
          <div><p className="text-[13px] font-medium text-muted">Average health</p><p className="text-xs text-muted">out of 100</p></div>
        </div>
        <KpiTile label="Domains monitored" value={data.domains.verified} sub={data.domains.unverified ? `${data.domains.unverified} waiting for verification` : `of ${data.domains.total} added`} />
        <KpiTile label="Healthy" value={data.health.pass} sub="all checks pass" tone="pass" />
        <KpiTile label="Need attention" value={data.health.warn} sub={`${data.issues.warning} warnings`} tone="warn" />
        <KpiTile label="Failing" value={data.health.fail} sub={`${data.issues.critical} critical issues`} tone="fail" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="Health score, last 14 days" description="Average of every monitored domain's daily scan" className="lg:col-span-2">
          <ScoreLineChart points={trend} />
        </Card>
        <Card title="DMARC enforcement" description={`${enforced} of ${data.domains.scanned} domains reject or quarantine spoofed mail`}>
          <StackedBar segments={policySegs} label="DMARC policies" />
          <div className="mt-3"><Legend segments={policySegs} /></div>
          <div className="mt-6 space-y-3">
            {(Object.keys(data.checks) as CheckName[]).map((c) => {
              const segs: Segment[] = [
                { label: "Pass", value: data.checks[c].pass ?? 0, tone: "pass" },
                { label: "Warning", value: data.checks[c].warn ?? 0, tone: "warn" },
                { label: "Fail", value: data.checks[c].fail ?? 0, tone: "fail" },
              ];
              return (
                <div key={c} className="grid grid-cols-[3.5rem_1fr_auto] items-center gap-3 text-sm">
                  <span className="font-display font-semibold text-heading">{CHECK_LABEL[c]}</span>
                  <StackedBar segments={segs} label={`${CHECK_LABEL[c]} results`} />
                  <span className="w-12 text-right text-xs text-muted tabular-nums">{segs[0].value}/{data.domains.scanned}</span>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {data.tls.total > 0 && (
        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <Card title="Certificate expiry, next 12 months" className="lg:col-span-2"
            description={`${data.tls.expired + data.tls.within_7} need renewal now, ${data.tls.within_30} within 30 days`}
            actions={<Link to="/reports/tls" className={`${linkCls} text-sm`}>All certificates</Link>}>
            <ExpiryChart months={data.tls.by_month} selected={null} onSelect={() => navigate("/reports/tls")} />
          </Card>
          <Card title="Expiring first" padded={false}>
            <ul className="divide-y divide-line">
              {data.tls.soonest.map((c) => (
                <li key={c.id}>
                  <Link to={`/domains/${c.domain_id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-subtle">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-heading">{c.label}</span>
                      <span className="block truncate text-xs text-muted">{c.issuer ?? "Unknown issuer"}</span>
                    </span>
                    <span className="text-sm"><DaysLeft days={c.days_left} /></span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}

      {data.recent_changes.length > 0 && (
        <div className="mt-6">
          <Card title="Recent DNS changes" description="Record sets that changed between scans across your domains" padded={false}>
            <ul className="divide-y divide-line">
              {data.recent_changes.map((c) => (
                <li key={c.id}>
                  <Link to={`/domains/${c.domain_id}?tab=records`} className="grid gap-1.5 px-5 py-3 hover:bg-subtle sm:grid-cols-[minmax(0,16rem)_1fr_auto] sm:items-start sm:gap-4">
                    <span className="min-w-0">
                      <span className="flex items-center gap-2"><Badge>{c.rtype}</Badge><span className="truncate text-sm font-medium text-heading">{c.name === c.domain ? "@" : c.name.replace(`.${c.domain}`, "")}</span></span>
                      <span className="mt-0.5 block text-xs text-muted">{c.domain}</span>
                    </span>
                    <span className="min-w-0"><ChangeDiff c={c} /></span>
                    <span className="text-xs text-muted sm:text-right">{timeAgo(c.detected_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card title="Domains that need attention" padded={false}
          actions={<Link to="/domains" className={`${linkCls} text-sm`}>All domains</Link>}>
          {data.attention.length === 0 ? <p className="px-5 py-6 text-sm text-muted">Every monitored domain passes all checks.</p> : (
            <ul className="divide-y divide-line">
              {data.attention.map((a) => (
                <li key={a.domain_id}>
                  <Link to={`/domains/${a.domain_id}`} className="flex items-center gap-4 px-5 py-3 hover:bg-subtle">
                    <ScoreRing score={a.score} size={40} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-heading">{a.domain}</span>
                      <span className="block truncate text-xs text-muted">{a.top_finding}</span>
                    </span>
                    <StatusPill status={a.status === "fail" ? "fail" : "warn"} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Open issues" description="Critical first" padded={false}>
          {data.findings.length === 0 ? <p className="px-5 py-6 text-sm text-muted">No open issues.</p> : (
            <ul className="divide-y divide-line">
              {data.findings.map((f, i) => (
                <li key={i}>
                  <Link to={`/domains/${f.domain_id}`} className="flex items-start gap-3 px-5 py-3 hover:bg-subtle">
                    <Badge tone={f.severity === "critical" ? "fail" : "warn"}>{f.severity === "critical" ? "Critical" : "Warning"}</Badge>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-heading">{f.title}</span>
                      <span className="block truncate text-xs text-muted">{f.domain} · {CHECK_LABEL[f.check]}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
