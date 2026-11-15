# Plans and billing

Code: `backend/apps/billing/`. Tests: `backend/tests/test_billing.py`.

## Plans

| Plan | Monthly | Yearly | Domains | Members | Alert channels | DMARC history |
| --- | --- | --- | --- | --- | --- | --- |
| Free | $0 | $0 | 1 | 1 | Email | 30 days |
| Starter | $19 | $190 | 5 | 3 | Email, Slack, Teams | 90 days |
| Agency | $79 | $790 | 25 | 10 | All | 90 days |
| MSP | $199 | $1,990 | 100 | Unlimited | All | 90 days |
| Enterprise | Contract | | 1,000+ (custom) | Unlimited | All | 90 days |

The catalogue lives in `plans.py`. Yearly prices give two months free.

- **Trial:** every new workspace (and every workspace that existed when billing shipped) starts a 14-day Agency trial with no card (`BILLING_TRIAL_DAYS`). When it ends, the workspace is on Free unless it subscribed.
- **Demo workspace:** demo workspaces have no billing.

## Limits

Limits are checked in `limits.py`. A blocked action returns HTTP 403 with code `plan_limit` and a message naming the plan.

| Limit | Where it is checked |
| --- | --- |
| Domains | Adding a domain |
| Members | Inviting: members and pending invitations count together |
| Channel types | Creating an alert channel |
| DMARC period | DMARC report views |
| Scheduled scans | Only the oldest *N* verified domains are scanned on schedule (`monitored_domain_ids`) |

Over the limit after a downgrade, nothing is deleted. The extra domains keep their history but are not scanned until the workspace upgrades. The billing page shows how many domains are affected.

## Stripe

- **Checkout:** Stripe Checkout in subscription mode. It requires a billing address, collects tax IDs (EU VAT and similar), allows promotion codes, and turns on automatic tax when `STRIPE_AUTOMATIC_TAX=true` (Stripe Tax must be active).
- **Customer Portal:** handles cards, invoices, switching plans (prorated) and cancelling (at period end). `stripe_setup` creates and updates a portal configuration tagged `metadata.dv=1`.
- **Prices:** found by lookup key `dv_<plan>_<monthly|yearly>`, so prices can change in Stripe without a code change.
- **Webhook:** `POST /api/v1/billing/stripe/webhook/`, verified with `STRIPE_WEBHOOK_SECRET`. Each event ID is processed once (`StripeEvent`), and a failure removes the record so Stripe retries.

| Event | Effect |
| --- | --- |
| `checkout.session.completed` | Re-read the subscription and apply it |
| `customer.subscription.created/updated/deleted` | Apply plan, interval, status, renewal date, cancel-at-period-end |
| `invoice.payment_failed` | Status `past_due` (the plan is kept while Stripe retries); email the owners |

Status mapping: active/trialing → `active`; past_due/unpaid → `past_due` (plan kept); canceled/incomplete_expired → `canceled` (Free).

Only the workspace **owner** can open Checkout or the portal. Admins see the plan and a banner when the trial ends within 7 days or a payment failed.

## Operations

| Task | Command |
| --- | --- |
| Create or update products, prices and the portal in Stripe | `./dc exec backend python manage.py stripe_setup` |
| Give a workspace a plan by hand (Enterprise, support) | `./dc exec backend python manage.py set_plan "<workspace name or id>" enterprise --domains 1000` |

The webhook endpoint must receive these events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`.
