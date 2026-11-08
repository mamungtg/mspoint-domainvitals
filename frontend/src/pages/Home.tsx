import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";

type Health = { status: string; checks: Record<string, string> };

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api<Health>("/health/").then(setHealth).catch(() => setFailed(true));
  }, []);

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
        <Link to="/login" className="rounded-md bg-slate-900 px-4 py-2 text-white">Sign in</Link>
      </div>
    </main>
  );
}
