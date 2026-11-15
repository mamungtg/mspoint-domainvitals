import { useState } from "react";
import { api, errorText } from "../lib/api";
import { Alert, Button } from "./ui";

const AFTER_VERIFY = "dv_after_verify";

/** Where to go after confirming the address (e.g. an invitation), kept across the email round trip. */
export function rememberNext(next: string | null) {
  try { if (next) localStorage.setItem(AFTER_VERIFY, next); else localStorage.removeItem(AFTER_VERIFY); } catch { /* storage blocked */ }
}
export function takeNext(): string | null {
  try { const v = localStorage.getItem(AFTER_VERIFY); localStorage.removeItem(AFTER_VERIFY); return v; } catch { return null; }
}

export default function ResendConfirmation({ email, variant = "secondary" }: { email: string; variant?: "secondary" | "ghost" }) {
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState("");
  async function send() {
    setState("sending"); setError("");
    try { await api("/auth/verify-email/resend/", { method: "POST", json: { email } }); setState("sent"); }
    catch (e) { setError(errorText(e)); setState("idle"); }
  }
  return (
    <div className="space-y-3">
      {state === "sent"
        ? <Alert tone="success">A new confirmation link is on its way to {email}. It can take a minute; check your spam folder too.</Alert>
        : <Button type="button" variant={variant} busy={state === "sending"} disabled={!email} onClick={send}>Send a new confirmation link</Button>}
      {error && <Alert>{error}</Alert>}
    </div>
  );
}
