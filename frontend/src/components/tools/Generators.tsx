import { useMemo, useState } from "react";
import { Alert, CopyField, Field, Input, Select } from "../ui";

const SENDERS = [
  { id: "google", label: "Google Workspace", term: "include:_spf.google.com" },
  { id: "microsoft", label: "Microsoft 365", term: "include:spf.protection.outlook.com" },
  { id: "zoho", label: "Zoho Mail", term: "include:zohomail.com" },
  { id: "ses", label: "Amazon SES", term: "include:amazonses.com" },
  { id: "sendgrid", label: "SendGrid", term: "include:sendgrid.net" },
  { id: "mailgun", label: "Mailgun", term: "include:mailgun.org" },
  { id: "mailchimp", label: "Mailchimp / Mandrill", term: "include:servers.mcsv.net" },
  { id: "brevo", label: "Brevo", term: "include:spf.brevo.com" },
  { id: "zendesk", label: "Zendesk", term: "include:mail.zendesk.com" },
  { id: "freshdesk", label: "Freshdesk", term: "include:email.freshdesk.com" },
];

const check = "h-4 w-4 accent-[#14508f]";
const split = (s: string) => s.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean);

export function SpfGenerator() {
  const [picked, setPicked] = useState<string[]>(["google"]);
  const [mx, setMx] = useState(false);
  const [a, setA] = useState(false);
  const [ips, setIps] = useState("");
  const [includes, setIncludes] = useState("");
  const [all, setAll] = useState("~all");

  const { record, lookups, problems } = useMemo(() => {
    const terms: string[] = [];
    if (a) terms.push("a");
    if (mx) terms.push("mx");
    const validIp = (ip: string) => /^\d{1,3}(\.\d{1,3}){3}(\/\d{1,2})?$/.test(ip) || /^[0-9a-f]*:[0-9a-f:]+(\/\d{1,3})?$/i.test(ip);
    for (const ip of split(ips).filter(validIp)) terms.push(ip.includes(":") ? `ip6:${ip}` : `ip4:${ip}`);
    SENDERS.filter((s) => picked.includes(s.id)).forEach((s) => terms.push(s.term));
    for (const inc of split(includes)) terms.push(`include:${inc.replace(/^include:/, "")}`);
    const uniq = Array.from(new Set(terms));
    const lookups = uniq.filter((t) => t === "a" || t === "mx" || t.startsWith("include:")).length;
    const problems: string[] = [];
    if (lookups > 10) problems.push("More than 10 lookups: SPF will fail. Remove senders you no longer use or replace includes with ip4/ip6 ranges.");
    const bad = split(ips).filter((ip) => !validIp(ip));
    if (bad.length) problems.push(`Left out, not an IP address or range: ${bad.join(", ")}`);
    return { record: ["v=spf1", ...uniq, all].join(" "), lookups, problems };
  }, [picked, mx, a, ips, includes, all]);

  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  return (
    <div className="space-y-6">
      <fieldset>
        <legend className="mb-3 text-sm font-medium text-heading">Services that send mail for this domain</legend>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {SENDERS.map((s) => (
            <label key={s.id} className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" className={check} checked={picked.includes(s.id)} onChange={() => toggle(s.id)} />{s.label}
            </label>
          ))}
          <label className="flex items-center gap-2 text-sm text-ink"><input type="checkbox" className={check} checked={mx} onChange={(e) => setMx(e.target.checked)} />The domain's own mail servers (mx)</label>
          <label className="flex items-center gap-2 text-sm text-ink"><input type="checkbox" className={check} checked={a} onChange={(e) => setA(e.target.checked)} />The domain's web server (a)</label>
        </div>
      </fieldset>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Other includes" hint="Domains from your providers' setup guides, separated by spaces">
          <Input value={includes} onChange={(e) => setIncludes(e.target.value)} placeholder="spf.example-crm.com" spellCheck={false} />
        </Field>
        <Field label="IP addresses or ranges" hint="For your own servers, e.g. 203.0.113.10 or 198.51.100.0/24">
          <Input value={ips} onChange={(e) => setIps(e.target.value)} placeholder="203.0.113.10" spellCheck={false} />
        </Field>
      </div>
      <Field label="Mail from anywhere else">
        <Select value={all} onChange={(e) => setAll(e.target.value)}>
          <option value="~all">Soft fail (~all): recommended while you check every sender</option>
          <option value="-all">Fail (-all): strict, once every sender is listed</option>
        </Select>
      </Field>
      <div className="space-y-3 rounded-lg border border-line bg-subtle p-4">
        <CopyField label="TXT record for the domain itself (host @)" value={record} />
        <p className="text-sm text-muted">
          {lookups} of 10 DNS lookups used by the terms above. Providers' includes can add more lookups of their own; check the published record with the SPF checker.
        </p>
        {problems.map((p) => <Alert key={p} tone="warning">{p}</Alert>)}
        <p className="text-sm text-ink">Replace any existing <code className="font-mono text-[13px]">v=spf1</code> record; a domain may have only one.</p>
      </div>
    </div>
  );
}

