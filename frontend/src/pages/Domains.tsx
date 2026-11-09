import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { IconChevron, IconGlobe, IconPlus, IconSearch } from "../components/icons";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, ScoreBar, Spinner, StatusIcon, Tabs, timeAgo } from "../components/ui";
import { api, ApiError, canWrite, CHECK_LABEL, CheckName, Domain, errorText } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

type Filter = "all" | "fail" | "warn" | "pass" | "unverified";
const CHECKS: CheckName[] = ["spf", "dkim", "dmarc", "mx", "dns"];

function bucket(d: Domain): Filter {
  if (!d.is_verified) return "unverified";
  const s = d.latest_scan?.overall_status;
  return s === "fail" ? "fail" : s === "warn" ? "warn" : s === "pass" ? "pass" : "all";
}

function AddDomainModal({ open, onClose, orgId }: { open: boolean; onClose: () => void; orgId: string }) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e?: FormEvent) => {
    e?.preventDefault();
    setBusy(true); setError("");
    try {
      const d = await api<Domain>(`/organizations/${orgId}/domains/`, { method: "POST", json: { name } });
      onClose(); navigate(`/domains/${d.id}`);
    } catch (err) {
      setError((err as ApiError).details?.name?.[0] ?? errorText(err));
    } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Add a domain"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button busy={busy} disabled={!name.trim()} onClick={() => submit()}>Add domain</Button></>}>
      <form onSubmit={submit} noValidate>
        <Field label="Domain name" hint="The domain used in mail addresses, for example clientname.com. You will verify ownership next." error={error}>
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="clientname.com" autoComplete="off" spellCheck={false} />
        </Field>
      </form>
    </Modal>
  );
}

export default function Domains() {
  const { current } = useWorkspace();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const { data, error } = useApi<Domain[]>(current ? `/organizations/${current.id}/domains/` : null);
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const writable = canWrite(current);
  const adding = params.get("add") === "1" && writable;
  const setAdding = (v: boolean) => { const p = new URLSearchParams(params); if (v) p.set("add", "1"); else p.delete("add"); setParams(p, { replace: true }); };

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: 0, fail: 0, warn: 0, pass: 0, unverified: 0 };
    (data ?? []).forEach((d) => { c.all++; const b = bucket(d); if (b !== "all") c[b]++; });
    return c;
  }, [data]);
  const rows = (data ?? []).filter((d) => (filter === "all" || bucket(d) === filter) && d.name.includes(q.trim().toLowerCase()));

  const addBtn = writable && <Button onClick={() => setAdding(true)} disabled={!user?.email_verified}
    title={user?.email_verified ? undefined : "Confirm your email address first"}><IconPlus />Add domain</Button>;

  return (
    <>
      <PageHeader title="Domains" description="Every domain this workspace monitors, with its latest scan." actions={addBtn} />
      {error && <Alert>{error}</Alert>}
      {!data && !error && <Spinner />}
      {data && data.length === 0 && (
        <Card><EmptyState icon={<IconGlobe />} title="No domains yet"
          body={writable ? "Add a domain, publish one TXT record to prove you control it, and the first scan runs straight away." : "Owners, admins and members can add domains to this workspace."}
          action={addBtn} /></Card>
      )}
      {data && data.length > 0 && (
        <Card padded={false}>
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 pt-3">
            <Tabs value={filter} onChange={setFilter} items={[
              { id: "all", label: "All", count: counts.all }, { id: "fail", label: "Failing", count: counts.fail },
              { id: "warn", label: "Warnings", count: counts.warn }, { id: "pass", label: "Healthy", count: counts.pass },
              { id: "unverified", label: "Unverified", count: counts.unverified }]} />
            <label className="relative mb-2 w-full sm:w-64">
              <span className="sr-only">Search domains</span>
              <span className="pointer-events-none absolute left-2.5 top-2.5 text-muted"><IconSearch /></span>
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search domains" className="pl-9" />
            </label>
          </div>
          <div className="relative overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-y border-line bg-subtle text-left text-xs font-medium text-muted">
                  <th className="px-5 py-2.5 font-medium">Domain</th>
                  <th className="px-3 py-2.5 font-medium">Health</th>
                  {CHECKS.map((c) => <th key={c} className="px-3 py-2.5 text-center font-medium">{CHECK_LABEL[c]}</th>)}
                  <th className="px-3 py-2.5 font-medium">Last scan</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((d) => (
                  <tr key={d.id} onClick={() => navigate(`/domains/${d.id}`)} className="cursor-pointer hover:bg-subtle">
                    <td className="px-5 py-3">
                      <Link to={`/domains/${d.id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-heading hover:underline">{d.name}</Link>
                      {!d.is_verified && <span className="ml-2"><Badge tone="warn">Not verified</Badge></span>}
                      {d.is_verified && !d.monitoring_enabled && <span className="ml-2"><Badge>Paused</Badge></span>}
                    </td>
                    <td className="px-3 py-3">{d.is_verified ? <ScoreBar score={d.latest_scan?.health_score} /> : <span className="text-xs text-muted">Waiting for verification</span>}</td>
                    {CHECKS.map((c) => (
                      <td key={c} className="px-3 py-3 text-center">
                        <span className="inline-flex" title={`${CHECK_LABEL[c]}: ${d.latest_scan?.summary[c] ?? "not checked"}`}>
                          <StatusIcon status={d.latest_scan?.summary[c] ?? "none"} />
                        </span>
                      </td>
                    ))}
                    <td className="whitespace-nowrap px-3 py-3 text-muted">{timeAgo(d.latest_scan?.completed_at)}</td>
                    <td className="pr-4 text-muted" aria-hidden="true"><IconChevron /></td>
                  </tr>
                ))}
                {rows.length === 0 && <tr><td colSpan={8} className="px-5 py-8 text-center text-muted">No domains match this view.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {current && <AddDomainModal open={adding} onClose={() => setAdding(false)} orgId={current.id} />}
    </>
  );
}
