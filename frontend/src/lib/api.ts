// Thin fetch wrapper: same-origin cookies + CSRF header read fresh on every
// write (Django rotates the token on login).
export type FieldErrors = Record<string, string[]>;
export type ApiError = { status: number; code: string; message: string; details?: FieldErrors; retryAfter?: number };

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)dv_csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function ensureCsrf(): Promise<void> {
  if (!csrfToken()) await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();
  const headers = new Headers(rest.headers);
  headers.set("Accept", "application/json");
  let body = rest.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    await ensureCsrf();
    headers.set("X-CSRFToken", csrfToken());
  }
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...rest, method, headers, body, credentials: "same-origin" });
  } catch {
    throw { status: 0, code: "network_error", message: "Cannot reach the server. Check your connection." } as ApiError;
  }
  if (res.status === 204 || res.status === 202) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = data?.error ?? {};
    throw {
      status: res.status,
      code: e.code ?? "error",
      message: e.message ?? res.statusText,
      details: normaliseDetails(e.details),
      retryAfter: typeof e.retry_after_seconds === "number" ? e.retry_after_seconds : undefined,
    } as ApiError;
  }
  return data as T;
}

function normaliseDetails(d: unknown): FieldErrors | undefined {
  if (!d || typeof d !== "object" || Array.isArray(d)) return undefined;
  const out: FieldErrors = {};
  for (const [k, v] of Object.entries(d as Record<string, unknown>)) {
    out[k] = Array.isArray(v) ? v.map(String) : [String(v)];
  }
  return out;
}

/** First human-readable message from an error, preferring field details. */
export function errorText(err: unknown, fallback = "Something went wrong. Please try again."): string {
  const e = err as ApiError;
  if (e?.status === 429) {
    const mins = e.retryAfter ? Math.max(1, Math.ceil(e.retryAfter / 60)) : null;
    return `Too many attempts. Please try again${mins ? ` in about ${mins} minute${mins === 1 ? "" : "s"}` : " later"}.`;
  }
  if (e?.details) {
    const first = Object.values(e.details).flat()[0];
    if (first) return first;
  }
  return e?.message || fallback;
}

export type User = { id: string; email: string; full_name: string; email_verified: boolean; is_staff?: boolean; created_at: string };
export type Role = "owner" | "admin" | "member" | "viewer";
export type Organization = {
  id: string; name: string; slug: string; timezone: string; status: string; is_demo: boolean; role: Role | null; created_at: string;
  billing: { plan: PlanKey; status: BillingStatus; trial_ends_at: string | null } | null;
};
export type Membership = { id: string; role: Role; created_at: string; user: { id: string; email: string; full_name: string } };
export type Invitation = {
  id: string; email: string; role: Role; invited_by: string | null; created_at: string; expires_at: string;
};

export const ROLE_LABEL: Record<Role, string> = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" };
export const ROLE_RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };
export const isManager = (r: Role | null | undefined) => r === "owner" || r === "admin";

export const canWrite = (o: Organization | null | undefined) => !!o && !o.is_demo && (o.role === "owner" || o.role === "admin" || o.role === "member");

