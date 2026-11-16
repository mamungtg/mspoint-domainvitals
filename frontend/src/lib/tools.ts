// Catalogue of the free public tools. The same data drives the pages and the
// prerendered SEO HTML (scripts/prerender-tools.mjs), so keep it plain data.

export type ToolKind =
  | { type: "check"; check: "spf" | "dmarc" | "dkim" | "mx" | "dns" | "all" }
  | { type: "ssl" }
  | { type: "propagation" }
  | { type: "spf-generator" }
  | { type: "dmarc-generator" };

export type Tool = {
  slug: string;
  name: string;
  title: string; // <title>, under ~60 characters
  description: string; // meta description, under ~155 characters
  h1: string;
  lead: string;
  kind: ToolKind;
  about: string[]; // what it checks / why it matters (rendered as paragraphs)
  faq: { q: string; a: string }[];
};

export const TOOLS: Tool[] = [
  {
    slug: "domain-health-check",
    name: "Domain health check",
    title: "Free Domain Health Check: SPF, DKIM, DMARC, MX, DNS",
    description: "Check SPF, DKIM, DMARC, MX and DNS for any domain in one go. Free, no sign-up, with the exact record to fix.",
    h1: "Domain health check",
    lead: "One scan of everything that decides whether mail from a domain is delivered and trusted: SPF, DKIM, DMARC, MX and the DNS setup behind them.",
    kind: { type: "check", check: "all" },
    about: [
      "The check reads the domain's public DNS the same way receiving mail servers do. Each part gets a pass, warning or failure, and every finding explains what is wrong and which record to change.",
      "The score starts at 100. Each critical problem costs 25 points and each warning 10, so you can see at a glance which domains need work first.",
    ],
    faq: [
      { q: "Is anything stored?", a: "No. Free checks are run live and the result is shown once. Nothing about the domain is saved unless you add it to a DomainVitals workspace." },
      { q: "Why do results differ from other tools?", a: "Some tools stop at syntax. DomainVitals also counts SPF DNS lookups through every include, looks for DKIM keys under common selectors, and checks that name servers answer for the zone." },
      { q: "How do I keep an eye on it?", a: "Add the domain to DomainVitals. It is scanned every day and you are alerted when something breaks or a record changes." },
    ],
  },
  {
    slug: "spf-checker",
    name: "SPF checker",
    title: "SPF Record Checker: Validate SPF and Count DNS Lookups",
    description: "Validate a domain's SPF record, count DNS lookups against the limit of 10, and find duplicate or broken records. Free, no sign-up.",
    h1: "SPF record checker",
    lead: "Check that a domain has exactly one valid SPF record, see every include it pulls in, and count the DNS lookups against the limit of 10.",
    kind: { type: "check", check: "spf" },
    about: [
      "SPF lists the servers allowed to send mail for a domain. Receivers reject or flag mail when the record is missing, when there is more than one, when the syntax is wrong, or when evaluating it needs more than 10 DNS lookups.",
      "The checker follows every include and redirect, counts lookups the way RFC 7208 does, and warns about +all, ?all, a missing all mechanism, invalid ip4/ip6 ranges and repeated terms.",
    ],
    faq: [
      { q: "What is the 10-lookup limit?", a: "Evaluating SPF may trigger at most 10 DNS lookups (include, a, mx, ptr, exists, redirect). Above that the result is a permanent error and many receivers treat the mail as unauthenticated." },
      { q: "Should I end with -all or ~all?", a: "Use ~all while you are still finding every sender, then move to -all. With DMARC in place, ~all is also acceptable because DMARC decides what happens to failing mail." },
      { q: "Can I have two SPF records?", a: "No. Two v=spf1 records make SPF fail for every message. Merge them into one record." },
    ],
  },
  {
    slug: "dmarc-checker",
    name: "DMARC checker",
    title: "DMARC Record Checker: Validate Policy and Reporting",
    description: "Check a domain's DMARC record, policy, pct, subdomain policy and report addresses. See how far it is from p=reject. Free, no sign-up.",
    h1: "DMARC record checker",
    lead: "See whether a domain publishes DMARC, which policy it enforces, where reports go, and what stands between it and p=reject.",
    kind: { type: "check", check: "dmarc" },
    about: [
      "DMARC tells receivers what to do with mail that fails SPF and DKIM alignment: nothing (p=none), spam folder (p=quarantine) or reject (p=reject). It is also how you get reports about who is sending as your domain.",
      "Google, Yahoo and Microsoft require DMARC for bulk senders. The checker reads the record at _dmarc.<domain>, validates every tag, and flags weak settings such as p=none, a partial pct or a missing rua address.",
    ],
    faq: [
      { q: "Is p=none enough?", a: "It is the right place to start, because you get reports without affecting delivery. It does not protect the domain from spoofing; plan to move to quarantine and then reject." },
      { q: "What is rua?", a: "The address that receives daily aggregate reports. Without it you cannot see which services send as your domain or whether they pass." },
      { q: "Do subdomains need their own record?", a: "Subdomains follow the parent's policy unless sp= sets another one. A record on a subdomain overrides it for that subdomain." },
    ],
  },
  {
    slug: "dkim-checker",
    name: "DKIM checker",
    title: "DKIM Record Checker: Find Keys and Check Key Length",
    description: "Look up DKIM keys for a domain under common selectors or your own, and check the key type and length. Free, no sign-up.",
    h1: "DKIM record checker",
    lead: "Find the DKIM public keys a domain publishes, under common selectors or one you enter, and check that they are valid and long enough.",
    kind: { type: "check", check: "dkim" },
    about: [
      "DKIM signs each message with a private key; receivers fetch the public key from <selector>._domainkey.<domain> to verify the signature. Each sending service uses its own selector.",
      "Without a selector the checker tries the ones used by Google Workspace, Microsoft 365, Zoho, SendGrid, Mailchimp and other common services. Keys shorter than 2048 bits are flagged.",
    ],
    faq: [
      { q: "What is a selector?", a: "A name that points to one key, for example google or selector1. The selector is in the s= tag of the DKIM-Signature header of a message you sent." },
      { q: "Why is no key found?", a: "Either the service uses a selector the checker doesn't try (enter it above) or DKIM signing has not been turned on for the domain in that service." },
      { q: "Is a 1024-bit key a problem?", a: "It still works, but 2048 bits is the current recommendation. Most providers let you rotate to a 2048-bit key in a few clicks." },
    ],
  },
  {
    slug: "mx-lookup",
    name: "MX lookup",
    title: "MX Record Lookup: Check a Domain's Mail Servers",
    description: "Look up a domain's MX records, priorities and whether each mail server resolves. Detects null MX. Free, no sign-up.",
    h1: "MX record lookup",
    lead: "List the mail servers that receive mail for a domain, in priority order, and check that each one resolves to an address.",
    kind: { type: "check", check: "mx" },
    about: [
      "MX records tell other servers where to deliver mail for a domain. A missing MX, or one pointing at a name that does not resolve, means mail bounces or is delayed.",
      "Domains that never receive mail can publish a null MX (priority 0, host '.') so senders know not to try. The lookup recognises it.",
    ],
    faq: [
      { q: "What do the numbers mean?", a: "The priority: lower is tried first. Servers with the same priority share the load." },
      { q: "Can an MX point to an IP address?", a: "No. An MX must point to a host name that has A or AAAA records, never to an IP address or a CNAME." },
    ],
  },
  {
    slug: "dns-health-check",
    name: "DNS health check",
    title: "DNS Health Check: Name Servers, SOA, CNAME and TTLs",
    description: "Check a domain's name servers, SOA, zone serials, dangling CNAMEs and TTLs. Find lame delegation and takeover risks. Free.",
    h1: "DNS health check",
    lead: "Check the DNS behind a domain: whether every name server answers, serials match, the SOA is sane and no CNAME points at something that no longer exists.",
    kind: { type: "check", check: "dns" },
    about: [
      "If one of a domain's name servers stops answering, or serves an old copy of the zone, some visitors and mail servers get wrong or no answers. The check asks each name server directly and compares serial numbers.",
      "It also flags a CNAME at the zone apex, CNAMEs that point to deleted names (a subdomain takeover risk), a single name server, and TTLs that are unusually short or long.",
    ],
    faq: [
      { q: "What is a lame name server?", a: "A server listed in the NS records that does not answer authoritatively for the domain. Queries sent to it fail or time out." },
      { q: "Why does a dangling CNAME matter?", a: "If www points to a cloud service name you no longer own, someone else can claim that name and serve content on your subdomain." },
    ],
  },
  {
    slug: "ssl-checker",
    name: "SSL checker",
    title: "SSL Certificate Checker: Expiry, Chain and Hostname",
    description: "Check a website's SSL/TLS certificate: days until expiry, trusted chain, hostname match, protocol, key size and HSTS. Free.",
    h1: "SSL certificate checker",
    lead: "Check the certificate a site presents: when it expires, whether browsers trust it, whether it covers the host name, and how the connection is protected.",
    kind: { type: "ssl" },
    about: [
      "An expired, untrusted or mismatched certificate shows visitors a full-page security warning. The checker connects the way a browser does, validates the chain against public trust stores, and reads the certificate even when it is invalid so you can see why.",
      "It also reports the TLS version, signature algorithm, key size and HSTS header, and warns when expiry is less than 30 days away.",
    ],
    faq: [
      { q: "Which hosts can be checked?", a: "Any public host name on port 443 or 8443. Names that resolve to private or internal addresses are not contacted." },
      { q: "My certificate renews automatically. Why monitor it?", a: "Automatic renewal fails quietly more often than you would expect: an expired API token, a changed DNS record, a full disk. Monitoring tells you weeks before visitors notice." },
    ],
  },
  {
    slug: "dns-propagation",
    name: "DNS propagation checker",
    title: "DNS Propagation Checker: Compare Name Servers and Resolvers",
    description: "Check whether a DNS change has propagated: compare the authoritative answer with Cloudflare, Google, Quad9 and OpenDNS. Free.",
    h1: "DNS propagation checker",
    lead: "After changing a record, see what the domain's own name servers answer and what Cloudflare, Google, Quad9 and OpenDNS still have cached.",
    kind: { type: "propagation" },
    about: [
      "DNS changes are not instant: resolvers keep an answer until its TTL runs out. The checker asks the authoritative name servers for the current value and compares it with four of the largest public resolvers.",
      "Supported types: A, AAAA, CNAME, MX, NS, TXT, SOA and CAA.",
    ],
    faq: [
      { q: "How long does propagation take?", a: "Up to the old record's TTL, measured from when each resolver last fetched it. With a TTL of one hour, most resolvers update within an hour." },
      { q: "Why does one resolver still show the old value?", a: "It cached the old answer recently. Wait for the TTL to pass; there is nothing to fix on your side." },
    ],
  },
  {
    slug: "spf-generator",
    name: "SPF generator",
    title: "SPF Record Generator: Build a Valid SPF Record",
    description: "Build a valid SPF record for Google Workspace, Microsoft 365, Zoho and other senders, within the 10-lookup limit. Free.",
    h1: "SPF record generator",
    lead: "Pick the services that send mail for your domain and get one valid SPF record to publish, with the lookup count shown as you go.",
    kind: { type: "spf-generator" },
    about: [
      "Publish the result as a TXT record on the domain itself (host @). Replace any existing v=spf1 record instead of adding a second one.",
      "Each include counts towards the limit of 10 DNS lookups. Senders with fixed addresses can be listed as ip4 or ip6 ranges, which cost no lookups.",
    ],
    faq: [
      { q: "Where do I find my services' include?", a: "Each provider documents it in its domain authentication guide. The common ones are built into the generator." },
      { q: "Do I still need DKIM?", a: "Yes. SPF breaks when mail is forwarded; DKIM survives forwarding. DMARC passes when either one passes and is aligned." },
    ],
  },
  {
    slug: "dmarc-generator",
    name: "DMARC generator",
    title: "DMARC Record Generator: Create a DMARC Policy",
    description: "Create a DMARC record step by step: policy, subdomain policy, percentage, alignment and report addresses. Free, no sign-up.",
    h1: "DMARC record generator",
    lead: "Choose a policy and where reports should go, and get a DMARC record ready to publish at _dmarc.<your domain>.",
    kind: { type: "dmarc-generator" },
    about: [
      "Start with p=none and a report address to see who sends as your domain. Once every legitimate service passes, move to p=quarantine and then p=reject.",
      "Publish the result as a TXT record with the host _dmarc. Only one DMARC record may exist per domain.",
    ],
    faq: [
      { q: "What do I do with the reports?", a: "They are XML files that arrive daily. DomainVitals reads them for you and shows each sending service, how much mail it sends and whether it passes." },
      { q: "Strict or relaxed alignment?", a: "Relaxed (the default) lets mail from a subdomain align with the parent domain. Use strict only when you know every sender uses the exact domain." },
    ],
  },
];

export const toolBySlug = (slug: string) => TOOLS.find((t) => t.slug === slug);
