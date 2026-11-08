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
  id: string; name: string; slug: string; timezone: string; status: string; role: Role | null; created_at: string;
};
export type Membership = { id: string; role: Role; created_at: string; user: { id: string; email: string; full_name: string } };
export type Invitation = {
  id: string; email: string; role: Role; invited_by: string | null; created_at: string; expires_at: string;
};

export const ROLE_LABEL: Record<Role, string> = { owner: "Owner", admin: "Admin", member: "Member", viewer: "Viewer" };
export const ROLE_RANK: Record<Role, number> = { viewer: 0, member: 1, admin: 2, owner: 3 };
export const isManager = (r: Role | null | undefined) => r === "owner" || r === "admin";
