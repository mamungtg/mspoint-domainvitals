import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, errorText, ROLE_LABEL } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";
import { Alert, Button, cls, Select } from "./ui";

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/domains", label: "Domains" },
  { to: "/alerts", label: "Alerts" },
  { to: "/settings/members", label: "Members" },
  { to: "/settings/workspace", label: "Workspace settings" },
];

function VerifyBanner() {
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [err, setErr] = useState("");
  const resend = async () => {
    setState("sending");
    try {
      await api("/auth/verify-email/resend/", { method: "POST" });
      setState("sent");
    } catch (e) {
      setErr(errorText(e));
      setState("error");
    }
  };
  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900">
      Please verify your email address. Check your inbox for the confirmation link.{" "}
      {state === "sent" ? <strong>Link sent.</strong> : (
        <button onClick={resend} disabled={state === "sending"} className="font-medium underline">
          {state === "sending" ? "Sending…" : "Resend link"}
        </button>
      )}
      {state === "error" && <span className="ml-2 text-red-700">{err}</span>}
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { orgs, current, select } = useWorkspace();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [logoutErr, setLogoutErr] = useState("");

  const onLogout = async () => {
    try { await logout(); navigate("/login", { replace: true }); }
    catch (e) { setLogoutErr(errorText(e)); }
  };

  const nav = (
    <nav className="space-y-1">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} onClick={() => setMenuOpen(false)}
          className={({ isActive }) => cls("block rounded-md px-3 py-2 text-sm",
            isActive ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100")}>
          {n.label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen">
      {user && !user.email_verified && <VerifyBanner />}
      <header className="flex items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-3">
          <button className="rounded-md border border-slate-300 px-2 py-1 text-sm md:hidden"
            aria-expanded={menuOpen} aria-label="Toggle navigation" onClick={() => setMenuOpen((v) => !v)}>
            Menu
          </button>
          <span className="font-bold text-slate-900">DomainVitals</span>
        </div>
        <div className="flex items-center gap-3">
          {orgs.length > 0 && current && (
            <label className="hidden items-center gap-2 text-sm sm:flex">
              <span className="text-slate-500">Workspace</span>
              <Select value={current.id} onChange={(e) => {
                if (e.target.value === "__new") navigate("/onboarding?new=1");
                else select(e.target.value);
              }} className="w-48 py-1">
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                <option value="__new">+ New workspace</option>
              </Select>
            </label>
          )}
          <span className="hidden text-sm text-slate-600 lg:inline">{user?.email}</span>
          <Button variant="secondary" onClick={onLogout} className="py-1">Sign out</Button>
        </div>
      </header>
      {logoutErr && <div className="p-4"><Alert>{logoutErr}</Alert></div>}
      <div className="mx-auto flex max-w-6xl gap-6 px-4 py-6">
        <aside className="hidden w-52 shrink-0 md:block">
          {current && <p className="mb-3 px-3 text-xs text-slate-500">{current.name} · {current.role && ROLE_LABEL[current.role]}</p>}
          {nav}
        </aside>
        {menuOpen && (
          <div className="fixed inset-0 z-20 bg-white p-4 md:hidden">
            <Button variant="ghost" onClick={() => setMenuOpen(false)} className="mb-4">Close</Button>
            {orgs.length > 1 && current && (
              <Select value={current.id} onChange={(e) => { select(e.target.value); setMenuOpen(false); }} className="mb-4">
                {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </Select>
            )}
            {nav}
          </div>
        )}
        <main className="min-w-0 flex-1"><Outlet /></main>
      </div>
    </div>
  );
}
