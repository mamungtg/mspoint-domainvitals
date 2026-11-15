import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { safeNext } from "../components/guards";
import ResendConfirmation, { takeNext } from "../components/ResendConfirmation";
import { Alert, Button, Field, Input, linkCls } from "../components/ui";
import { ApiError, errorText } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [unconfirmed, setUnconfirmed] = useState("");
  const [busy, setBusy] = useState(false);
  const justConfirmed = params.get("confirmed") === "1";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setUnconfirmed("");
    try {
      await login(email, password);
      navigate(safeNext(params.get("next") ?? takeNext()), { replace: true });
    } catch (err) {
      if ((err as ApiError).code === "email_not_verified") setUnconfirmed(email.trim());
      else setError(errorText(err, "Sign-in failed. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Sign in" subtitle={justConfirmed ? undefined : "Welcome back."}
      footer={<>No account yet? <Link className={linkCls} to={`/register${params.get("next") ? `?next=${encodeURIComponent(params.get("next")!)}` : ""}`}>Create one</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {justConfirmed && <Alert tone="success">Your email address is confirmed. Sign in to continue.</Alert>}
        <Field label="Email"><Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <Alert>{error}</Alert>}
        {unconfirmed && (
          <div className="space-y-3">
            <Alert tone="warning">Confirm your email address before signing in. Open the link we sent to {unconfirmed}.</Alert>
            <ResendConfirmation email={unconfirmed} variant="ghost" />
          </div>
        )}
        <Button type="submit" busy={busy} className="w-full">Sign in</Button>
        <p className="text-center text-sm"><Link className={linkCls} to="/forgot-password">Forgot your password?</Link></p>
      </form>
    </AuthLayout>
  );
}
