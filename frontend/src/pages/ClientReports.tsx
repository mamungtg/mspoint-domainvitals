import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { IconDownload } from "../components/icons";
import { Alert, Button, Card, Field, Input, PageHeader, Select, Spinner } from "../components/ui";
import { api, ApiError, Domain, errorText, FieldErrors, isManager } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

type Branding = { company_name: string; accent_color: string; footer_text: string; has_logo: boolean; white_label: boolean };
type Schedule = { enabled: boolean; recipients: string[]; last_sent_on: string | null };

export default function ClientReports() {
  const { current } = useWorkspace();
  const manager = !!current && !current.is_demo && isManager(current.role);
  return (
    <>
      <PageHeader title="Client reports" description="PDF reports on domain health, certificates and DMARC, with your own branding, to download or send every month." />
      {!current ? <Spinner /> : (
        <div className="space-y-6">
          <Generate orgId={current.id} />
          <BrandingCard orgId={current.id} manager={manager} demo={current.is_demo} />
          <ScheduleCard orgId={current.id} manager={manager} />
        </div>
      )}
    </>
  );
}

function Generate({ orgId }: { orgId: string }) {
  const { data } = useApi<Domain[]>(`/organizations/${orgId}/domains/`);
  const [domain, setDomain] = useState("");
  const [days, setDays] = useState("30");
  const verified = (data ?? []).filter((d) => d.is_verified);
  const href = `/api/v1/organizations/${orgId}/reports/pdf/?days=${days}${domain ? `&domain=${domain}` : ""}`;
  return (
    <Card title="Download a report" description="A summary page for all domains, then a page per domain with its score trend, problems and how to fix them, certificates, DMARC results and DNS changes.">
      <div className="grid gap-4 md:grid-cols-[1fr_12rem_auto] md:items-end">
        <Field label="Domains">
          <Select value={domain} onChange={(e) => setDomain(e.target.value)}>
            <option value="">All verified domains ({verified.length})</option>
            {verified.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </Select>
        </Field>
        <Field label="Period">
          <Select value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="30">Last 30 days</option><option value="90">Last 90 days</option>
          </Select>
        </Field>
        {verified.length > 0 ? (
          <a href={href} download className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-orange-500 px-4 text-sm font-semibold text-navy-950 hover:bg-orange-600">
            <IconDownload />Download PDF
          </a>
        ) : <Button disabled><IconDownload />Download PDF</Button>}
      </div>
      {data && verified.length === 0 && <div className="mt-4"><Alert tone="info">Verify a domain first; reports cover verified domains.</Alert></div>}
    </Card>
  );
}

function BrandingCard({ orgId, manager, demo }: { orgId: string; manager: boolean; demo: boolean }) {
  const { data, reload } = useApi<Branding>(`/organizations/${orgId}/reports/branding/`);
  const [form, setForm] = useState({ company_name: "", accent_color: "#14508F", footer_text: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState("");
  const [logoVersion, setLogoVersion] = useState(0);
  useEffect(() => { if (data) setForm({ company_name: data.company_name, accent_color: data.accent_color, footer_text: data.footer_text }); }, [data]);
  if (!data) return <Card title="Branding"><Spinner /></Card>;
  const locked = !data.white_label;
  const editable = manager && !locked;

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy("save"); setErrors({}); setMsg(null);
    try { await api(`/organizations/${orgId}/reports/branding/`, { method: "PATCH", json: form }); setMsg({ tone: "success", text: "Branding saved. New reports use it straight away." }); void reload(); }
    catch (err) { const d = (err as ApiError).details; if (d) setErrors(d); else setMsg({ tone: "error", text: errorText(err) }); }
    finally { setBusy(""); }
  }
  async function upload(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    setBusy("logo"); setMsg(null);
    const body = new FormData(); body.append("file", f);
    try { await api(`/organizations/${orgId}/reports/branding/logo/`, { method: "POST", body }); setLogoVersion((v) => v + 1); void reload(); }
    catch (err) { setMsg({ tone: "error", text: (err as ApiError).details?.file?.[0] ?? errorText(err) }); }
    finally { setBusy(""); }
  }
  async function removeLogo() {
    setBusy("remove");
    try { await api(`/organizations/${orgId}/reports/branding/logo/`, { method: "DELETE" }); void reload(); } finally { setBusy(""); }
  }

  return (
    <Card title="White-label branding" description="Your logo, company name and colour on every page, so reports go to clients under your name.">
      {demo && <div className="mb-5"><Alert tone="info">Branding can't be changed in the sample workspace. Switch to your own workspace to add your logo.</Alert></div>}
      {locked && !demo && (
        <div className="mb-5"><Alert tone="info">
          White-label reports are included in the Agency, MSP and Enterprise plans. Reports on this plan carry DomainVitals branding.{" "}
          <Link to="/settings/billing" className="font-semibold underline">See plans</Link>
        </Alert></div>
      )}
      <form onSubmit={save} className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="space-y-4">
          <Field label="Company name" error={errors.company_name?.[0]}>
            <Input value={form.company_name} disabled={!editable} maxLength={80} placeholder="Acme IT Services" onChange={(e) => setForm({ ...form, company_name: e.target.value })} />
          </Field>
          <Field label="Brand colour" error={errors.accent_color?.[0]} hint="Used for headings, the page band and charts">
            <div className="flex gap-2">
              <input type="color" aria-label="Pick colour" disabled={!editable} value={/^#[0-9a-f]{6}$/i.test(form.accent_color) ? form.accent_color : "#14508F"}
                onChange={(e) => setForm({ ...form, accent_color: e.target.value.toUpperCase() })} className="h-10 w-12 cursor-pointer rounded-md border border-line bg-surface p-1 disabled:cursor-not-allowed" />
              <Input value={form.accent_color} disabled={!editable} maxLength={7} onChange={(e) => setForm({ ...form, accent_color: e.target.value })} />
            </div>
          </Field>
          <Field label="Footer" error={errors.footer_text?.[0]} hint="Shown at the bottom of every page, e.g. your support address and phone">
            <Input value={form.footer_text} disabled={!editable} maxLength={200} placeholder="support@acme-it.com · +1 555 0100" onChange={(e) => setForm({ ...form, footer_text: e.target.value })} />
          </Field>
          {editable && <Button type="submit" busy={busy === "save"}>Save branding</Button>}
        </div>
        <div>
          <p className="mb-1.5 text-sm font-medium text-heading">Logo</p>
          <div className="flex h-28 items-center justify-center rounded-md border border-dashed border-line bg-white p-3">
            {data.has_logo
              ? <img src={`/api/v1/organizations/${orgId}/reports/branding/logo/?v=${logoVersion}`} alt="Report logo" className="max-h-full max-w-full object-contain" />
              : <span className="text-sm text-muted">No logo</span>}
          </div>
          <p className="mt-1.5 text-xs text-muted">PNG or JPEG, up to 1 MB. A wide logo on a transparent background looks best.</p>
          {editable && (
            <div className="mt-3 flex flex-wrap gap-2">
              <label className="inline-flex cursor-pointer items-center rounded-md border border-line px-3 py-1.5 text-sm font-medium text-heading hover:bg-subtle">
                {busy === "logo" ? "Uploading…" : data.has_logo ? "Replace logo" : "Upload logo"}
                <input type="file" accept="image/png,image/jpeg" className="sr-only" onChange={upload} />
              </label>
              {data.has_logo && <Button type="button" size="sm" variant="ghost" busy={busy === "remove"} onClick={removeLogo}>Remove</Button>}
            </div>
          )}
        </div>
      </form>
      {msg && <div className="mt-4"><Alert tone={msg.tone}>{msg.text}</Alert></div>}
    </Card>
  );
}

function ScheduleCard({ orgId, manager }: { orgId: string; manager: boolean }) {
  const { data, reload } = useApi<Schedule>(`/organizations/${orgId}/reports/schedule/`);
  const [enabled, setEnabled] = useState(false);
  const [recipients, setRecipients] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) { setEnabled(data.enabled); setRecipients(data.recipients.join(", ")); } }, [data]);
  if (!data) return <Card title="Monthly report"><Spinner /></Card>;

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setOk(false);
    try {
      await api(`/organizations/${orgId}/reports/schedule/`, { method: "PUT", json: { enabled, recipients: recipients.split(/[\s,;]+/).filter(Boolean) } });
      setOk(true); void reload();
    } catch (err) { const d = (err as ApiError).details; setError(d?.recipients?.[0] ?? d?.non_field_errors?.[0] ?? errorText(err)); }
    finally { setBusy(false); }
  }
  return (
    <Card title="Monthly report by mail" description="On the 1st of each month, the report for all verified domains (last 30 days) is mailed as a PDF attachment.">
      <form onSubmit={save} className="space-y-4">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" className="h-4 w-4 accent-[#14508f]" checked={enabled} disabled={!manager} onChange={(e) => setEnabled(e.target.checked)} />
          Send the monthly report
        </label>
        <Field label="Recipients" hint="Up to 10 addresses, separated by commas">
          <Input value={recipients} disabled={!manager} onChange={(e) => setRecipients(e.target.value)} placeholder="it@client.com, you@yourcompany.com" />
        </Field>
        {data.last_sent_on && <p className="text-sm text-muted">Last sent {new Date(data.last_sent_on).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}.</p>}
        {error && <Alert>{error}</Alert>}
        {ok && <Alert tone="success">Saved.</Alert>}
        {manager && <Button type="submit" busy={busy}>Save</Button>}
      </form>
    </Card>
  );
}
