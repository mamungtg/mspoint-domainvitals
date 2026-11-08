import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Alert, Button, Field, Input } from "../components/ui";
import { linkCls } from "../components/ui";
import { api, errorText } from "../lib/api";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const uid = params.get("uid"), token = params.get("token");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError("The two passwords do not match."); return; }
    setBusy(true); setError("");
    try {
      await api("/auth/password-reset/confirm/", { method: "POST", json: { uid, token, new_password: password } });
      setDone(true);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!uid || !token) {
    return <AuthLayout title="Reset your password"><Alert>This reset link is incomplete. Request a new one.</Alert></AuthLayout>;
  }
  return (
    <AuthLayout title="Choose a new password">
      {done ? (
        <div className="space-y-4">
          <Alert tone="success">Your password has been changed.</Alert>
          <Link className={linkCls} to="/login">Sign in</Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Field label="New password" hint="At least 10 characters.">
            <Input type="password" required autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Confirm new password">
            <Input type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" busy={busy} className="w-full">Set password</Button>
        </form>
      )}
    </AuthLayout>
  );
}
