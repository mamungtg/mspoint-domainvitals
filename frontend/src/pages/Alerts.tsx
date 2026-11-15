import { FormEvent, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { IconBell, IconPlus } from "../components/icons";
import {
  Alert as Notice, Badge, Button, Card, CopyField, EmptyState, Field, Input, Modal, PageHeader, Select, Spinner, StatusIcon, Tabs, timeAgo,
} from "../components/ui";
import {
  ALERT_KIND_LABEL, AlertChannel, AlertItem, AlertKind, AlertList, api, ApiError, canWrite, ChannelType, errorText, FieldErrors, isManager,
} from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

type Tab = "open" | "notice" | "resolved" | "channels";
const SEV = { critical: "fail", warning: "warn", info: "none" } as const;
const KINDS = Object.keys(ALERT_KIND_LABEL) as AlertKind[];
const TYPE_LABEL: Record<ChannelType, string> = { email: "Email", slack: "Slack", teams: "Microsoft Teams", webhook: "Webhook" };

export default function Alerts() {
  const { current } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const tab = (["open", "notice", "resolved", "channels"].includes(params.get("tab") ?? "") ? params.get("tab") : "open") as Tab;
  const setTab = (t: Tab) => setParams(t === "open" ? {} : { tab: t }, { replace: true });
  const status = tab === "channels" ? "open" : tab;
  const { data, error, reload } = useApi<AlertList>(current ? `/organizations/${current.id}/alerts/?status=${status}` : null);

  return (
    <>
      <PageHeader title="Alerts" description="Problems that need someone to act, and what changed across your domains." />
      <div className="mb-6">
        <Tabs value={tab} onChange={setTab} items={[
          { id: "open", label: "Open", count: data?.counts.open },
          { id: "notice", label: "Activity" },
          { id: "resolved", label: "Resolved" },
          { id: "channels", label: "Notification channels" },
        ]} />
      </div>
      {tab === "channels" ? <Channels /> : error ? <Notice>{error}</Notice> : !data ? <Spinner /> : (
        <AlertListView items={data.alerts} tab={tab} writable={canWrite(current)} onChange={() => { void reload(); }} />
      )}
    </>
  );
}

function AlertListView({ items, tab, writable, onChange }: { items: AlertItem[]; tab: Tab; writable: boolean; onChange: () => void }) {
  if (!items.length) {
    const empty = {
      open: ["Nothing needs attention", "Failing checks and certificate problems show up here until they are fixed."],
      notice: ["No activity yet", "DNS record changes and new unauthenticated DMARC senders are listed here."],
      resolved: ["Nothing resolved yet", "Problems move here once a scan finds them fixed."],
    }[tab as "open" | "notice" | "resolved"];
    return <Card><EmptyState icon={<IconBell />} title={empty[0]} body={empty[1]} /></Card>;
  }
  return (
    <Card padded={false}>
      <ul className="divide-y divide-line">
        {items.map((a) => <AlertRow key={a.id} a={a} writable={writable && tab === "open"} onChange={onChange} />)}
      </ul>
    </Card>
  );
}

function AlertRow({ a, writable, onChange }: { a: AlertItem; writable: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  async function ack() {
    setBusy(true); setErr("");
    try { await api(`/alerts/${a.id}/acknowledge/`, { method: "POST" }); onChange(); }
    catch (e) { setErr(errorText(e)); } finally { setBusy(false); }
  }
  const tab = { certificate: "tls", dns_change: "records", dmarc_sender: "dmarc", check: "results" }[a.kind];
  return (
    <li className="flex gap-3 px-5 py-4">
      <span className="mt-0.5 shrink-0">{a.status === "resolved" ? <StatusIcon status="pass" size={18} /> : <StatusIcon status={SEV[a.severity]} size={18} />}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="font-medium text-heading">{a.title}</p>
          <Badge>{ALERT_KIND_LABEL[a.kind]}</Badge>
          {a.status === "open" && a.severity === "critical" && <Badge tone="fail">Critical</Badge>}
        </div>
        {a.detail && <p className="mt-1.5 whitespace-pre-line text-sm text-ink">{a.detail}</p>}
        <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
          {a.domain && <Link className="font-medium text-link hover:underline" to={`/domains/${a.domain}?tab=${tab}`}>{a.domain_name}</Link>}
          <span>{a.status === "resolved" ? `Resolved ${timeAgo(a.resolved_at).toLowerCase()}` : `${a.status === "notice" ? "" : "Opened "}${timeAgo(a.opened_at).toLowerCase()}`}</span>
          {a.acknowledged_by && <span>Acknowledged by {a.acknowledged_by}</span>}
        </p>
        {err && <div className="mt-2"><Notice>{err}</Notice></div>}
      </div>
      {writable && !a.acknowledged_at && (
        <div className="shrink-0"><Button size="sm" variant="secondary" busy={busy} onClick={ack}>Acknowledge</Button></div>
      )}
    </li>
  );
}

/* ---------- Notification channels ---------- */

function Channels() {
  const { current } = useWorkspace();
  const manager = !current?.is_demo && isManager(current?.role);
  const { data, error, reload } = useApi<AlertChannel[]>(current ? `/organizations/${current.id}/alert-channels/` : null);
  const [editing, setEditing] = useState<AlertChannel | "new" | null>(null);
  if (error) return <Notice>{error}</Notice>;
  if (!data) return <Spinner />;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">Each channel chooses which events it receives. A problem notifies when it opens, when it becomes critical and when it is resolved; it does not repeat while it stays open.</p>
        {manager && <Button onClick={() => setEditing("new")}><IconPlus />Add channel</Button>}
      </div>
      {current?.is_demo && <Notice tone="info">Channels are not available in the sample workspace.</Notice>}
      {!current?.is_demo && data.length === 0 && (
        <Card><EmptyState icon={<IconBell />} title="No notification channels" body="Nobody is notified about problems. Add an email, Slack, Teams or webhook channel." /></Card>
      )}
      {data.map((c) => <ChannelCard key={c.id} c={c} manager={manager} onEdit={() => setEditing(c)} onChange={() => { void reload(); }} />)}
      {editing && current && (
        <ChannelForm orgId={current.id} channel={editing === "new" ? null : editing}
          onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void reload(); }} />
      )}
    </div>
  );
}

