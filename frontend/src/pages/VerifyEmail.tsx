import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Alert, Spinner } from "../components/ui";
import { api, errorText } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const { user, refresh } = useAuth();
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // StrictMode runs effects twice in dev
    started.current = true;
    const token = params.get("token");
    if (!token) { setError("This link is missing its token."); setState("error"); return; }
    api("/auth/verify-email/", { method: "POST", json: { token } })
      .then(async () => { setState("done"); await refresh(); })
      .catch((e) => { setError(errorText(e)); setState("error"); });
  }, [params, refresh]);

  return (
    <AuthLayout title="Email verification">
      {state === "working" && <Spinner label="Verifying…" />}
      {state === "done" && (
        <div className="space-y-4">
          <Alert tone="success">Your email address is verified.</Alert>
          <Link className="font-medium text-sky-700" to={user ? "/dashboard" : "/login"}>Continue</Link>
        </div>
      )}
      {state === "error" && (
        <div className="space-y-4">
          <Alert>{error}</Alert>
          <p className="text-sm text-slate-600">Sign in and use “Resend link” to get a new one.</p>
          <Link className="font-medium text-sky-700" to={user ? "/dashboard" : "/login"}>Continue</Link>
        </div>
      )}
    </AuthLayout>
  );
}
