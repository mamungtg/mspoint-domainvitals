import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Alert, Button, Field, Input, Select } from "../components/ui";
import { linkCls } from "../components/ui";
import { api, errorText, Organization } from "../lib/api";
import { useWorkspace } from "../lib/workspace";
import { browserTimezone, timezones } from "./timezones";

export default function Onboarding() {
  const { orgs, reload, select } = useWorkspace();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const zones = useMemo(timezones, []);
  const [name, setName] = useState("");
  const [tz, setTz] = useState(() => { const b = browserTimezone(); return zones.includes(b) ? b : "UTC"; });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isAdditional = orgs.length > 0 || params.get("new") === "1";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Give your workspace a name."); return; }
    setBusy(true); setError("");
    try {
      const org = await api<Organization>("/organizations/", { method: "POST", json: { name: name.trim(), timezone: tz } });
      await reload();
      select(org.id);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title={isAdditional ? "New workspace" : "Create your workspace"}
      subtitle="A workspace holds your domains, alerts and team. Agencies usually create one for their own team."
      footer={isAdditional ? <Link className={linkCls} to="/dashboard">Cancel</Link> : undefined}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Workspace name"><Input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Acme Digital Agency" /></Field>
        <Field label="Time zone" hint="Used for reports and alert times.">
          <Select value={tz} onChange={(e) => setTz(e.target.value)}>
            {zones.map((z) => <option key={z} value={z}>{z}</option>)}
          </Select>
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" busy={busy} className="w-full">Create workspace</Button>
      </form>
    </AuthLayout>
  );
}