function ChannelCard({ c, manager, onEdit, onChange }: { c: AlertChannel; manager: boolean; onEdit: () => void; onChange: () => void }) {
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  async function run(kind: string, fn: () => Promise<void>) {
    setBusy(kind); setMsg(null);
    try { await fn(); } catch (e) { setMsg({ tone: "error", text: errorText(e) }); } finally { setBusy(""); }
  }
  const test = () => run("test", async () => {
    const r = await api<{ sent: boolean; error: string }>(`/alert-channels/${c.id}/test/`, { method: "POST" });
    setMsg(r.sent ? { tone: "success", text: "Test sent. Check that it arrived." } : { tone: "error", text: r.error || "The test could not be sent." });
    onChange();
  });
  const toggle = () => run("toggle", async () => { await api(`/alert-channels/${c.id}/`, { method: "PATCH", json: { enabled: !c.enabled } }); onChange(); });
  const remove = () => run("delete", async () => {
    if (!window.confirm(`Delete the "${c.name}" channel?`)) return;
    await api(`/alert-channels/${c.id}/`, { method: "DELETE" }); onChange();
  });
  const target = c.type === "email"
    ? [c.notify_managers && "Owners and admins", ...c.recipients].filter(Boolean).join(", ")
    : c.url.replace(/^https:\/\//, "").replace(/(\/[^/]{0,12})[^/]*$/, "$1…");
  return (
    <Card>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display font-semibold text-heading">{c.name}</p>
            <Badge tone="brand">{TYPE_LABEL[c.type]}</Badge>
            {!c.enabled && <Badge>Paused</Badge>}
          </div>
          <p className="mt-1 truncate text-sm text-muted">{target}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {c.events.map((e) => <Badge key={e}>{ALERT_KIND_LABEL[e]}</Badge>)}
            <Badge>{c.min_severity === "critical" ? "Critical problems only" : "Warnings and critical"}</Badge>
          </div>
          <p className="mt-3 text-xs text-muted">
            {c.last_error ? <span className="text-fail">Last delivery failed: {c.last_error}</span>
              : c.last_sent_at ? `Last sent ${timeAgo(c.last_sent_at).toLowerCase()}` : "Nothing sent yet"}
          </p>
        </div>
        {manager && (
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button size="sm" variant="secondary" busy={busy === "test"} onClick={test}>Send test</Button>
            <Button size="sm" variant="ghost" onClick={onEdit}>Edit</Button>
            <Button size="sm" variant="ghost" busy={busy === "toggle"} onClick={toggle}>{c.enabled ? "Pause" : "Resume"}</Button>
            <Button size="sm" variant="ghost" busy={busy === "delete"} onClick={remove}>Delete</Button>
          </div>
        )}
      </div>
      {manager && c.type === "webhook" && c.secret && (
        <div className="mt-4"><CopyField label="Signing secret (verify the X-DomainVitals-Signature header: HMAC-SHA256 of the body)" value={c.secret} /></div>
      )}
      {msg && <div className="mt-4"><Notice tone={msg.tone}>{msg.text}</Notice></div>}
    </Card>
  );
}

const URL_HELP: Record<Exclude<ChannelType, "email">, string> = {
  slack: "In Slack: Apps → Incoming Webhooks → Add to a channel, then paste the https://hooks.slack.com/… URL.",
  teams: "In Teams: channel → Workflows → “Post to a channel when a webhook request is received”, then paste the URL it gives you.",
  webhook: "We POST JSON to this https URL and sign each request with HMAC-SHA256 (header X-DomainVitals-Signature).",
};

function ChannelForm({ orgId, channel, onClose, onSaved }: { orgId: string; channel: AlertChannel | null; onClose: () => void; onSaved: () => void }) {
  const [type, setType] = useState<ChannelType>(channel?.type ?? "email");
  const [name, setName] = useState(channel?.name ?? TYPE_LABEL.email);
  const [url, setUrl] = useState(channel?.url ?? "");
  const [managers, setManagers] = useState(channel?.notify_managers ?? true);
  const [recipients, setRecipients] = useState((channel?.recipients ?? []).join(", "));
  const [events, setEvents] = useState<AlertKind[]>(channel?.events ?? KINDS);
  const [minSev, setMinSev] = useState(channel?.min_severity ?? "warning");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [error, setError] = useState("");

  // New channels are named after their type until the user types a name.
  const [autoName, setAutoName] = useState(!channel);
  useEffect(() => { if (autoName) setName(TYPE_LABEL[type]); }, [type, autoName]);

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErrors({}); setError("");
    const body = {
      type, name, events, min_severity: minSev,
      ...(type === "email" ? { notify_managers: managers, recipients: recipients.split(/[\s,;]+/).filter(Boolean) } : { url }),
    };
    try {
      if (channel) await api(`/alert-channels/${channel.id}/`, { method: "PATCH", json: body });
      else await api(`/organizations/${orgId}/alert-channels/`, { method: "POST", json: body });
      onSaved();
    } catch (err) {
      const d = (err as ApiError).details;
      if (d) setErrors(d); else setError(errorText(err));
    } finally { setBusy(false); }
  }
  const toggle = (k: AlertKind) => setEvents((ev) => (ev.includes(k) ? ev.filter((x) => x !== k) : [...ev, k]));

  return (
    <Modal open onClose={onClose} title={channel ? "Edit channel" : "Add notification channel"}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button type="submit" form="channel-form" busy={busy}>{channel ? "Save" : "Add channel"}</Button></>}>
      <form id="channel-form" onSubmit={save} className="space-y-4" noValidate>
        {!channel && (
          <Field label="Type">
            <Select value={type} onChange={(e) => setType(e.target.value as ChannelType)}>
              {(Object.keys(TYPE_LABEL) as ChannelType[]).map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
            </Select>
          </Field>
        )}
        <Field label="Name" error={errors.name?.[0]}><Input value={name} onChange={(e) => { setAutoName(false); setName(e.target.value); }} maxLength={80} /></Field>
        {type === "email" ? (
          <>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" className="h-4 w-4 accent-[#14508f]" checked={managers} onChange={(e) => setManagers(e.target.checked)} />
              All owners and admins of this workspace
            </label>
            <Field label="Other recipients" hint="Up to 10 addresses, separated by commas" error={errors.recipients?.[0]}>
              <Input value={recipients} onChange={(e) => setRecipients(e.target.value)} placeholder="it@client.com" />
            </Field>
          </>
        ) : (
          <Field label="Webhook URL" hint={URL_HELP[type]} error={errors.url?.[0]}>
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" spellCheck={false} />
          </Field>
        )}
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-heading">Send these events</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            {KINDS.map((k) => (
              <label key={k} className="flex items-center gap-2 text-sm text-ink">
                <input type="checkbox" className="h-4 w-4 accent-[#14508f]" checked={events.includes(k)} onChange={() => toggle(k)} />
                {ALERT_KIND_LABEL[k]}
              </label>
            ))}
          </div>
          {errors.events?.[0] && <p className="mt-1 text-sm text-fail">{errors.events[0]}</p>}
        </fieldset>
        <Field label="Problems to send" hint="Applies to failing checks and certificates">
          <Select value={minSev} onChange={(e) => setMinSev(e.target.value as "critical" | "warning")}>
            <option value="warning">Warnings and critical problems</option>
            <option value="critical">Critical problems only</option>
          </Select>
        </Field>
        {(errors.non_field_errors?.[0] || errors.detail?.[0] || error) && <Notice>{errors.non_field_errors?.[0] || errors.detail?.[0] || error}</Notice>}
      </form>
    </Modal>
  );
}
