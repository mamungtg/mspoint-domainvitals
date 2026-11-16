import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";
import { Spinner } from "./ui";

/** Only allows signed-in users; others go to /login?next=<here>. */
export function RequireAuth() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return <Outlet />;
}

/** Signed-in users without any workspace are sent to onboarding. */
export function RequireWorkspace() {
  const { orgs, loading } = useWorkspace();
  if (loading) return <Spinner />;
  if (orgs.length === 0) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}

/** Pages like login/register: signed-in users skip straight to the app. */
export function GuestOnly() {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <Outlet />;
}

/** Only same-site paths are allowed after sign-in. Rejects protocol-relative
 *  ("//x", "/\\x"), backslashes, control characters and anything with a scheme,
 *  which browsers or the router could turn into an external redirect. */
export function safeNext(next: string | null, fallback = "/dashboard"): string {
  if (!next || next.length > 512) return fallback;
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("\\") || /[\u0000-\u001f\u007f]/.test(next)) return fallback;
  try {
    const u = new URL(next, "https://app.invalid");
    if (u.origin !== "https://app.invalid") return fallback;
    return u.pathname + u.search + u.hash;
  } catch {
    return fallback;
  }
}
