import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { safeNext } from "../components/guards";
import { Alert, Button, Field, Input } from "../components/ui";
import { errorText } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      await login(email, password);
      navigate(safeNext(params.get("next")), { replace: true });
    } catch (err) {
      setError(errorText(err, "Sign-in failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Sign in" subtitle="Welcome back."
      footer={<>No account yet? <Link className="font-medium text-sky-700" to={`/register${params.get("next") ? `?next=${encodeURIComponent(params.get("next")!)}` : ""}`}>Create one</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Email"><Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><Input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" busy={busy} className="w-full">Sign in</Button>
        <p className="text-center text-sm"><Link className="text-sky-700" to="/forgot-password">Forgot your password?</Link></p>
      </form>
    </AuthLayout>
  );
}
