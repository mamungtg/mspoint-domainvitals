import { ReactNode, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api, errorText, Organization, ROLE_LABEL } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import { useWorkspace } from "../lib/workspace";
import {
  IconBell, IconCard, IconClose, IconFile, IconGlobe, IconHome, IconLock, IconLogout, IconMenu, IconMoon, IconSearch,
  IconChevron, IconPlus, IconSettings, IconSun, IconUsers,
} from "./icons";
import { Logo } from "./Logo";
import { cls } from "./ui";

type NavItem = { to: string; label: string; icon: () => ReactNode; soon?: boolean };
const GROUPS: { title: string; items: NavItem[] }[] = [
  { title: "Monitoring", items: [
    { to: "/dashboard", label: "Overview", icon: IconHome },
    { to: "/domains", label: "Domains", icon: IconGlobe },
    { to: "/alerts", label: "Alerts", icon: IconBell, soon: true },
  ] },
  { title: "Reports", items: [
    { to: "/reports/dmarc", label: "DMARC reports", icon: IconFile, soon: true },
    { to: "/reports/tls", label: "SSL/TLS certificates", icon: IconLock },
  ] },
  { title: "Tools", items: [{ to: "/tools/checker", label: "Domain checker", icon: IconSearch }] },
  { title: "Workspace", items: [
    { to: "/settings/members", label: "Members", icon: IconUsers },
    { to: "/settings/workspace", label: "Settings", icon: IconSettings },
    { to: "/settings/billing", label: "Plan and billing", icon: IconCard, soon: true },
  ] },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col bg-navy-900 text-navy-100">
      <Link to="/dashboard" onClick={onNavigate} className="block px-5 pb-6 pt-6" aria-label="DomainVitals overview"><Logo inverse /></Link>
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6" aria-label="Main">
        {GROUPS.map((g) => (
          <div key={g.title}>
            <p className="px-3 pb-1.5 text-xs font-medium text-navy-100/50">{g.title}</p>
            <div className="space-y-0.5">
              {g.items.map((n) => (
                <NavLink key={n.to} to={n.to} onClick={onNavigate}
                  className={({ isActive }) => cls("relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                    isActive ? "bg-white/10 font-medium text-white before:absolute before:inset-y-1.5 before:left-0 before:w-[3px] before:rounded-full before:bg-orange-500"
                             : "text-navy-100/80 hover:bg-white/5 hover:text-white")}>
                  <n.icon /><span className="flex-1">{n.label}</span>
                  {n.soon && <span className="rounded bg-white/10 px-1.5 py-px text-[10px] font-medium text-navy-100/70">Soon</span>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <p className="border-t border-white/10 px-5 py-4 text-xs text-navy-100/50">© {new Date().getFullYear()} MSPoint LLC</p>
    </div>
  );
}

function WorkspaceSwitcher() {
  const { orgs, current, select } = useWorkspace();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const itemsRef = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    const idx = Math.max(0, orgs.findIndex((o) => o.id === current?.id));
    itemsRef.current[idx]?.focus();
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, orgs, current]);

  if (!current) return null;

  const onKey = (e: React.KeyboardEvent) => {
    const items = itemsRef.current.filter(Boolean) as HTMLButtonElement[];
    const at = items.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "Escape") { setOpen(false); (wrap.current?.querySelector("button") as HTMLButtonElement)?.focus(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); items[(at + 1) % items.length]?.focus(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); items[(at - 1 + items.length) % items.length]?.focus(); }
  };
  const choose = (id: string) => { select(id); setOpen(false); };

  return (
    <div ref={wrap} className="relative flex min-w-0 items-center gap-2" onKeyDown={onKey}>
      <button type="button" onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open}
        aria-label={`Workspace: ${current.name}. Change workspace`}
        className="flex h-9 min-w-0 max-w-[18rem] items-center gap-2.5 rounded-md border border-line bg-surface pl-2 pr-2.5 text-sm font-medium text-heading hover:bg-subtle">
        <span className={cls("flex h-6 w-6 shrink-0 items-center justify-center rounded text-[11px] font-semibold",
          current.is_demo ? "bg-orange-500/15 text-accent" : "bg-navy-700 text-white")} aria-hidden="true">
          {current.name.trim().slice(0, 1).toUpperCase()}
        </span>
        <span className="truncate">{current.name}</span>
        <span className="ml-auto rotate-90 text-muted" aria-hidden="true"><IconChevron /></span>
      </button>
      {current.is_demo && <span className="hidden rounded bg-orange-500/15 px-2 py-0.5 text-xs font-semibold text-accent sm:inline">Sample data</span>}

      {open && (
        <div role="menu" aria-label="Workspaces"
          className="absolute left-0 top-11 z-40 w-72 overflow-hidden rounded-lg border border-line bg-surface py-1.5 shadow-xl shadow-navy-950/20">
          <p className="px-3 pb-1.5 pt-1 text-xs font-medium text-muted">Workspaces</p>
          {orgs.map((o, i) => {
            const active = o.id === current.id;
            return (
              <button key={o.id} type="button" role="menuitemradio" aria-checked={active}
                ref={(el) => { itemsRef.current[i] = el; }} onClick={() => choose(o.id)}
                className={cls("flex w-full items-center gap-3 px-3 py-2 text-left text-sm focus:bg-subtle focus:outline-none hover:bg-subtle",
                  active ? "text-heading" : "text-ink")}>
                <span className={cls("flex h-7 w-7 shrink-0 items-center justify-center rounded text-xs font-semibold",
                  o.is_demo ? "bg-orange-500/15 text-accent" : "bg-navy-700 text-white")} aria-hidden="true">
                  {o.name.trim().slice(0, 1).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{o.name}</span>
                  <span className="block text-xs text-muted">{o.is_demo ? "Sample data, read-only" : o.role ? ROLE_LABEL[o.role] : ""}</span>
                </span>
                {active && <span className="text-pass" aria-hidden="true"><svg width="16" height="16" viewBox="0 0 20 20"><path d="m5 10.5 3.2 3L15 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg></span>}
              </button>
            );
          })}
          <div className="my-1.5 border-t border-line" />
          <button type="button" role="menuitem" ref={(el) => { itemsRef.current[orgs.length] = el; }}
            onClick={() => { setOpen(false); navigate("/onboarding?new=1"); }}
            className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm font-medium text-link hover:bg-subtle focus:bg-subtle focus:outline-none">
            <span className="flex h-7 w-7 items-center justify-center rounded border border-dashed border-line" aria-hidden="true"><IconPlus /></span>
            Create a workspace
          </button>
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const { current } = useWorkspace();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  const initials = (user?.full_name || user?.email || "?").split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
  const onLogout = async () => {
    try { await logout(); navigate("/login", { replace: true }); } catch (e) { setErr(errorText(e)); }
  };
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((v) => !v)} aria-haspopup="menu" aria-expanded={open} aria-label="Account menu"
        className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-700 text-[13px] font-semibold text-white hover:bg-navy-800">
        {initials}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-11 z-30 w-64 rounded-lg border border-line bg-surface p-1.5 shadow-xl">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium text-heading">{user?.full_name || user?.email}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
            {current?.role && <p className="mt-1 text-xs text-muted">{ROLE_LABEL[current.role]} in {current.name}</p>}
          </div>
          <div className="my-1 border-t border-line" />
          <button role="menuitem" onClick={onLogout} className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-ink hover:bg-subtle">
            <IconLogout />Sign out
          </button>
          {err && <p className="px-3 py-1 text-xs text-fail">{err}</p>}
        </div>
      )}
    </div>
  );
}

function ThemeToggle() {
  const [theme, toggle] = useTheme();
  return (
    <button onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
      className="flex h-9 w-9 items-center justify-center rounded-md text-muted hover:bg-subtle hover:text-heading">
      {theme === "dark" ? <IconSun /> : <IconMoon />}
    </button>
  );
}

function VerifyBanner() {
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [err, setErr] = useState("");
  const resend = async () => {
    setState("sending");
    try { await api("/auth/verify-email/resend/", { method: "POST" }); setState("sent"); }
    catch (e) { setErr(errorText(e)); setState("error"); }
  };
  return (
    <div className="border-b border-warn/25 bg-warn-bg px-4 py-2.5 text-sm text-warn sm:px-8">
      Confirm your email address to add domains, invite teammates and receive alerts.{" "}
      {state === "sent" ? <strong>Confirmation link sent.</strong> : (
        <button onClick={resend} disabled={state === "sending"} className="font-semibold underline underline-offset-2">
          {state === "sending" ? "Sending…" : "Resend confirmation link"}
        </button>
      )}
      {state === "error" && <span className="ml-2 font-medium text-fail">{err}</span>}
    </div>
  );
}

function DemoBanner({ orgs }: { orgs: Organization[] }) {
  const { select } = useWorkspace();
  const real = orgs.find((o) => !o.is_demo);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-orange-500/30 bg-orange-500/10 px-4 py-2.5 text-sm text-heading sm:px-8">
      <span>You are looking at sample data for six made-up client domains. Nothing here can be changed.</span>
      {real ? (
        <button onClick={() => select(real.id)} className="font-semibold text-link underline underline-offset-2">Switch to {real.name}</button>
      ) : (
        <Link to="/onboarding?new=1" className="font-semibold text-link underline underline-offset-2">Create your own workspace</Link>
      )}
    </div>
  );
}

export default function AppLayout() {
  const { user } = useAuth();
  const { orgs, current } = useWorkspace();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => { setOpen(false); }, [loc.pathname]);
  return (
    <div className="min-h-screen bg-canvas lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 lg:block"><Sidebar /></aside>
      {open && (
        <div className="fixed inset-0 z-30 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-navy-950/55" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] shadow-xl">
            <button onClick={() => setOpen(false)} aria-label="Close navigation"
              className="absolute right-3 top-6 z-10 rounded-md p-1.5 text-white hover:bg-white/10"><IconClose /></button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
      <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-surface/95 px-4 backdrop-blur sm:px-8">
        <button onClick={() => setOpen(true)} aria-label="Open navigation" aria-expanded={open}
          className="rounded-md p-2 text-heading hover:bg-subtle lg:hidden"><IconMenu /></button>
        <div className="min-w-0 flex-1"><WorkspaceSwitcher /></div>
        <ThemeToggle />
        <UserMenu />
      </header>
      {user && !user.email_verified && <VerifyBanner />}
      {current?.is_demo && <DemoBanner orgs={orgs} />}
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-8"><Outlet /></main>
    </div>
  );
}
