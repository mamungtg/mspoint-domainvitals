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

export type User = { id: string; email: string; full_name: string; email_verified: boolean; created_at: string };
export type Role = "owner" | "admin" | "member" | "viewer";
export type Organization = {
  id: string; name: string; slug: string; timezone: string; status: string; is_demo: boolean; role: Role | null; created_at: string;
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
export type CheckName = "spf" | "dkim" | "dmarc" | "mx";
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
  dkim_selectors: string[]; created_at: string; latest_scan: ScanSummary | null;
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
};

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
export const CHECK_LABEL: Record<CheckName, string> = { spf: "SPF", dkim: "DKIM", dmarc: "DMARC", mx: "MX" };
export const CHECK_LONG: Record<CheckName, string> = {
  spf: "Sender Policy Framework", dkim: "DomainKeys Identified Mail",
  dmarc: "Domain-based Message Authentication, Reporting and Conformance", mx: "Mail exchangers",
};
