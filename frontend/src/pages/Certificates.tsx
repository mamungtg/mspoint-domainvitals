import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import CertTable from "../components/CertTable";
import { ExpiryChart } from "../components/charts";
import { IconLock } from "../components/icons";
import { Alert, Button, Card, EmptyState, KpiTile, PageHeader, Spinner, Tabs } from "../components/ui";
import { CertRow, CertSummary } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

type Filter = "all" | "attention" | "healthy";

export default function Certificates() {
  const { current } = useWorkspace();
  const { data, error, reload } = useApi<{ summary: CertSummary; certificates: CertRow[] }>(current ? `/organizations/${current.id}/certificates/` : null);
  const [month, setMonth] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const pending = data?.certificates.some((c) => c.pending) ?? false;

  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => { void reload(); }, 4000);
    return () => clearInterval(t);
  }, [pending, reload]);

  const rows = useMemo(() => {
    if (!data) return [];
    let r = [...data.certificates].sort((a, b) => (a.days_left ?? 99999) - (b.days_left ?? 99999));
    if (month) r = r.filter((c) => c.not_after?.slice(0, 7) === month);
    if (filter === "attention") r = r.filter((c) => c.status === "fail" || c.status === "warn" || c.status === "error");
    if (filter === "healthy") r = r.filter((c) => c.status === "pass");
    return r;
  }, [data, month, filter]);

  if (error) return <><PageHeader title="SSL/TLS certificates" /><Alert>{error}</Alert></>;
  if (!data) return <Spinner />;
  const s = data.summary;
  const attention = data.certificates.filter((c) => c.status === "fail" || c.status === "warn" || c.status === "error").length;
  // Failing or unreachable for a reason other than expiry (name mismatch, untrusted chain, no connection).
  const other = data.certificates.filter((c) => (c.status === "fail" || c.status === "error") && (c.days_left === null || c.days_left > 7)).length;
  const monthName = month ? new Date(`${month}-01T00:00:00Z`).toLocaleDateString(undefined, { month: "long", year: "numeric", timeZone: "UTC" }) : null;

  return (
    <>
      <PageHeader title="SSL/TLS certificates"
        description={pending ? "Checking certificates now. Results appear here as each check finishes." : "Every HTTPS certificate on your verified domains, checked once a day."} />
      {s.total === 0 ? (
        <Card>
          <EmptyState icon={<IconLock />} title="No certificates checked yet"
            body="Each verified domain and its www host are checked automatically. Add a domain and publish its verification record to start."
            action={<Link to="/domains"><Button>Go to domains</Button></Link>} />
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <KpiTile label="Expired" value={s.expired} tone={s.expired ? "fail" : "neutral"} sub="Visitors see a warning" />
            <KpiTile label="Expire within 7 days" value={s.within_7} tone={s.within_7 ? "fail" : "neutral"} sub="Renew now" />
            <KpiTile label="Expire within 30 days" value={s.within_30} tone={s.within_30 ? "warn" : "neutral"} sub="Check auto-renewal" />
            <KpiTile label="Other problems" value={other} tone={other ? "fail" : "neutral"} sub="Name, chain or connection" />
            <KpiTile label="Healthy" value={s.healthy} tone="pass" sub={`of ${s.total} host names`} />
          </div>

          <Card title="Expiry calendar" description="Certificates expiring each month for the next 12 months. Select a month to filter the list."
            actions={month && <Button variant="ghost" size="sm" onClick={() => setMonth(null)}>Show all months</Button>}>
            <ExpiryChart months={s.by_month} selected={month} onSelect={setMonth} />
          </Card>

          <Card padded={false} title={monthName ? `Expiring in ${monthName}` : "All certificates"}
            description={`${rows.length} host name${rows.length === 1 ? "" : "s"}, soonest expiry first`}>
            <div className="px-5 pt-3">
              <Tabs value={filter} onChange={setFilter} items={[
                { id: "all", label: "All", count: data.certificates.length },
                { id: "attention", label: "Need attention", count: attention },
                { id: "healthy", label: "Healthy", count: s.healthy },
              ]} />
            </div>
            <CertTable rows={rows} empty="No certificates match this filter." />
          </Card>
        </div>
      )}
    </>
  );
}