export function DmarcGenerator() {
  const [p, setP] = useState("none");
  const [sp, setSp] = useState("");
  const [pct, setPct] = useState("100");
  const [rua, setRua] = useState("");
  const [adkim, setAdkim] = useState("r");
  const [aspf, setAspf] = useState("r");

  const { record, problems } = useMemo(() => {
    const addrs = split(rua).map((x) => x.replace(/^mailto:/i, ""));
    const problems: string[] = [];
    const bad = addrs.filter((x) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(x));
    if (bad.length) problems.push(`Not an email address: ${bad.join(", ")}`);
    if (!addrs.length) problems.push("Without a report address you won't learn who sends mail as your domain.");
    const n = Number(pct);
    if (!Number.isInteger(n) || n < 0 || n > 100) problems.push("Percentage must be a whole number from 0 to 100.");
    const tags = [`v=DMARC1`, `p=${p}`];
    if (sp) tags.push(`sp=${sp}`);
    if (pct !== "100" && Number.isInteger(n)) tags.push(`pct=${n}`);
    if (addrs.length) tags.push(`rua=${addrs.map((x) => `mailto:${x}`).join(",")}`);
    if (adkim === "s") tags.push("adkim=s");
    if (aspf === "s") tags.push("aspf=s");
    return { record: tags.join("; "), problems };
  }, [p, sp, pct, rua, adkim, aspf]);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Policy for failing mail">
          <Select value={p} onChange={(e) => setP(e.target.value)}>
            <option value="none">Monitor only (p=none): start here</option>
            <option value="quarantine">Send to spam (p=quarantine)</option>
            <option value="reject">Reject (p=reject): full protection</option>
          </Select>
        </Field>
        <Field label="Subdomains">
          <Select value={sp} onChange={(e) => setSp(e.target.value)}>
            <option value="">Same as the domain</option>
            <option value="none">Monitor only</option>
            <option value="quarantine">Send to spam</option>
            <option value="reject">Reject</option>
          </Select>
        </Field>
        <Field label="Report address(es)" hint="Where daily aggregate reports go; separate several with commas">
          <Input value={rua} onChange={(e) => setRua(e.target.value)} placeholder="dmarc-reports@example.com" spellCheck={false} />
        </Field>
        <Field label="Apply policy to this % of failing mail" hint="Use less than 100 only while moving to quarantine or reject">
          <Input value={pct} onChange={(e) => setPct(e.target.value)} inputMode="numeric" />
        </Field>
        <Field label="DKIM alignment">
          <Select value={adkim} onChange={(e) => setAdkim(e.target.value)}><option value="r">Relaxed (recommended)</option><option value="s">Strict</option></Select>
        </Field>
        <Field label="SPF alignment">
          <Select value={aspf} onChange={(e) => setAspf(e.target.value)}><option value="r">Relaxed (recommended)</option><option value="s">Strict</option></Select>
        </Field>
      </div>
      <div className="space-y-3 rounded-lg border border-line bg-subtle p-4">
        <CopyField label="TXT record at _dmarc (host _dmarc)" value={record} />
        {problems.map((x) => <Alert key={x} tone="warning">{x}</Alert>)}
        <p className="text-sm text-ink">
          Reports sent to a mailbox on another domain need that domain's permission. With a DomainVitals account,
          reports go to DomainVitals and are turned into a readable dashboard for you.
        </p>
      </div>
    </div>
  );
}
