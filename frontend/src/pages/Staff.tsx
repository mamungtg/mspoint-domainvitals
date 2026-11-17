import { ReactNode, useEffect, useState } from "react";
import { Link, Navigate, useParams, useSearchParams } from "react-router-dom";
import { Alert, Badge, Card, Input, KpiTile, PageHeader, Select, Spinner, Tabs, timeAgo } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/useApi";

type Billing = {
  plan: string; effective_plan: string; status: string; interval: string; trial_ends_at: string | null;
  current_period_end: string | null; cancel_at_period_end: boolean; stripe_customer_id: string; mrr: number;
};
type WorkspaceRow = {
  id: string; name: string; created_at: string; status: string; domains: number; verified_domains: number; members: number;
  last_login: string | null; owner: { email: string; full_name: string; email_verified: boolean }; billing: Billing;
};
type UserRow = {
  id: string; email: string; full_name: string; email_verified: boolean; is_staff: boolean; is_active: boolean;
  created_at: string; last_login: string | null; terms_version: string; workspaces: { id: string; name: string; role: string }[];
};
type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
type Overview = {
  users: number; users_unverified: number; signups_7d: number; signups_30d: number; workspaces: number; trialing: number;
  paying: number; past_due: number; paying_by_plan: Record<string, number>; mrr: number; domains: number; verified_domains: number;
  trials_ending_7d: { id: string; name: string; trial_ends_at: string }[];
};