/* ---------- Domains & scans ---------- */
export type CheckName = "spf" | "dkim" | "dmarc" | "mx" | "dns";
export type CheckStatus = "pass" | "warn" | "fail" | "error";
export type Finding = { code: string; severity: "critical" | "warning" | "info"; title: string; detail: string; fix: string };
export type CheckResult = {
  check: CheckName; status: CheckStatus; summary: string; record: string | null; findings: Finding[];
  data: Record<string, unknown>;
};
export type ScanSummary = {
  id: string; status: "queued" | "running" | "completed" | "failed"; trigger: string; health_score: number | null;
  overall_status: CheckStatus | ""; critical_count: number; warning_count: number;
  summary: Partial<Record<CheckName, CheckStatus>>; created_at: string; completed_at: string | null;
};
export type ScanDetail = ScanSummary & { results: Partial<Record<CheckName, CheckResult>>; error: string; started_at: string | null };
export type Domain = {
  id: string; name: string; is_verified: boolean; verified_at: string | null; monitoring_enabled: boolean;
  dkim_selectors: string[]; dns_watch_names: string[]; created_at: string; latest_scan: ScanSummary | null;
  verification: { type: string; host: string; value: string; failing_since: string | null };
};
export type OverviewFinding = Finding & { domain_id: string; domain: string; check: CheckName };
export type Overview = {
  domains: { total: number; verified: number; unverified: number; scanned: number };
  health: { pass: number; warn: number; fail: number; error: number; average_score: number | null };
  issues: { critical: number; warning: number };
  dmarc_policies: { reject: number; quarantine: number; none: number; missing: number };
  checks: Record<CheckName, Partial<Record<CheckStatus, number>>>;
  score_trend: { date: string; score: number | null }[];
  attention: { domain_id: string; domain: string; score: number | null; status: CheckStatus; top_finding: string | null }[];
  findings: OverviewFinding[];
  tls: CertSummary & { soonest: CertRow[] };
  recent_changes: (DnsChange & { domain_id: string; domain: string })[];
  alerts: { open: number; critical: number };
};

export type DnsRecordRow = { name: string; type: string; ttl: number | null; values: string[]; last_changed: string | null; tracked_since: string | null };
export type NameServer = { ns: string; ip: string; authoritative: boolean; serial: number | null; error: string };
export type DnsRecords = { scanned_at: string | null; records: DnsRecordRow[]; name_servers: NameServer[];
  soa?: { primary: string; serial: number; refresh: number; retry: number; expire: number; minimum: number } | null; hosts?: string[] };
export type DnsChange = { id: string; name: string; rtype: string; kind: "added" | "removed" | "changed" | "ttl";
  old_values: string[]; new_values: string[]; old_ttl: number | null; new_ttl: number | null; detected_at: string };
export type PropagationServer = { kind: "authoritative" | "public"; server: string; ip: string; values?: string[]; ttl?: number | null;
  status: "match" | "different" | "missing" | "error"; error?: string };
export type Propagation = { name: string; type: string; zone: string; expected: string[]; servers: PropagationServer[];
  matched: number; answered: number; total: number; propagated: boolean };

export type CertRow = {
  id: string; hostname: string; port: number; label: string; enabled: boolean; domain_id: string; domain: string;
  domain_verified: boolean; status: CheckStatus | null; scanned_at: string | null; pending: boolean;
  days_left: number | null; not_after: string | null; issuer: string | null; tls_version: string | null;
  findings: Finding[]; error: string;
};
export type CertSummary = {
  total: number; checked: number; expired: number; within_7: number; within_30: number; failing: number; healthy: number;
  unreachable: number; by_month: { month: string; count: number }[];
};
export type HostScan = {
  id: string; status: "queued" | "completed" | "failed"; result_status: CheckStatus | ""; created_at: string;
  completed_at: string | null; not_after: string | null; error: string; findings: Finding[];
  certificate: {
    hostname?: string; ip?: string; tls_version?: string; cipher?: string; subject_cn?: string; sans?: string[];
    issuer?: string; issuer_org?: string; not_before?: string; not_after?: string; signature_algorithm?: string;
    key_type?: string; key_bits?: number | null; trusted?: boolean; hostname_match?: boolean; hsts?: string | null;
    self_signed?: boolean;
  };
};
export const CHECK_LABEL: Record<CheckName, string> = { spf: "SPF", dkim: "DKIM", dmarc: "DMARC", mx: "MX", dns: "DNS" };
export const CHECK_LONG: Record<CheckName, string> = {
  spf: "Sender Policy Framework", dkim: "DomainKeys Identified Mail",
  dmarc: "Domain-based Message Authentication, Reporting and Conformance", mx: "Mail exchangers",
  dns: "Name servers, SOA, host records and TTLs",
};

