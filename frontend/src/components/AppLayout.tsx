import { ReactNode, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, errorText, ROLE_LABEL } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useWorkspace } from "../lib/workspace";
import { IconBell, IconClose, IconGlobe, IconHome, IconLogout, IconMenu, IconSettings, IconUsers } from "./icons";
import { Logo } from "./Logo";
import { Alert, cls } from "./ui";

const NAV: { to: string; label: string; icon: () => ReactNode }[] = [
  { to: "/dashboard", label: "Overview", icon: IconHome },
  { to: "/domains", label: "Domains", icon: IconGlobe },
  { to: "/alerts", label: "Alerts", icon: IconBell },
  { to: "/settings/members", label: "Members", icon: IconUsers },
  { to: "/settings/workspace", label: "Settings", icon: IconSettings },
];

function VerifyBanner() {
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [err, setErr] = useState("");
  const resend = async () => {
    setState("sending");
    try { await api("/auth/verify-email/resend/", { method: "POST" }); setState("sent"); }
    catch (e) { setErr(errorText(e)); setState("error"); }
  };
  return (
    <div className="border-b border-warn/20 bg-warn-bg px-4 py-2.5 text-sm text-warn sm:px-8">
      Confirm your email address to invite teammates and receive alerts.{" "}
      {state === "sent" ? <strong>Confirmation link sent.</strong> : (
        <button onClick={resend} disabled={state === "sending"} className="font-semibold underline underline-offset-2">
          {state === "sending" ? "Sending…" : "Resend confirmation link"}
        </button>
      )}
      {state === "error" && <span className="ml-2 font-medium text-fail">{err}</span>}
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const { orgs, current, select } = useWorkspace();
  const navigate = useNavigate();
  const [err, setErr] = useState("");

  const onLogout = async () => {
    try { await logout(); navigate("/login", { replace: true }); }
    catch (e) { setErr(errorText(e)); }
  };

  return (
    <div className="flex h-full flex-col bg-navy-900 text-navy-100">
      <div className="px-5 pb-5 pt-6"><Logo inverse /></div>

      {current && (
        <div className="px-3">
          <label htmlFor="ws-switch" className="px-2 text-xs text-navy-100/60">Workspace</label>
          <select id="ws-switch" value={current.id}
            onChange={(e) => {
              if (e.target.value === "__new") { navigate("/onboarding?new=1"); onNavigate?.(); }
              else select(e.target.value);
            }}
            className="mt-1 h-10 w-full rounded-md border border-white/10 bg-navy-800 px-2.5 text-sm text-white focus:border-orange-500 focus:outline-none">
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
            <option value="__new">Create another workspace</option>
          </select>
          {current.role && <p className="mt-1.5 px-2 text-xs text-navy-100/60">Your role: {ROLE_LABEL[current.role]}</p>}
        </div>
      )}

      <nav className="mt-6 flex-1 space-y-0.5 px-3" aria-label="Main">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} onClick={onNavigate}
            className={({ isActive }) => cls(
              "relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
              isActive ? "bg-white/10 font-medium text-white before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-orange-500"
                       : "text-navy-100/80 hover:bg-white/5 hover:text-white")}>
            <n.icon />{n.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-3">
        <p className="truncate px-2 text-sm text-white">{user?.full_name || user?.email}</p>
        {user?.full_name && <p className="truncate px-2 text-xs text-navy-100/60">{user.email}</p>}
        <button onClick={onLogout}
          className="mt-2 flex w-full items-center gap-3 rounded-md px-2 py-2 text-sm text-navy-100/80 hover:bg-white/5 hover:text-white">
          <IconLogout />Sign out
        </button>
        {err && <div className="mt-2"><Alert>{err}</Alert></div>}
      </div>
    </div>
  );
}

export default function AppLayout() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 lg:block"><Sidebar /></aside>

      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-white px-4 py-3 lg:hidden">
        <Logo size={28} />
        <button onClick={() => setOpen(true)} aria-label="Open navigation" aria-expanded={open}
          className="rounded-md p-2 text-navy-900 hover:bg-canvas"><IconMenu /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-30 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-navy-950/50" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] shadow-xl">
            <button onClick={() => setOpen(false)} aria-label="Close navigation"
              className="absolute right-3 top-5 z-10 rounded-md p-1.5 text-white hover:bg-white/10"><IconClose /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      {user && !user.email_verified && <VerifyBanner />}
      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8"><Outlet /></main>
    </div>
  );
}