const date = (s: string | null | undefined) => (s ? new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—");
const usd = (n: number) => n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const link = "font-medium text-link hover:underline";
const th = "px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted";
const td = "px-4 py-3 align-top";

export function StatusBadge({ b }: { b: Billing }) {
  const map: Record<string, [string, "pass" | "warn" | "fail" | "brand" | "neutral"]> = {
    active: ["Paying", "pass"], trialing: ["Trial", "brand"], past_due: ["Payment overdue", "fail"],
    trial_ended: ["Trial ended", "warn"], canceled: ["Canceled", "neutral"], free: ["Free", "neutral"],
  };
  const [label, tone] = map[b.status] ?? [b.status, "neutral"];
  return <Badge tone={tone}>{label}</Badge>;
}

function Table({ head, children, empty, min = 760 }: { head: string[]; children: ReactNode; empty: boolean; min?: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={{ minWidth: min }}>
        <thead className="border-b border-line bg-subtle"><tr>{head.map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
      {empty && <p className="px-4 py-10 text-center text-sm text-muted">Nothing matches.</p>}
    </div>
  );
}

function Pager({ page, count, setPage }: { page: number; count: number; setPage: (n: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / 25));
  if (pages <= 1) return null;
  return (
    <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm text-muted">
      <span>Page {page} of {pages} · {count} total</span>
      <span className="flex gap-2">
        <button className={link} disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <button className={link} disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
      </span>
    </div>
  );
}

function useDebounced(v: string, ms = 300) {
  const [d, setD] = useState(v);
  useEffect(() => { const t = setTimeout(() => setD(v), ms); return () => clearTimeout(t); }, [v, ms]);
  return d;
}

function OverviewTab() {
  const { data, error } = useApi<Overview>("/staff/overview/");
  if (error) return <Alert>{error}</Alert>;
  if (!data) return <Spinner />;
  const plans = Object.entries(data.paying_by_plan);
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiTile label="Monthly recurring revenue" value={usd(data.mrr)} tone="pass" sub={`${data.paying} paying workspace${data.paying === 1 ? "" : "s"}`} />
        <KpiTile label="On trial" value={data.trialing} sub={`${data.trials_ending_7d.length} end within 7 days`} />
        <KpiTile label="Payment overdue" value={data.past_due} tone={data.past_due ? "fail" : "neutral"} sub="Stripe is retrying" />
        <KpiTile label="Workspaces" value={data.workspaces} sub={`${data.verified_domains} of ${data.domains} domains verified`} />
        <KpiTile label="Users" value={data.users} sub={`${data.users_unverified} not confirmed`} />
        <KpiTile label="Sign-ups, 7 days" value={data.signups_7d} />
        <KpiTile label="Sign-ups, 30 days" value={data.signups_30d} />
        <KpiTile label="Paying by plan" value={plans.length ? plans.map(([p, n]) => `${n} ${cap(p)}`).join(" · ") : "—"} />
      </div>
      <Card title="Trials ending in the next 7 days" description="Good moment to reach out." padded={false}>
        {data.trials_ending_7d.length === 0 ? <p className="px-5 py-6 text-sm text-muted">None.</p> : (
          <ul className="divide-y divide-line">
            {data.trials_ending_7d.map((t) => (
              <li key={t.id} className="flex items-center justify-between px-5 py-3 text-sm">
                <Link className={link} to={`/staff/workspaces/${t.id}`}>{t.name}</Link>
                <span className="text-muted">ends {date(t.trial_ends_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function WorkspacesTab() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  useEffect(() => setPage(1), [dq, status]);
  const qs = new URLSearchParams({ page: String(page), ...(dq && { q: dq }), ...(status && { status }) });
  const { data, error } = useApi<Page<WorkspaceRow>>(`/staff/workspaces/?${qs}`);
  const exportQs = new URLSearchParams({ export: "csv", ...(dq && { q: dq }), ...(status && { status }) });
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <div className="min-w-[220px] flex-1"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search workspace, owner email or domain" aria-label="Search workspaces" /></div>
        <div className="w-44"><Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">All workspaces</option><option value="active">Paying</option><option value="trialing">On trial</option>
          <option value="past_due">Payment overdue</option><option value="free">Free / trial ended</option><option value="canceled">Canceled</option>
        </Select></div>
        <a className={`${link} text-sm`} href={`/api/v1/staff/workspaces/?${exportQs}`}>Export CSV</a>
      </div>
      {error ? <div className="p-4"><Alert>{error}</Alert></div> : !data ? <Spinner /> : (
        <>
          <Table head={["Workspace", "Owner", "Plan", "Domains", "Members", "Last sign-in", "Created"]} empty={data.results.length === 0}>
            {data.results.map((w) => (
              <tr key={w.id} className="hover:bg-subtle/60">
                <td className={td}><Link className={link} to={`/staff/workspaces/${w.id}`}>{w.name}</Link></td>
                <td className={td}><span className="block text-heading">{w.owner.email}</span>{w.owner.full_name && <span className="text-xs text-muted">{w.owner.full_name}</span>}</td>
                <td className={td}><span className="flex flex-wrap items-center gap-1.5">{cap(w.billing.plan)} <StatusBadge b={w.billing} /></span>
                  {w.billing.mrr > 0 && <span className="text-xs text-muted">{usd(w.billing.mrr)}/mo</span>}</td>
                <td className={`${td} tabular-nums`}>{w.verified_domains} / {w.domains}</td>
                <td className={`${td} tabular-nums`}>{w.members}</td>
                <td className={`${td} text-muted`}>{timeAgo(w.last_login)}</td>
                <td className={`${td} text-muted`}>{date(w.created_at)}</td>
              </tr>
            ))}
          </Table>
          <Pager page={page} count={data.count} setPage={setPage} />
        </>
      )}
    </Card>
  );
}

function UsersTab() {
  const [q, setQ] = useState("");
  const [verified, setVerified] = useState("");
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  useEffect(() => setPage(1), [dq, verified]);
  const qs = new URLSearchParams({ page: String(page), ...(dq && { q: dq }), ...(verified && { verified }) });
  const { data, error } = useApi<Page<UserRow>>(`/staff/users/?${qs}`);
  const exportQs = new URLSearchParams({ export: "csv", ...(dq && { q: dq }), ...(verified && { verified }) });
  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <div className="min-w-[220px] flex-1"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email or name" aria-label="Search users" /></div>
        <div className="w-44"><Select value={verified} onChange={(e) => setVerified(e.target.value)} aria-label="Filter by confirmation">
          <option value="">All users</option><option value="yes">Email confirmed</option><option value="no">Not confirmed</option>
        </Select></div>
        <a className={`${link} text-sm`} href={`/api/v1/staff/users/?${exportQs}`}>Export CSV</a>
      </div>
      {error ? <div className="p-4"><Alert>{error}</Alert></div> : !data ? <Spinner /> : (
        <>
          <Table head={["User", "Email", "Workspaces", "Signed up", "Last sign-in"]} empty={data.results.length === 0}>
            {data.results.map((u) => (
              <tr key={u.id} className="hover:bg-subtle/60">
                <td className={td}><span className="block text-heading">{u.email}</span>
                  <span className="text-xs text-muted">{u.full_name}{u.is_staff && <> · <span className="text-accent">staff</span></>}</span></td>
                <td className={td}>{u.email_verified ? <Badge tone="pass">Confirmed</Badge> : <Badge tone="warn">Not confirmed</Badge>}</td>
                <td className={td}>{u.workspaces.length === 0 ? <span className="text-muted">None</span> :
                  u.workspaces.map((w) => <span key={w.id} className="block"><Link className={link} to={`/staff/workspaces/${w.id}`}>{w.name}</Link> <span className="text-xs text-muted">{w.role}</span></span>)}</td>
                <td className={`${td} text-muted`}>{date(u.created_at)}</td>
                <td className={`${td} text-muted`}>{timeAgo(u.last_login)}</td>
              </tr>
            ))}
          </Table>
          <Pager page={page} count={data.count} setPage={setPage} />
        </>
      )}
    </Card>
  );
}

type Tab = "overview" | "workspaces" | "users";

export default function Staff() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (["overview", "workspaces", "users"].includes(params.get("tab") ?? "") ? params.get("tab") : "overview") as Tab;
  if (!user?.is_staff) return <Navigate to="/dashboard" replace />;
  return (
    <>
      <PageHeader eyebrow="MSPoint staff" title="Customers" description="Every workspace, user and subscription on DomainVitals. Only staff can see this page." />
      <div className="mb-6"><Tabs value={tab} onChange={(t) => setParams({ tab: t }, { replace: true })}
        items={[{ id: "overview", label: "Overview" }, { id: "workspaces", label: "Workspaces" }, { id: "users", label: "Users" }]} /></div>
      {tab === "overview" && <OverviewTab />}
      {tab === "workspaces" && <WorkspacesTab />}
      {tab === "users" && <UsersTab />}
    </>
  );
}

type Detail = WorkspaceRow & {
  timezone: string;
  members: { email: string; full_name: string; role: string; joined_at: string; last_login: string | null }[];
  domain_list: { name: string; verified_at: string | null; created_at: string; monitoring_enabled: boolean; score: number | null; overall: string; checked_at: string | null }[];
};

export function StaffWorkspace() {
  const { user } = useAuth();
  const { id } = useParams();
  const { data, error } = useApi<Detail>(user?.is_staff ? `/staff/workspaces/${id}/` : null);
  if (!user?.is_staff) return <Navigate to="/dashboard" replace />;
  const back = <Link className={`${link} text-sm`} to="/staff?tab=workspaces">← All workspaces</Link>;
  if (error) return <>{back}<div className="mt-4"><Alert>{error}</Alert></div></>;
  if (!data) return <Spinner />;
  const b = data.billing;
  const row = (k: string, v: ReactNode) => <div className="flex justify-between gap-4 py-2 text-sm"><dt className="text-muted">{k}</dt><dd className="text-right text-heading">{v}</dd></div>;
  return (
    <>
      <div className="mb-3">{back}</div>
      <PageHeader eyebrow="MSPoint staff" title={data.name} description={<>Owner {data.owner.email}{data.owner.full_name && ` (${data.owner.full_name})`} · created {date(data.created_at)}</>} />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          <Card title={`Domains (${data.domain_list.length})`} padded={false}>
            <Table min={600} head={["Domain", "Status", "Score", "Last check", "Added"]} empty={data.domain_list.length === 0}>
              {data.domain_list.map((d) => (
                <tr key={d.name}>
                  <td className={`${td} break-all font-medium text-heading`}>{d.name}</td>
                  <td className={`${td} whitespace-nowrap`}>{!d.verified_at ? <Badge tone="warn">Not verified</Badge> : !d.monitoring_enabled ? <Badge>Paused</Badge>
                    : <Badge tone={d.overall === "fail" ? "fail" : d.overall === "warn" ? "warn" : "pass"}>{d.overall ? cap(d.overall) : "Monitored"}</Badge>}</td>
                  <td className={`${td} tabular-nums`}>{d.score ?? "—"}</td>
                  <td className={`${td} text-muted`}>{timeAgo(d.checked_at)}</td>
                  <td className={`${td} text-muted`}>{date(d.created_at)}</td>
                </tr>
              ))}
            </Table>
          </Card>
          <Card title={`Members (${data.members.length})`} padded={false}>
            <Table min={560} head={["Member", "Role", "Joined", "Last sign-in"]} empty={data.members.length === 0}>
              {data.members.map((m) => (
                <tr key={m.email}>
                  <td className={td}><span className="block text-heading">{m.email}</span><span className="text-xs text-muted">{m.full_name}</span></td>
                  <td className={td}>{cap(m.role)}</td>
                  <td className={`${td} text-muted`}>{date(m.joined_at)}</td>
                  <td className={`${td} text-muted`}>{timeAgo(m.last_login)}</td>
                </tr>
              ))}
            </Table>
          </Card>
        </div>
        <Card title="Subscription">
          <dl className="divide-y divide-line">
            {row("Plan", cap(b.plan))}
            {row("Status", <StatusBadge b={b} />)}
            {row("Limits in effect", cap(b.effective_plan))}
            {b.interval && row("Billing", b.interval === "year" ? "Yearly" : "Monthly")}
            {b.mrr > 0 && row("Revenue", `${usd(b.mrr)}/month`)}
            {b.trial_ends_at && row(b.status === "trialing" ? "Trial ends" : "Trial ended", date(b.trial_ends_at))}
            {b.current_period_end && row(b.cancel_at_period_end ? "Cancels on" : "Renews on", date(b.current_period_end))}
            {row("Stripe customer", b.stripe_customer_id ? <code className="font-mono text-xs">{b.stripe_customer_id}</code> : "—")}
            {row("Time zone", data.timezone)}
          </dl>
          <p className="mt-4 text-xs text-muted">Change a plan by hand with <code className="font-mono">./dc exec backend python manage.py set_plan "{data.name}" &lt;plan&gt;</code>.</p>
        </Card>
      </div>
    </>
  );
}
