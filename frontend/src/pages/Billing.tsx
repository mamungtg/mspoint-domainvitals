import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Alert, Badge, Button, Card, cls, PageHeader, Spinner, StatusPill } from "../components/ui";
import { api, Billing as BillingData, BillingStatus, errorText, PlanInfo, PlanKey } from "../lib/api";
import { useApi } from "../lib/useApi";
import { useWorkspace } from "../lib/workspace";

const SALES = "mailto:sales@mspointit.com?subject=DomainVitals%20Enterprise";
const CHANNEL_NAMES: Record<string, string> = { email: "Email", slack: "Slack", teams: "Teams", webhook: "Webhooks" };
const STATUS: Record<BillingStatus, { label: string; tone: "pass" | "warn" | "fail" | "none" }> = {
  free: { label: "Free", tone: "none" },
  trialing: { label: "Free trial", tone: "pass" },
  active: { label: "Active", tone: "pass" },
  past_due: { label: "Payment overdue", tone: "fail" },
  canceled: { label: "Canceled", tone: "none" },
};
const date = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" }) : "");

function Usage({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const r = limit ? Math.min(1, used / limit) : 0;
  return (
    <div>
      <div className="mb-1.5 flex justify-between text-sm">
        <span className="text-ink">{label}</span>
        <span className="font-medium tabular-nums text-heading">{used}{limit !== null ? ` of ${limit}` : " (unlimited)"}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-subtle" aria-hidden="true">
        <div className={cls("h-full rounded-full", limit !== null && used > limit ? "bg-fail" : r >= 0.9 ? "bg-warn" : "bg-navy-700 [[data-theme=dark]_&]:bg-[#7fb2ec]")}
          style={{ width: `${limit === null ? 4 : Math.max(2, r * 100)}%` }} />
      </div>
    </div>
  );
}

export default function Billing() {
  const { current } = useWorkspace();
  const [params, setParams] = useSearchParams();
  const checkout = params.get("checkout");
  const { data, error, reload } = useApi<BillingData>(current ? `/organizations/${current.id}/billing/` : null);
  const [interval, setInterval_] = useState<"month" | "year">("year");
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");

  // After Stripe Checkout the webhook can take a few seconds; refresh until the plan shows.
  const waiting = checkout === "success" && data && !data.demo && data.status !== "active";
  useEffect(() => {
    if (!waiting) return;
    let n = 0;
    const t = window.setInterval(() => { n += 1; void reload(); if (n > 15) window.clearInterval(t); }, 2000);
    return () => window.clearInterval(t);
  }, [waiting, reload]);
  useEffect(() => { if (data && !data.demo && data.interval) setInterval_(data.interval); }, [data]);

  async function go(kind: string, path: string, body?: unknown) {
    setBusy(kind); setActionError("");
    try {
      const r = await api<{ url: string }>(path, { method: "POST", json: body });
      window.location.assign(r.url);
    } catch (e) { setActionError(errorText(e)); setBusy(""); }
  }

  const header = <PageHeader title="Plan and billing" description="Your plan, what it includes, and invoices." />;
  if (error) return <>{header}<Alert>{error}</Alert></>;
  if (!data || !current) return <>{header}<Spinner /></>;
  if (data.demo) return <>{header}<Alert tone="info">The sample workspace has no plan. Switch to your own workspace to see billing.</Alert></>;

  const subscribed = (data.status === "active" || data.status === "past_due") && data.has_customer;
  const canPay = data.can_manage && data.online_payments;
  const checkoutPlan = (p: PlanKey) => go(`plan-${p}`, `/organizations/${current.id}/billing/checkout/`, { plan: p, interval });
  const portal = () => go("portal", `/organizations/${current.id}/billing/portal/`);
  const current_ = data.plans.find((p) => p.key === data.plan)!;

  return (
    <>
      {header}
      <div className="space-y-6">
        {checkout === "success" && (
          <Alert tone="success">
            {waiting ? "Thank you. Payment received; activating your plan…" : "Thank you. Your subscription is active."}{" "}
            <button className="underline" onClick={() => setParams({}, { replace: true })}>Dismiss</button>
          </Alert>
        )}
        {checkout === "cancel" && <Alert tone="info">Checkout was cancelled. Nothing was charged.</Alert>}
        {actionError && <Alert>{actionError}</Alert>}
        {data.status === "past_due" && (
          <Alert tone="error">The last payment failed. Stripe will retry automatically; update the card in the billing portal to avoid moving to the Free plan.</Alert>
        )}

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card title="Current plan">
            <div className="flex flex-wrap items-center gap-3">
              <p className="font-display text-2xl font-semibold text-heading">{current_.name}</p>
              <StatusPill status={STATUS[data.status].tone} label={STATUS[data.status].label} />
              {data.interval && <Badge>{data.interval === "year" ? "Billed yearly" : "Billed monthly"}</Badge>}
            </div>
            <p className="mt-2 text-sm text-muted">
              {data.trial_active && data.trial_ends_at && `Trial of the Agency plan until ${date(data.trial_ends_at)}. No card needed; afterwards the workspace moves to Free unless you choose a plan.`}
              {data.status === "active" && data.current_period_end && (data.cancel_at_period_end
                ? `Cancels on ${date(data.current_period_end)}. You keep the plan until then.`
                : `Renews on ${date(data.current_period_end)}.`)}
              {data.status === "canceled" && "Your subscription ended. Choose a plan to monitor more domains."}
              {data.status === "free" && "Choose a plan to monitor more domains and add your team."}
            </p>
            {data.can_manage && data.has_customer && (
              <div className="mt-4">
                <Button variant="secondary" busy={busy === "portal"} onClick={portal} disabled={!data.online_payments}>
                  Manage billing, invoices and card
                </Button>
              </div>
            )}
            {!data.can_manage && <p className="mt-4 text-sm text-muted">Only the workspace owner can change the plan.</p>}
          </Card>
          <Card title="Usage">
            <div className="space-y-4">
              <Usage label="Domains" used={data.usage.domains} limit={data.limits.domains} />
              <Usage label="Team members and pending invitations" used={data.usage.members + data.usage.pending_invitations} limit={data.limits.members} />
              {data.usage.unmonitored_domains > 0 && (
                <Alert tone="warning">
                  {data.usage.unmonitored_domains} verified domain{data.usage.unmonitored_domains === 1 ? " is" : "s are"} over the plan limit and not scanned on schedule. Nothing has been deleted; upgrade to monitor them again.
                </Alert>
              )}
            </div>
          </Card>
        </div>

        {!data.online_payments && data.can_manage && (
          <Alert tone="info">Online payments are being set up. To change plans now, email sales@mspointit.com.</Alert>
        )}

        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Plans</h2>
            <p className="text-sm text-muted">Prices in US dollars. Taxes may apply depending on your country.</p>
          </div>
          <div role="group" aria-label="Billing period" className="inline-flex rounded-md border border-line bg-surface p-0.5">
            {(["month", "year"] as const).map((i) => (
              <button key={i} type="button" aria-pressed={interval === i} onClick={() => setInterval_(i)}
                className={cls("rounded px-3 py-1 text-sm font-medium", interval === i ? "bg-navy-700 text-white" : "text-muted hover:text-heading")}>
                {i === "month" ? "Monthly" : "Yearly, 2 months free"}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {data.plans.map((p) => (
            <PlanCard key={p.key} p={p} interval={interval} isCurrent={p.key === data.plan && !data.trial_active}
              trial={data.trial_active && p.key === "agency"}>
              {p.key === "enterprise" ? (
                <a href={SALES} className="block"><Button variant="secondary" className="w-full">Contact sales</Button></a>
              ) : p.key === data.plan && !data.trial_active ? (
                <Button variant="secondary" className="w-full" disabled>Current plan</Button>
              ) : p.key === "free" ? (
                subscribed ? <Button variant="ghost" className="w-full" disabled={!canPay} busy={busy === "portal"} onClick={portal}>Cancel in billing portal</Button> : null
              ) : subscribed ? (
                <Button variant="secondary" className="w-full" disabled={!canPay} busy={busy === "portal"} onClick={portal}>Switch in billing portal</Button>
              ) : (
                <Button className="w-full" disabled={!canPay} busy={busy === `plan-${p.key}`} onClick={() => checkoutPlan(p.key)}>
                  Choose {p.name}
                </Button>
              )}
            </PlanCard>
          ))}
        </div>
        <p className="text-xs text-muted">
          Payments are processed by Stripe; card details never reach DomainVitals. Downgrading keeps every domain and its history:
          domains above the new limit stop being scanned until you upgrade again. Subscriptions are sold by MSPoint LLC.
        </p>
      </div>
    </>
  );
}

function PlanCard({ p, interval, isCurrent, trial, children }: { p: PlanInfo; interval: "month" | "year"; isCurrent: boolean; trial: boolean; children: React.ReactNode }) {
  const price = p.price ? p.price[interval] : null;
  const features = [
    `${p.domains.toLocaleString()} domain${p.domains === 1 ? "" : "s"}${p.key === "enterprise" ? "+" : ""}`,
    p.members === null ? "Unlimited team members" : `${p.members} team member${p.members === 1 ? "" : "s"}`,
    `Alerts by ${p.channels.map((c) => CHANNEL_NAMES[c]).join(", ")}`,
    `${p.dmarc_days} days of DMARC reports`,
    "SPF, DKIM, DMARC, DNS and SSL monitoring",
  ];
  return (
    <div className={cls("flex flex-col rounded-lg border bg-surface p-5", isCurrent || trial ? "border-orange-500 ring-1 ring-orange-500" : "border-line")}>
      <div className="flex items-center justify-between gap-2">
        <p className="font-display text-lg font-semibold text-heading">{p.name}</p>
        {trial && <Badge tone="brand">Your trial</Badge>}
        {p.key === "agency" && !trial && <Badge tone="warn">Popular</Badge>}
      </div>
      <p className="mt-1 min-h-[2.5rem] text-sm text-muted">{p.summary}</p>
      <p className="mt-3">
        {price === null ? <span className="font-display text-2xl font-semibold text-heading">Custom</span> : (
          <>
            <span className="font-display text-3xl font-semibold text-heading">${interval === "year" && price ? Math.round(price / 12) : price}</span>
            <span className="text-sm text-muted"> /month</span>
          </>
        )}
      </p>
      <p className="min-h-[1.25rem] text-xs text-muted">{price && interval === "year" ? `$${price.toLocaleString()} billed yearly` : price ? "Billed monthly" : ""}</p>
      <ul className="mt-4 flex-1 space-y-2 text-sm text-ink">
        {features.map((f) => (
          <li key={f} className="flex gap-2">
            <svg viewBox="0 0 20 20" className="mt-0.5 h-4 w-4 shrink-0 text-pass" aria-hidden="true"><path d="m5 10.5 3.2 3L15 7" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
            {f}
          </li>
        ))}
      </ul>
      <div className="mt-5">{children}</div>
    </div>
  );
}
