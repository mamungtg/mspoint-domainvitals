// Thin fetch wrapper: same-origin cookies + CSRF header read fresh on every
// write (Django rotates the token on login).
export type ApiError = { status: number; code: string; message: string; details?: unknown };

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)dv_csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function ensureCsrf(): Promise<void> {
  if (!csrfToken()) await fetch("/api/v1/auth/csrf/", { credentials: "same-origin" });
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    await ensureCsrf();
    headers.set("X-CSRFToken", csrfToken());
  }
  const res = await fetch(`/api/v1${path}`, { ...init, method, headers, credentials: "same-origin" });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = body?.error ?? {};
    throw { status: res.status, code: e.code ?? "error", message: e.message ?? res.statusText, details: e.details } as ApiError;
  }
  return body as T;
}

export type User = { id: string; email: string; full_name: string; email_verified: boolean };
