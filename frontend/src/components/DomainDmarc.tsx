import { useState } from "react";
import { DomainDmarc as DomainDmarcData } from "../lib/api";
import { useApi } from "../lib/useApi";
import { DmarcKpis, PeriodSwitch, ReportList, SenderTable, SetupPanel, STATUS, UploadReport, VolumeCard } from "./Dmarc";
import { Alert, Card, Spinner, StatusPill } from "./ui";

export default function DomainDmarc({ domainId, writable }: { domainId: string; writable: boolean }) {
  const [days, setDays] = useState(30);
  const { data, error, reload } = useApi<DomainDmarcData>(`/domains/${domainId}/dmarc/?days=${days}`);
  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Card><Spinner /></Card>;
  if (!data.verified) return <Card><p className="text-muted">Verify this domain to collect its DMARC reports.</p></Card>;
  const st = STATUS[data.domain.status];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusPill status={st.tone} label={st.label} />
        <PeriodSwitch value={days} onChange={setDays} />
      </div>
      {data.domain.status !== "receiving" && (
        <Card title="Send reports to DomainVitals"><SetupPanel row={data.domain} rua={data.rua_address} /></Card>
      )}
      <DmarcKpis s={data} />
      <VolumeCard s={data} />
      <Card padded={false} title="Sending services" description="Servers that sent mail as this domain">
        <SenderTable senders={data.senders} />
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card padded={false} title="Recent reports" description="Aggregate reports received from mail providers">
          <ReportList reports={data.reports} />
        </Card>
        {writable && (
          <Card title="Import a report" description="Upload a report file (.xml, .gz or .zip) you received elsewhere. It must be for this domain.">
            <UploadReport domainId={domainId} onDone={() => { void reload(); }} />
          </Card>
        )}
      </div>
    </div>
  );
}
