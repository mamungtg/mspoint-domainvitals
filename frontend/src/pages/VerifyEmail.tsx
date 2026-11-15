import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import ResendConfirmation from "../components/ResendConfirmation";
import { Alert, Field, Input, Spinner, linkCls } from "../components/ui";
import { api, errorText } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { user, refresh } = useAuth();
  const [state, setState] = useState<"working" | "error">("working");
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // StrictMode runs effects twice in dev
    started.current = true;
    const token = params.get("token");
    if (!token) { setError("This link is missing its token."); setState("error"); return; }
    api("/auth/verify-email/", { method: "POST", json: { token } })
      .then(async () => {
        await refresh();
        navigate(user ? "/dashboard" : "/login?confirmed=1", { replace: true });
      })
      .catch((e) => { setError(errorText(e)); setState("error"); });
  }, [params, refresh, navigate, user]);

  return (
    <AuthLayout title="Confirm your email address">
      {state === "working" && <Spinner label="Confirming…" />}
      {state === "error" && (
        <div className="space-y-5">
          <Alert>{error}</Alert>
          <p className="text-sm text-ink">Links expire after 48 hours. Enter your email address to get a fresh link.</p>
          <Field label="Email"><Input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <ResendConfirmation email={email.trim()} />
          <p className="text-sm"><Link className={linkCls} to="/login">Back to sign in</Link></p>
        </div>
      )}
    </AuthLayout>
  );
}
