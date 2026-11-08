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

/** Only allow relative in-app redirects (no open redirect via ?next=). */
export function safeNext(next: string | null, fallback = "/dashboard"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return fallback;
  return next;
}
