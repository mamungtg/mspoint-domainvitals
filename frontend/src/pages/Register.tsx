import { FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import ResendConfirmation, { rememberNext } from "../components/ResendConfirmation";
import { Alert, Button, Field, Input, linkCls } from "../components/ui";
import { ApiError, errorText, FieldErrors } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Register() {
  const { register } = useAuth();
  const [params] = useSearchParams();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setFieldErrors({});
    try {
      const r = await register(email, password, fullName, accepted);
      rememberNext(params.get("next"));
      setSentTo(r.email);
    } catch (err) {
      const d = (err as ApiError).details;
      if (d && (d.email || d.password || d.full_name || d.accept_terms)) setFieldErrors(d);
      else setError(errorText(err, "Registration failed."));
    } finally {
      setBusy(false);
    }
  }

  if (sentTo) {
    return (
      <AuthLayout title="Check your inbox" subtitle="One more step before you can sign in."
        footer={<>Already confirmed? <Link className={linkCls} to="/login">Sign in</Link></>}>
        <div className="space-y-5">
          <p className="text-ink">
            We sent a confirmation link to <strong className="text-heading">{sentTo}</strong>. Open it to activate your account, then sign in.
          </p>
          <p className="text-sm text-muted">The link expires in 48 hours. Nothing arrived after a few minutes? Check your spam folder or send a new link.</p>
          <ResendConfirmation email={sentTo} />
        </div>
      </AuthLayout>
    );
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
        <div>
          <label className="flex items-start gap-2.5 text-sm text-ink">
            <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-[#14508f]" checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)} aria-invalid={!!fieldErrors.accept_terms} />
            <span>
              I agree to the <Link className={linkCls} to="/legal/terms" target="_blank">Terms of Service</Link>, including
              the <Link className={linkCls} to="/legal/dpa" target="_blank">Data Processing Addendum</Link>, and have read
              the <Link className={linkCls} to="/legal/privacy" target="_blank">Privacy Policy</Link>.
            </span>
          </label>
          {fieldErrors.accept_terms?.[0] && <p className="mt-1.5 text-xs font-medium text-fail">{fieldErrors.accept_terms[0]}</p>}
        </div>
        {error && <Alert>{error}</Alert>}
        <Button type="submit" busy={busy} disabled={!accepted} className="w-full">Create account</Button>
        <p className="text-center text-xs text-muted">We'll email you a link to confirm your address before your first sign-in.</p>
      </form>
    </AuthLayout>
  );
}
