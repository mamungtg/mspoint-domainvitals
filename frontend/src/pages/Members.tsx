import { FormEvent, useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Field, Input, PageHeader, Select, Spinner } from "../components/ui";
import { api, errorText, Invitation, isManager, Membership, Role, ROLE_LABEL, ROLE_RANK } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";

const ROLES: Role[] = ["owner", "admin", "member", "viewer"];
const ROLE_HELP: Record<Role, string> = {
  owner: "Full control, including billing and owners",
  admin: "Manage members, domains and settings",
  member: "Add and manage domains",
  viewer: "Read-only access",
};

export default function Members() {
  const { user } = useAuth();
  const { current, reload: reloadOrgs } = useWorkspace();
  const [members, setMembers] = useState<Membership[] | null>(null);
  const [invites, setInvites] = useState<Invitation[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("member");
  const [busy, setBusy] = useState(false);
  const myRole = current?.role ?? null;
  const manager = isManager(myRole);

  const load = useCallback(async () => {
    if (!current) return;
    setError("");
    try {
      setMembers(await api<Membership[]>(`/organizations/${current.id}/members/`));
      setInvites(manager ? await api<Invitation[]>(`/organizations/${current.id}/invitations/`) : []);
    } catch (e) {
      setError(errorText(e));
    }
  }, [current, manager]);

  useEffect(() => { setMembers(null); void load(); }, [load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    setError(""); setNotice("");
    try { await fn(); setNotice(ok); await load(); }
    catch (e) { setError(errorText(e)); }
  };

  async function onInvite(e: FormEvent) {
    e.preventDefault();
    if (!current) return;
    setBusy(true);
    await run(() => api(`/organizations/${current.id}/members/`, { method: "POST", json: { email, role } }),
      `Invitation sent to ${email}.`);
    setEmail("");
    setBusy(false);
  }

  const changeRole = (m: Membership, r: Role) =>
    run(() => api(`/memberships/${m.id}/`, { method: "PATCH", json: { role: r } }), `${m.user.email} is now ${ROLE_LABEL[r]}.`);

  const remove = async (m: Membership) => {
    const self = m.user.id === user?.id;
    if (!window.confirm(self ? "Leave this workspace?" : `Remove ${m.user.email} from this workspace?`)) return;
    await run(() => api(`/memberships/${m.id}/`, { method: "DELETE" }), self ? "You left the workspace." : `${m.user.email} was removed.`);
    if (self) await reloadOrgs();
  };

  const revoke = (i: Invitation) =>
    run(() => api(`/invitations/${i.id}/`, { method: "DELETE" }), `Invitation for ${i.email} revoked.`);

  // Which roles can the current user assign? Never above their own.
  const assignable = ROLES.filter((r) => myRole && ROLE_RANK[r] <= ROLE_RANK[myRole]);
  const ownerCount = members?.filter((m) => m.role === "owner").length ?? 0;
  const canLeave = (m: Membership) => m.user.id === user?.id && !(m.role === "owner" && ownerCount <= 1);
  const canEdit = (m: Membership) =>
    manager && m.user.id !== user?.id && !(myRole === "admin" && m.role === "owner");

  if (!current) return <Spinner />;
  return (
    <div className="space-y-6">
      <PageHeader title="Members" description={`People who can see and manage ${current.name}.`} />
      {error && <Alert>{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {manager && (
        <Card title="Invite a teammate" description="They get an email with a link to join this workspace.">
          <form onSubmit={onInvite} className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end" noValidate>
            <Field label="Email"><Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="colleague@company.com" /></Field>
            <Field label="Role">
              <Select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                {assignable.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
              </Select>
            </Field>
            <Button type="submit" busy={busy} disabled={!email}>Send invite</Button>
          </form>
          <p className="mt-2 text-xs text-muted">{ROLE_HELP[role]}. Invitations expire after 7 days.</p>
        </Card>
      )}

      <Card title="Team" padded={false}>
        {members === null ? <Spinner /> : (
          <ul className="divide-y divide-line">
            {members.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-navy-900">
                    {m.user.full_name || m.user.email} {m.user.id === user?.id && <span className="text-muted">(you)</span>}
                  </p>
                  <p className="truncate text-xs text-muted">{m.user.email}</p>
                </div>
                <div className="flex items-center gap-2">
                  {canEdit(m) ? (
                    <Select aria-label={`Role for ${m.user.email}`} value={m.role} className="h-8 w-32 text-[13px]"
                      onChange={(e) => changeRole(m, e.target.value as Role)}>
                      {assignable.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                    </Select>
                  ) : <Badge>{ROLE_LABEL[m.role]}</Badge>}
                  {(canEdit(m) || canLeave(m)) && (
                    <Button variant="danger" size="sm" onClick={() => remove(m)}>
                      {m.user.id === user?.id ? "Leave" : "Remove"}
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {manager && invites.length > 0 && (
        <Card title="Pending invitations" padded={false}>
          <ul className="divide-y divide-line">
            {invites.map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
                <div>
                  <p className="text-sm text-navy-900">{i.email} <Badge tone="brand">{ROLE_LABEL[i.role]}</Badge></p>
                  <p className="text-xs text-muted">Expires {new Date(i.expires_at).toLocaleDateString()}</p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => revoke(i)}>Revoke</Button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
