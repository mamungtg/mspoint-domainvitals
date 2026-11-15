import { useState } from "react";
import { Link } from "react-router-dom";
import { DmarcKpis, DomainStatusTable, PeriodSwitch, SenderTable, VolumeCard } from "../components/Dmarc";
import { IconFile } from "../components/icons";
import { Alert, Button, Card, EmptyState, PageHeader, Spinner } from "../components/ui";
import { OrgDmarc } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

export default function DmarcReports() {
  const { current } = useWorkspace();
  const [days, setDays] = useState(30);
  const { data, error } = useApi<OrgDmarc>(current ? `/organizations/${current.id}/dmarc/?days=${days}` : null);

  const header = (
    <PageHeader title="DMARC reports"
      description="Who sends mail using your domains, and whether that mail passes SPF, DKIM and DMARC."
      actions={<PeriodSwitch value={days} onChange={setDays} />} />
  );
  if (error) return <>{header}<Alert>{error}</Alert></>;
  if (!data) return <>{header}<Spinner /></>;

  if (data.domains.length === 0) {
    return (
      <>{header}
        <Card><EmptyState icon={<IconFile />} title="No verified domains yet"
          body="DMARC reports are collected for verified domains. Add a domain and publish its verification record first."
          action={<Link to="/domains"><Button>Go to domains</Button></Link>} /></Card>
      </>
    );
  }

  const notSetUp = data.domains.filter((d) => d.status !== "receiving").length;
  return (
    <>
      {header}
      <div className="space-y-6">
        {data.totals.messages === 0 && (
          <Alert tone="info">No reports in this period yet. Use “Set up” below to send your domains' reports to DomainVitals.</Alert>
        )}
        <DmarcKpis s={data} />
        <VolumeCard s={data} />
        <Card padded={false} title="Sending services"
          description="Every server that sent mail as your domains. Unrecognised services that fail DMARC are usually spoofing.">
          <SenderTable senders={data.senders} />
        </Card>
        <Card padded={false} title="Domains"
          description={notSetUp ? `${notSetUp} of ${data.domains.length} domains are not sending reports to DomainVitals yet.` : "All verified domains are sending reports."}>
          <DomainStatusTable rows={data.domains} rua={data.rua_address} />
        </Card>
      </div>
    </>
  );
}
