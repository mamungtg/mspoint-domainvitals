import { FormEvent, useState } from "react";
import { api, ApiError, User } from "../lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setUser(await api<User>("/auth/login/", { method: "POST", body: JSON.stringify({ email, password }) }));
    } catch (err) {
      setError((err as ApiError).message ?? "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  if (user) {
    return (
      <main className="mx-auto max-w-sm px-4 py-24">
        <h1 className="text-2xl font-semibold">Signed in</h1>
        <p className="mt-2 text-slate-600">{user.email}</p>
        {!user.email_verified && <p className="mt-2 text-amber-700">Please verify your email address.</p>}
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-sm px-4 py-24">
      <h1 className="text-2xl font-semibold">Sign in to DomainVitals</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block">
          <span className="text-sm text-slate-700">Email</span>
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        </label>
        <label className="block">
          <span className="text-sm text-slate-700">Password</span>
          <input type="password" required autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2" />
        </label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <button disabled={busy} className="w-full rounded-md bg-slate-900 px-4 py-2 text-white disabled:opacity-60">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
