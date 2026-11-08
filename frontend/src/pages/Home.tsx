import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

type Health = { status: string };

export default function Home() {
  const { user } = useAuth();
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => { api<Health>("/health/").then(setHealth).catch(() => setFailed(true)); }, []);
  const label = failed ? "Unreachable" : health ? (health.status === "ok" ? "Operational" : "Degraded") : "Checking…";

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-4">
      <p className="text-sm font-semibold tracking-wide text-sky-700">MSPOINT</p>
      <h1 className="mt-1 text-4xl font-bold">DomainVitals</h1>
      <p className="mt-3 text-slate-600">
        One dashboard to monitor email authentication, DNS and SSL/TLS health across all your client domains.
      </p>
      <div className="mt-8 rounded-lg border border-slate-200 bg-white p-4">
        <p className="text-sm text-slate-500">API status</p>
        <p className="mt-1 font-medium">{label}</p>
      </div>
      <div className="mt-6 flex gap-3">
        {user ? (
          <Link to="/dashboard" className="rounded-md bg-slate-900 px-4 py-2 text-white">Open dashboard</Link>
        ) : (
          <>
            <Link to="/login" className="rounded-md bg-slate-900 px-4 py-2 text-white">Sign in</Link>
            <Link to="/register" className="rounded-md border border-slate-300 bg-white px-4 py-2">Create account</Link>
          </>
        )}
      </div>
    </main>
  );
}
