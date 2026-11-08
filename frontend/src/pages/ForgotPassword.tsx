import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Alert, Button, Field, Input } from "../components/ui";
import { linkCls } from "../components/ui";
import { api, errorText } from "../lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/auth/password-reset/", { method: "POST", json: { email } });
      setSent(true);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to choose a new password."
      footer={<Link className={linkCls} to="/login">Back to sign in</Link>}>
      {sent ? (
        <Alert tone="success">If an account exists for {email}, a reset link is on its way.</Alert>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <Field label="Email"><Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          {error && <Alert>{error}</Alert>}
          <Button type="submit" busy={busy} className="w-full">Send reset link</Button>
        </form>
      )}
    </AuthLayout>
  );
}
