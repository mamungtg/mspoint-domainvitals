import { FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { safeNext } from "../components/guards";
import { Alert, Button, Field, Input } from "../components/ui";
import { linkCls } from "../components/ui";
import { ApiError, errorText, FieldErrors } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setFieldErrors({});
    try {
      await register(email, password, fullName);
      navigate(safeNext(params.get("next"), "/onboarding"), { replace: true });
    } catch (err) {
      const d = (err as ApiError).details;
      if (d && (d.email || d.password || d.full_name)) setFieldErrors(d);
      else setError(errorText(err, "Registration failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Create your account" subtitle="Start monitoring your domains in minutes."
      footer={<>Already have an account? <Link className={linkCls} to="/login">Sign in</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Full name" error={fieldErrors.full_name?.[0]}>
          <Input autoComplete="name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </Field>
        <Field label="Work email" error={fieldErrors.email?.[0]}>
          <Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" hint="At least 10 characters; avoid common passwords." error={fieldErrors.password?.[0] ?? fieldErrors.non_field_errors?.[0]}>
          <Input type="password" required autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" busy={busy} className="w-full">Create account</Button>
      </form>
    </AuthLayout>
  );
}
