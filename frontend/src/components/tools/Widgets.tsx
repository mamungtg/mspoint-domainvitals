import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { DaysLeft, FindingList } from "../CertTable";
import CheckCard from "../CheckCard";
import { PropagationResult } from "../DnsRecords";
import { Alert, Button, Field, Input, ScoreRing, Select, StatusPill } from "../ui";
import { api, ApiError, CheckName, CheckResult, errorText, Finding, Propagation } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const ORDER: CheckName[] = ["dmarc", "spf", "dkim", "mx", "dns"];

function friendlyError(err: unknown, signedIn: boolean): string {
  const e = err as ApiError;
  if (e.status === 429) {
    return signedIn
      ? "You've run a lot of checks in the last hour. Please try again in a few minutes."
      : "You've reached the free limit of checks for this hour. Create a free account to keep checking, or try again later.";
  }
  return e.details?.domain?.[0] ?? e.details?.hostname?.[0] ?? e.details?.name?.[0] ?? errorText(err);
}

/** Keeps the input in the URL (?q=) so results can be shared and bookmarked. */
function useQueryValue(): [string, (v: string) => void] {
  const [params, setParams] = useSearchParams();
  return [params.get("q") ?? "", (v) => setParams(v ? { q: v } : {}, { replace: true })];
}

type CheckResponse = { domain: string; score?: number; results: Partial<Record<CheckName, CheckResult>> };

export function DomainCheckWidget({ check, onResult }: { check: CheckName | "all"; onResult: (domain: string | null) => void }) {
  const { user } = useAuth();
  const [q, setQ] = useQueryValue();
  const [domain, setDomain] = useState(q);
  const [selector, setSelector] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<CheckResponse | null>(null);

  async function run(name = domain) {
    if (!name.trim()) return;
    setBusy(true); setError(""); setResult(null); onResult(null);
    try {
      const r = await api<CheckResponse>("/tools/check/", { method: "POST", json: { domain: name, check, selector } });
      setResult(r); setQ(r.domain); onResult(r.domain);
    } catch (err) { setError(friendlyError(err, !!user)); } finally { setBusy(false); }
  }
  useEffect(() => { if (q) void run(q); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); void run(); }} noValidate
        className={check === "dkim" ? "grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end" : "grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end"}>
        <Field label="Domain"><Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="example.com" autoComplete="off" spellCheck={false} inputMode="url" /></Field>
        {check === "dkim" && <Field label="Selector (optional)"><Input value={selector} onChange={(e) => setSelector(e.target.value)} placeholder="google" spellCheck={false} /></Field>}
        <Button type="submit" busy={busy} disabled={!domain.trim()}>Check</Button>
      </form>
      {error && <div className="mt-5"><Alert>{error}</Alert></div>}
      {result && (
        <div className="mt-6 space-y-5">
          {result.score !== undefined && (
            <div className="flex items-center gap-5 rounded-lg border border-line bg-surface px-5 py-4">
              <ScoreRing score={result.score} size={72} />
              <div><p className="font-display text-[17px] font-semibold text-heading">{result.domain}</p>
                <p className="text-sm text-muted">Checked just now from public DNS.</p></div>
            </div>
          )}
          <div className={check === "all" ? "grid gap-5 xl:grid-cols-2" : ""}>
            {ORDER.filter((c) => result.results[c]).map((c) => <CheckCard key={c} name={c} result={result.results[c]} />)}
          </div>
        </div>
      )}
    </div>
  );
}

type SslResponse = {
  hostname: string; port: number; days_left: number | null;
  certificate: { subject_cn: string; sans: string[]; issuer: string; issuer_org: string; not_after: string; not_before?: string; tls_version: string; key_type: string; key_bits: number; signature_algorithm: string };
  result: { status: "pass" | "warn" | "fail"; summary?: string; findings: Finding[] };
};

export function SslWidget({ onResult }: { onResult: (domain: string | null) => void }) {
  const { user } = useAuth();
  const [q, setQ] = useQueryValue();
  const [host, setHost] = useState(q);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [r, setR] = useState<SslResponse | null>(null);

  async function run(name = host) {
    if (!name.trim()) return;
    setBusy(true); setError(""); setR(null); onResult(null);
    try {
      const res = await api<SslResponse>("/tools/ssl/", { method: "POST", json: { hostname: name } });
      setR(res); setQ(res.hostname); onResult(res.hostname.replace(/^www\./, ""));
    } catch (err) { setError(friendlyError(err, !!user)); } finally { setBusy(false); }
  }
  useEffect(() => { if (q) void run(q); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const c = r?.certificate;
  const rows: [string, string][] = c ? [
    ["Issued to", c.subject_cn || "–"],
    ["Also covers", c.sans.filter((s) => s !== c.subject_cn).slice(0, 8).join(", ") || "–"],
    ["Issuer", c.issuer_org || c.issuer || "–"],
    ["Expires", c.not_after ? new Date(c.not_after).toUTCString() : "–"],
    ["Protocol", c.tls_version || "–"],
    ["Key", c.key_type ? `${c.key_type} ${c.key_bits} bits` : "–"],
    ["Signature", c.signature_algorithm || "–"],
  ] : [];
  return (
    <div>
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); void run(); }} className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end" noValidate>
        <Field label="Host name"><Input value={host} onChange={(e) => setHost(e.target.value)} placeholder="www.example.com" autoComplete="off" spellCheck={false} inputMode="url" /></Field>
        <Button type="submit" busy={busy} disabled={!host.trim()}>Check certificate</Button>
      </form>
      {error && <div className="mt-5"><Alert>{error}</Alert></div>}
      {r && c && (
        <div className="mt-6 rounded-lg border border-line bg-surface">
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4">
            <StatusPill status={r.result.status} />
            <p className="font-display text-[17px] font-semibold text-heading">{r.hostname}{r.port !== 443 && `:${r.port}`}</p>
            <span className="ml-auto"><DaysLeft days={r.days_left} /></span>
          </div>
          <dl className="grid gap-x-6 gap-y-3 px-5 py-4 text-sm sm:grid-cols-[9rem_1fr]">
            {rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k}</dt><dd className="break-words text-ink">{v}</dd></div>)}
          </dl>
          {r.result.findings.length > 0 && <div className="border-t border-line px-5 py-4"><FindingList findings={r.result.findings} /></div>}
        </div>
      )}
    </div>
  );
}

const TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA"];

export function PropagationWidget({ onResult }: { onResult: (domain: string | null) => void }) {
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [type, setType] = useState("A");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<Propagation | null>(null);

  async function run(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setData(null); onResult(null);
    try {
      setData(await api<Propagation>("/tools/propagation/", { method: "POST", json: { name, type } }));
      onResult(name.trim().toLowerCase().split(".").slice(-2).join("."));
    } catch (err) { setError(friendlyError(err, !!user)); } finally { setBusy(false); }
  }
  return (
    <div>
      <form onSubmit={run} className="grid gap-3 sm:grid-cols-[1fr_9rem_auto] sm:items-end" noValidate>
        <Field label="Host name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="www.example.com" autoComplete="off" spellCheck={false} /></Field>
        <Field label="Record type"><Select value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t}>{t}</option>)}</Select></Field>
        <Button type="submit" busy={busy} disabled={!name.trim()}>Check</Button>
      </form>
      {error && <div className="mt-5"><Alert>{error}</Alert></div>}
      {data && <div className="mt-6"><PropagationResult data={data} /></div>}
    </div>
  );
}
