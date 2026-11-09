import { FormEvent, useState } from "react";
import CheckCard from "../components/CheckCard";
import { PropagationResult, runToolPropagation } from "../components/DnsRecords";
import { Alert, Button, Card, Field, Input, PageHeader, ScoreRing, Select } from "../components/ui";
import { api, ApiError, CheckName, CheckResult, errorText, Propagation } from "../lib/api";

type Result = { domain: string; score?: number; results: Partial<Record<CheckName, CheckResult>> };
const ORDER: CheckName[] = ["dmarc", "spf", "dkim", "mx", "dns"];

export default function Checker() {
  const [domain, setDomain] = useState("");
  const [check, setCheck] = useState<"all" | CheckName>("all");
  const [selector, setSelector] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function run(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setResult(null);
    try { setResult(await api<Result>("/tools/check/", { method: "POST", json: { domain, check, selector } })); }
    catch (err) { setError((err as ApiError).details?.domain?.[0] ?? errorText(err)); }
    finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="Domain checker" description="Look up any domain's mail authentication right now. Nothing is saved and no verification is needed." />
      <Card>
        <form onSubmit={run} className="grid gap-4 md:grid-cols-[1fr_12rem_12rem_auto] md:items-end" noValidate>
          <Field label="Domain"><Input value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="example.com" autoComplete="off" spellCheck={false} /></Field>
          <Field label="Check">
            <Select value={check} onChange={(e) => setCheck(e.target.value as "all" | CheckName)}>
              <option value="all">Everything</option><option value="dmarc">DMARC</option><option value="spf">SPF</option>
              <option value="dkim">DKIM</option><option value="mx">MX</option><option value="dns">DNS health</option>
            </Select>
          </Field>
          <Field label="DKIM selector (optional)"><Input value={selector} onChange={(e) => setSelector(e.target.value)} placeholder="selector1" /></Field>
          <Button type="submit" busy={busy} disabled={!domain.trim()}>Check domain</Button>
        </form>
      </Card>
      {error && <div className="mt-6"><Alert>{error}</Alert></div>}
      {result && (
        <div className="mt-6 space-y-6">
          {result.score !== undefined && (
            <div className="flex items-center gap-5 rounded-lg border border-line bg-surface px-6 py-5">
              <ScoreRing score={result.score} size={80} />
              <div><p className="font-display text-[17px] font-semibold text-heading">{result.domain}</p>
                <p className="text-sm text-muted">Checked just now from public DNS.</p></div>
            </div>
          )}
          <div className="grid gap-6 xl:grid-cols-2">
            {ORDER.filter((c) => result.results[c]).map((c) => <CheckCard key={c} name={c} result={result.results[c]} />)}
          </div>
        </div>
      )}
      <PropagationTool />
    </>
  );
}

const TYPES = ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA", "CAA"];

function PropagationTool() {
  const [name, setName] = useState("");
  const [type, setType] = useState("A");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<Propagation | null>(null);

  async function run(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setData(null);
    try { setData(await runToolPropagation(name, type)); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <div className="mt-8">
      <Card title="DNS propagation" description="Compare a record on the domain's own name servers with what Cloudflare, Google, Quad9 and OpenDNS return. Useful right after you change DNS.">
        <form onSubmit={run} className="grid gap-4 md:grid-cols-[1fr_10rem_auto] md:items-end" noValidate>
          <Field label="Host name"><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="www.example.com" autoComplete="off" spellCheck={false} /></Field>
          <Field label="Record type">
            <Select value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
          </Field>
          <Button type="submit" variant="secondary" busy={busy} disabled={!name.trim()}>Check propagation</Button>
        </form>
        {error && <div className="mt-4"><Alert>{error}</Alert></div>}
        {data && <div className="mt-5"><PropagationResult data={data} /></div>}
      </Card>
    </div>
  );
}
