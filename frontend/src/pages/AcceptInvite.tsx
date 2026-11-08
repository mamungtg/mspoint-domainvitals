import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AuthLayout from "../components/AuthLayout";
import { Alert, Spinner } from "../components/ui";
import { api, errorText, Organization } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";

/** Reached from the invitation email. RequireAuth sends guests to login first. */
export default function AcceptInvite() {
  const [params] = useSearchParams();
  const { user } = useAuth();
  const { reload, select } = useWorkspace();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = params.get("token");
    if (!token) { setError("This invitation link is incomplete."); return; }
    api<Organization>("/invitations/accept/", { method: "POST", json: { token } })
      .then(async (org) => { await reload(); select(org.id); navigate("/dashboard", { replace: true }); })
      .catch((e) => setError(errorText(e)));
  }, [params, reload, select, navigate]);

  return (
    <AuthLayout title="Join workspace">
      {error ? (
        <div className="space-y-4">
          <Alert>{error}</Alert>
          <p className="text-sm text-slate-600">
            You are signed in as <strong>{user?.email}</strong>. The invitation must be accepted by the address it was sent to,
            after verifying that email address.
          </p>
          <Link className="font-medium text-sky-700" to="/dashboard">Go to dashboard</Link>
        </div>
      ) : <Spinner label="Joining workspace…" />}
    </AuthLayout>
  );
}
