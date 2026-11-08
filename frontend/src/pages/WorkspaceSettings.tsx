import { FormEvent, useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Field, Input, Select } from "../components/ui";
import { api, errorText, isManager } from "../lib/api";
import { useWorkspace } from "../lib/workspace";
import { timezones } from "./timezones";

export default function WorkspaceSettings() {
  const { current, reload } = useWorkspace();
  const zones = useMemo(timezones, []);
  const [name, setName] = useState("");
  const [tz, setTz] = useState("UTC");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const editable = isManager(current?.role);

  useEffect(() => { if (current) { setName(current.name); setTz(current.timezone); } }, [current]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!current) return;
    setBusy(true); setError(""); setSaved(false);
    try {
      await api(`/organizations/${current.id}/`, { method: "PATCH", json: { name: name.trim(), timezone: tz } });
      await reload();
      setSaved(true);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!current) return null;
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Workspace settings</h1>
      <Card>
        <form onSubmit={onSubmit} className="max-w-md space-y-4" noValidate>
          <Field label="Name"><Input value={name} disabled={!editable} maxLength={120} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Time zone">
            <Select value={tz} disabled={!editable} onChange={(e) => setTz(e.target.value)}>
              {zones.map((z) => <option key={z} value={z}>{z}</option>)}
            </Select>
          </Field>
          {!editable && <Alert tone="info">Only owners and admins can change these settings.</Alert>}
          {error && <Alert>{error}</Alert>}
          {saved && <Alert tone="success">Settings saved.</Alert>}
          {editable && <Button type="submit" busy={busy}>Save changes</Button>}
        </form>
      </Card>
    </div>
  );
}