// --- DMARC reports -------------------------------------------------------------
export type DmarcVerdict = "pass" | "warn" | "fail";
export type DmarcIp = {
  ip: string; ptr: string; messages: number; passed: number; spf_aligned: number; dkim_aligned: number;
  dkim_domains: string[]; header_from: string[];
};
export type DmarcSender = {
  name: string; known: boolean; messages: number; passed: number; spf_aligned: number; dkim_aligned: number;
  pass_rate: number | null; verdict: DmarcVerdict; ips: DmarcIp[];
};
export type DmarcStatus = "receiving" | "waiting" | "not_configured" | "no_dmarc" | "unknown";
export type DmarcDomainRow = {
  id: string; name: string; messages: number; passed: number; pass_rate: number | null; last_report: string | null;
  status: DmarcStatus; policy: string | null; suggested_record: string;
};
export type DmarcTotals = {
  messages: number; passed: number; failed: number; pass_rate: number | null; quarantined: number; rejected: number;
  senders: number; unauthenticated_senders: number;
};
export type DmarcSummary = {
  days: number; since: string; totals: DmarcTotals; by_day: { day: string; passed: number; failed: number }[];
  senders: DmarcSender[]; rua_address: string;
};
export type DmarcReportRow = {
  id: string; reporter: string; date_begin: string; date_end: string; messages: number;
  policy: Record<string, string>; source: "mail" | "upload" | "demo"; received_at: string;
};
export type OrgDmarc = DmarcSummary & { domains: DmarcDomainRow[] };
export type DomainDmarc = ({ verified: true; domain: DmarcDomainRow; reports: DmarcReportRow[] } & DmarcSummary) | { verified: false; rua_address: string };

// --- Alerts ---------------------------------------------------------------------
export type AlertKind = "check" | "certificate" | "dns_change" | "dmarc_sender";
export type AlertSeverity = "critical" | "warning" | "info";
export type AlertItem = {
  id: string; kind: AlertKind; severity: AlertSeverity; status: "open" | "resolved" | "notice"; title: string; detail: string;
  domain: string | null; domain_name: string | null; opened_at: string; updated_at: string; resolved_at: string | null;
  acknowledged_by: string | null; acknowledged_at: string | null;
};
export type AlertList = { counts: { open: number; critical: number; unacknowledged: number }; alerts: AlertItem[] };
export type ChannelType = "email" | "slack" | "teams" | "webhook";
export type AlertChannel = {
  id: string; type: ChannelType; name: string; enabled: boolean; url: string; notify_managers: boolean; recipients: string[];
  events: AlertKind[]; min_severity: "critical" | "warning"; secret: string | null; last_sent_at: string | null; last_error: string; created_at: string;
};
export const ALERT_KIND_LABEL: Record<AlertKind, string> = {
  check: "Failing checks", certificate: "Certificates", dns_change: "DNS changes", dmarc_sender: "New DMARC senders",
};

// --- Billing ----------------------------------------------------------------------
export type PlanKey = "free" | "starter" | "agency" | "msp" | "enterprise";
export type BillingStatus = "free" | "trialing" | "active" | "past_due" | "canceled";
export type PlanInfo = {
  key: PlanKey; name: string; price: { month: number; year: number } | null; domains: number; members: number | null;
  channels: ChannelType[]; dmarc_days: number; summary: string;
};
export type Billing =
  | { demo: true; plans: PlanInfo[] }
  | {
      demo: false; plan: PlanKey; subscribed_plan: PlanKey; status: BillingStatus; interval: "" | "month" | "year";
      trial_ends_at: string | null; trial_active: boolean; current_period_end: string | null; cancel_at_period_end: boolean;
      has_customer: boolean; limits: { domains: number; members: number | null; channels: ChannelType[]; dmarc_days: number };
      usage: { domains: number; members: number; pending_invitations: number; unmonitored_domains: number };
      can_manage: boolean; online_payments: boolean; plans: PlanInfo[];
    };
