// Legal documents shown at /legal/<slug> and prerendered for crawlers.
// No imports: scripts/prerender-tools.mjs loads this file directly.
// When a document changes materially, bump LEGAL_VERSION here and in the
// backend setting LEGAL_TERMS_VERSION so new sign-ups record the new version.

export const LEGAL_VERSION = "2026-11-17";
export const LEGAL_UPDATED = "17 November 2026";

/** A block is a paragraph, a bulleted list or a table (first row is the header). */
export type Block = string | { ul: string[] } | { table: string[][] };
export type Section = { h: string; body: Block[] };
export type LegalDoc = { slug: string; name: string; title: string; description: string; intro: string[]; sections: Section[] };

const COMPANY = "MSPoint LLC";

export const SUBPROCESSORS: string[][] = [
  ["Subprocessor", "Purpose", "Data", "Location"],
  ["Cloudflare, Inc.", "Network edge, DDoS protection and the encrypted tunnel that carries all traffic to our servers", "All traffic to and from the service, including IP addresses", "Global edge network; United States"],
  ["Zoho Corporation", "Sending account and alert mail; receiving DMARC aggregate reports", "Names and email addresses of recipients, mail content, DMARC reports", "United States"],
  ["Stripe, Inc.", "Subscription payments, invoices and tax", "Billing contact, payment details (entered directly with Stripe), invoices", "United States"],
];

export const LEGAL: LegalDoc[] = [
  {
    slug: "terms",
    name: "Terms of Service",
    title: "Terms of Service | DomainVitals",
    description: "The terms that apply to DomainVitals accounts, subscriptions and the free tools, provided by MSPoint LLC.",
    intro: [
      `These Terms of Service ("Terms") are an agreement between ${COMPANY}, a Wyoming limited liability company ("MSPoint", "we", "us"), and you, or the organisation you act for ("Customer", "you"). They apply to DomainVitals at app.mspointit.com, its API, and the free public tools (together, the "Service").`,
      "By creating an account, or by using the Service, you accept these Terms. If you accept them for an organisation, you confirm that you may bind it. Our Privacy Policy and Data Processing Addendum form part of these Terms.",
    ],
    sections: [
      { h: "1. Accounts", body: [
        "You must give accurate information, keep your password secret and confirm your email address before you sign in. You are responsible for everything done through your account and your workspaces.",
        "You must be at least 18 years old and use the Service for business or professional purposes.",
        "Tell us at once at security@mspointit.com if you think someone has used your account without permission.",
      ] },
      { h: "2. Workspaces and team members", body: [
        "A workspace belongs to the Customer that created it. Owners decide who is invited, and with what role. You are responsible for the people you invite and for removing access when they leave.",
      ] },
      { h: "3. Acceptable use", body: [
        "You may add only domains that you own or manage, or that you are authorised to monitor. Domains must be verified with a DNS record before they are monitored.",
        "You must not:",
        { ul: [
          "use the Service, or the free tools, to scan, probe or overload systems you are not authorised to test;",
          "get round rate limits, plan limits or access controls, or scrape the Service automatically except through the documented API;",
          "try to reach another customer's data, or test the security of the Service without our written permission (report vulnerabilities to security@mspointit.com instead);",
          "upload malware, or use the Service to send spam or for anything unlawful;",
          "resell or provide the Service to others, except that agencies and MSPs may use it to look after their own clients' domains and share reports with those clients.",
        ] },
        "We may suspend access that breaks this section or puts the Service or other customers at risk. Where we reasonably can, we will tell you first.",
      ] },
      { h: "4. Plans, trials and payment", body: [
        "Plans, prices and limits are shown on the Billing page and may differ by plan. New workspaces get a free trial of a paid plan. When it ends, the workspace moves to the Free plan unless you subscribe; no card is needed for the trial.",
        "Paid plans are billed in advance, monthly or yearly, through Stripe, and renew automatically until cancelled. Prices exclude taxes unless stated; you pay any taxes that apply.",
        "You can cancel at any time in the billing portal. Cancellation takes effect at the end of the current billing period, and you keep the paid features until then. Fees already paid are not refundable, except where the law requires it.",
        "If a payment fails we will try again and tell you. If it is still unpaid after 14 days we may move the workspace to the Free plan; your data is kept, but only the domains the Free plan allows are monitored.",
        "We may change prices with at least 30 days' notice. The change applies from your next renewal after the notice period.",
      ] },
      { h: "5. Free public tools", body: [
        "The free tools are provided as they are, without an account, subject to rate limits. Results reflect what public DNS and the checked servers returned at that moment.",
      ] },
      { h: "6. Your data", body: [
        "You keep all rights in the data you put into the Service, such as domain names, DNS and certificate results, DMARC reports, alert settings and logos (\"Customer Data\"). You give us the rights we need to host, process and show it in order to provide the Service.",
        "We process personal data in Customer Data as your processor, under the Data Processing Addendum.",
        "You can export reports and remove domains at any time. After your account or workspace is closed, we delete Customer Data as described in the Privacy Policy.",
      ] },
      { h: "7. Our service and intellectual property", body: [
        "MSPoint owns the Service, including its software, design and documentation. These Terms give you a limited, non-exclusive, non-transferable right to use it during your subscription. If you send us feedback, we may use it without obligation to you.",
        "We may improve and change the Service. We will not remove a core feature of a paid plan during a paid period without giving you notice and the option to cancel with a pro rata refund.",
      ] },
      { h: "8. Availability and support", body: [
        "We aim to keep the Service available at all times and to fix problems quickly, but unless you have a separate written agreement there is no guaranteed uptime. Planned maintenance is kept short and, where possible, announced in advance. Support is by email at support@mspointit.com.",
        "Monitoring helps you find problems; it does not guarantee that every problem will be detected, or that alerts will arrive. You remain responsible for your own domains, DNS and mail systems.",
      ] },
      { h: "9. Third-party services", body: [
        "The Service works with services you choose, such as Slack, Microsoft Teams, webhooks and your DNS and mail providers. Their own terms apply to them, and we are not responsible for them.",
      ] },
      { h: "10. Confidentiality", body: [
        "Each party will keep the other's non-public information confidential, use it only for this agreement, and protect it with at least reasonable care. This does not cover information that is public, already known, independently developed, or that must be disclosed by law (with notice where allowed).",
      ] },
      { h: "11. Disclaimer", body: [
        "Except as these Terms expressly say, the Service is provided \"as is\" and \"as available\". To the extent the law allows, MSPoint disclaims all other warranties, including merchantability, fitness for a particular purpose and non-infringement.",
      ] },
      { h: "12. Limitation of liability", body: [
        "To the extent the law allows, neither party is liable for indirect, incidental, special, consequential or punitive damages, or for lost profits, revenue, goodwill or data, even if told they were possible.",
        "Each party's total liability arising out of or relating to these Terms is limited to the fees you paid to MSPoint for the Service in the 12 months before the event that gave rise to the claim, or USD 100 if you have paid nothing.",
        "These limits do not apply to your payment obligations, to breaches of section 3, or to liability that cannot be limited by law.",
      ] },
      { h: "13. Indemnity", body: [
        "You will defend and indemnify MSPoint against third-party claims arising from Customer Data or from your use of the Service in breach of these Terms, including monitoring domains you were not authorised to monitor.",
      ] },
      { h: "14. Term and termination", body: [
        "These Terms apply while you have an account. You may close your account at any time by writing to support@mspointit.com. We may end them with 30 days' notice, or at once if you materially breach them and do not fix the breach within 10 days of notice (or at once for serious breaches of section 3).",
        "Sections 6, 7, 10 to 13 and 16 survive termination.",
      ] },
      { h: "15. Changes to these Terms", body: [
        "We may update these Terms. For material changes we will give at least 30 days' notice by email or in the app. If you keep using the Service after the changes take effect, the new Terms apply; if you do not agree, you can cancel before then.",
      ] },
      { h: "16. General", body: [
        "These Terms are governed by the laws of the State of Wyoming, USA, without regard to its conflict-of-law rules. The state and federal courts located in Wyoming have exclusive jurisdiction, except that either party may seek urgent relief in any competent court. Mandatory consumer or data protection laws that apply to you are not affected.",
        "You may not assign these Terms without our consent; we may assign them to a successor of our business. Neither party is liable for delays caused by events beyond its reasonable control. If any part is unenforceable, the rest stays in effect. These Terms, with the documents they refer to and any signed order form, are the entire agreement on this subject.",
        "Notices to us: support@mspointit.com. Notices to you: the email address of the workspace owner.",
      ] },
    ],
  },
  {
    slug: "privacy",
    name: "Privacy Policy",
    title: "Privacy Policy | DomainVitals",
    description: "What personal data DomainVitals collects, why, who it is shared with, how long it is kept and your rights.",
    intro: [
      `This policy explains how ${COMPANY} ("MSPoint", "we") handles personal data in DomainVitals: the website at app.mspointit.com, the app, its API and the free tools.`,
      "For data about our own customers and website visitors, MSPoint is the controller. For personal data that customers put into their workspaces, such as DMARC reports or the contact details of their own clients, the customer is the controller and we act as its processor under our Data Processing Addendum.",
    ],
    sections: [
      { h: "1. Data we collect", body: [
        { table: [
          ["Data", "Examples", "Source"],
          ["Account", "Name, work email address, password (stored only as a salted hash), email confirmation status", "You"],
          ["Workspace", "Workspace name, members and their roles, invitations, branding and logo, report schedule and recipients", "You and your team"],
          ["Monitoring data", "Domain names, DNS records, certificate details, scan results and history, alerts", "Public DNS and servers that we check for you"],
          ["DMARC reports", "Aggregate reports from mailbox providers: sending IP addresses, sender host names, message counts and authentication results", "Mailbox providers, sent to the report address you publish"],
          ["Alert destinations", "Email addresses, Slack and Teams webhook URLs, your own webhook URLs", "You"],
          ["Billing", "Billing contact, plan, invoices and payment status. Card details are entered directly with Stripe and never reach us.", "You and Stripe"],
          ["Technical and security", "IP address, browser user agent, request IDs, sign-in attempts, audit log of changes in a workspace", "Your device"],
          ["Free tools", "The domain or host you check, and your IP address for rate limiting", "You"],
          ["Support", "What you write to us", "You"],
        ] },
      ] },
      { h: "2. Why we use it, and the legal basis", body: [
        { ul: [
          "To provide the Service: create accounts, run checks, show results, send alerts and reports (contract).",
          "To send service mail: confirmation links, password resets, security notices, billing notices (contract; legitimate interests).",
          "To keep the Service secure: rate limits, account lockout, fraud and abuse prevention, audit logs (legitimate interests; legal obligation).",
          "To bill and keep accounting records (contract; legal obligation).",
          "To improve the Service from aggregated, non-identifying usage information (legitimate interests).",
          "Product news or marketing mail only with your consent, which you can withdraw at any time.",
        ] },
        "We do not sell personal data, use it for advertising, or use Customer Data to train AI models.",
      ] },
      { h: "3. Cookies and local storage", body: [
        "We use only what the Service needs: a session cookie that keeps you signed in, and a CSRF cookie that protects forms. Your colour theme choice is stored in your browser. We use no advertising or analytics cookies, so we do not show a cookie banner.",
      ] },
      { h: "4. Who we share data with", body: [
        "We share personal data only with the service providers below, who process it for us under contract, and when the law requires it. The current list of subprocessors is also at /legal/subprocessors.",
        { table: SUBPROCESSORS },
        "Checks send DNS queries to public resolvers (Cloudflare, Google and Quad9) and connect to the servers you monitor; these queries contain domain names, not account data. Alerts go to the destinations you configure, such as Slack or Microsoft Teams, under those providers' own terms.",
        "If MSPoint is involved in a merger, acquisition or sale of assets, data may transfer to the new owner under this policy.",
      ] },
      { h: "5. International transfers", body: [
        "MSPoint is a US company. The DomainVitals application servers and database are located in the United States, and our subprocessors process data in the United States and other countries. Where data protection law requires it, transfers from the EEA, UK or Switzerland rely on the European Commission's Standard Contractual Clauses (and the UK Addendum), or another valid transfer mechanism.",
      ] },
      { h: "6. How long we keep data", body: [
        { ul: [
          "Account and workspace data: while the account is open. After an account or workspace is closed, we delete it within 30 days.",
          "DMARC reports: for the history your plan includes, and no more than 400 days.",
          "Scan results and alerts: while the domain is in the workspace; deleted with the domain.",
          "Security logs: up to 12 months.",
          "Billing records: as long as tax and accounting law requires (usually up to 7 years).",
          "Database backups: up to 12 months, then overwritten. Deleted data in backups is not used, and is not restored except to recover from a disaster.",
        ] },
      ] },
      { h: "7. Security", body: [
        "All traffic is encrypted in transit; servers accept no direct connections from the internet. Passwords are hashed, access is restricted by role, each workspace's data is isolated, and payment data stays with Stripe. More detail is in Annex II of the Data Processing Addendum. Report security issues to security@mspointit.com.",
      ] },
      { h: "8. Your rights", body: [
        "Depending on where you live (for example under the GDPR, the UK GDPR or US state laws such as the CCPA), you may have the right to access, correct, delete or export your personal data, to object to or restrict processing, and to withdraw consent. You can change your account details in the app, or write to privacy@mspointit.com. We will reply within 30 days and will not discriminate against you for exercising your rights. You can also complain to your local data protection authority.",
        "If your data is in a customer's workspace (for example in a DMARC report), please contact that customer; we will help them respond.",
      ] },
      { h: "9. Children", body: [
        "The Service is for businesses and is not directed at anyone under 18. We do not knowingly collect their data.",
      ] },
      { h: "10. Changes", body: [
        "We will post changes here and update the date above. If the changes are material, we will notify account owners by email before they take effect.",
      ] },
      { h: "11. Contact", body: [
        `${COMPANY}, Wyoming, USA. Privacy questions: privacy@mspointit.com. Everything else: support@mspointit.com.`,
      ] },
    ],
  },
  {
    slug: "dpa",
    name: "Data Processing Addendum",
    title: "Data Processing Addendum (DPA) | DomainVitals",
    description: "The DomainVitals Data Processing Addendum: GDPR Article 28 terms, Standard Contractual Clauses, subprocessors and security measures.",
    intro: [
      `This Data Processing Addendum ("DPA") forms part of the Terms of Service between ${COMPANY} ("Processor") and the Customer ("Controller"). It applies when MSPoint processes personal data on the Customer's behalf in providing DomainVitals, and is accepted together with the Terms. Customers who need a countersigned copy can request one at privacy@mspointit.com.`,
    ],
    sections: [
      { h: "1. Definitions", body: [
        "\"Data Protection Laws\" means all laws on personal data that apply to the processing, including the EU GDPR, the UK GDPR, the Swiss FADP and US state privacy laws. \"Personal data\", \"processing\", \"controller\", \"processor\", \"data subject\" and \"supervisory authority\" have the meanings given in the GDPR. \"Customer Personal Data\" is personal data in Customer Data that MSPoint processes for the Customer.",
      ] },
      { h: "2. Roles and instructions", body: [
        "The Customer is the controller (or a processor acting for its own clients) and MSPoint is the processor (or subprocessor). MSPoint processes Customer Personal Data only on the Customer's documented instructions: the Terms, this DPA, and the Customer's use and configuration of the Service. MSPoint will tell the Customer if it believes an instruction breaks Data Protection Laws.",
        "The Customer is responsible for having a lawful basis for the processing and for the accuracy of Customer Personal Data. For the CCPA, MSPoint is a service provider and will not sell or share Customer Personal Data, or use it outside the direct business relationship with the Customer.",
      ] },
      { h: "3. Confidentiality and security", body: [
        "MSPoint ensures that everyone authorised to process Customer Personal Data is bound by confidentiality, and implements the technical and organisational measures in Annex II. MSPoint may update these measures as long as overall protection is not reduced.",
      ] },
      { h: "4. Subprocessors", body: [
        "The Customer gives general authorisation for MSPoint to use subprocessors. The current list is in Annex III and at /legal/subprocessors. MSPoint will give at least 30 days' notice of a new subprocessor by updating that page and emailing workspace owners. The Customer may object on reasonable data protection grounds within that period; if the parties cannot resolve the objection, the Customer may terminate the affected Service and receive a pro rata refund of prepaid fees.",
        "MSPoint imposes data protection obligations on each subprocessor that are no less protective than this DPA, and remains liable for their performance.",
      ] },
      { h: "5. Data subject requests and assistance", body: [
        "MSPoint will pass on to the Customer any request from a data subject about Customer Personal Data, without responding itself unless instructed to, and will help the Customer respond, taking into account the nature of the processing. MSPoint will also give reasonable help with data protection impact assessments and consultations with supervisory authorities.",
      ] },
      { h: "6. Personal data breaches", body: [
        "MSPoint will notify the Customer without undue delay, and in any case within 72 hours of becoming aware of a personal data breach affecting Customer Personal Data. The notice will describe the breach, the data and data subjects affected, likely consequences, and the measures taken or proposed, with further information as it becomes available.",
      ] },
      { h: "7. Deletion and return", body: [
        "During the subscription the Customer can export reports and remove domains and data. Within 30 days after the account or workspace is closed, MSPoint deletes Customer Personal Data, unless the law requires it to be kept. Backups are overwritten within 12 months and are not restored except for disaster recovery.",
      ] },
      { h: "8. Audits", body: [
        "MSPoint will make available the information reasonably needed to show compliance with this DPA, including answers to security questionnaires, once a year or after a personal data breach. Where that is not enough, the Customer may carry out an audit, at its own cost, with 30 days' notice, during business hours, under confidentiality, and without access to other customers' data.",
      ] },
      { h: "9. International transfers", body: [
        "Where Customer Personal Data is transferred from the EEA, the UK or Switzerland to a country without an adequacy decision, the parties incorporate the Standard Contractual Clauses adopted by Commission Implementing Decision (EU) 2021/914: Module Two (controller to processor) or Module Three (processor to processor), as applicable. In the Clauses: clause 7 (docking) applies; clause 9 option 2 (general authorisation, 30 days' notice) applies; the optional wording in clause 11 does not apply; clauses 17 and 18 are governed by the law of, and disputes heard in, Ireland. The annexes are Annexes I to III of this DPA.",
        "For the UK, the International Data Transfer Addendum issued by the ICO applies, with the information above. For Switzerland, references to the GDPR mean the FADP and the competent authority is the FDPIC.",
      ] },
      { h: "10. Liability and precedence", body: [
        "Each party's liability under this DPA is subject to the limits in the Terms, except where Data Protection Laws or the Standard Contractual Clauses do not allow it. If this DPA conflicts with the Terms, this DPA prevails; if it conflicts with the Standard Contractual Clauses, the Clauses prevail.",
      ] },
      { h: "Annex I: Details of processing", body: [
        { table: [
          ["Item", "Details"],
          ["Parties", "Data exporter: the Customer (controller). Data importer: MSPoint LLC, Wyoming, USA (processor); contact privacy@mspointit.com."],
          ["Subject matter and purpose", "Monitoring the Customer's domains (DNS, mail authentication, certificates), processing DMARC aggregate reports, sending alerts and reports, and managing the Customer's workspace."],
          ["Duration", "The term of the Terms, plus the deletion period in section 7."],
          ["Location", "Application servers and database in the United States; subprocessors as listed in Annex III."],
          ["Data subjects", "The Customer's team members and invitees; recipients of alerts and reports; the Customer's clients' contacts; people whose details appear in DMARC reports or monitored DNS records."],
          ["Personal data", "Names, email addresses, IP addresses and host names of sending mail servers, webhook URLs, data in DNS records and certificates, audit log entries."],
          ["Sensitive data", "None intended. The Customer must not put special categories of data into the Service."],
          ["Frequency", "Continuous."],
          ["Retention", "As set out in the Privacy Policy, section 6."],
        ] },
      ] },
      { h: "Annex II: Technical and organisational measures", body: [
        { ul: [
          "Encryption in transit: TLS for all connections, HSTS, an authenticated encrypted tunnel to our servers, no inbound ports open to the internet.",
          "Access control: confirmed email addresses, salted password hashes, rate limits and per-account lockout, role-based access within workspaces, and staff access restricted to those who need it.",
          "Isolation: every request is checked against the workspace membership of the signed-in user, backed by automated tests covering every route.",
          "Application security: CSRF protection, a strict Content Security Policy, safe parsing of uploaded reports and images, outbound requests limited to public addresses, signed webhooks.",
          "Vulnerability management: dependency audits on every change and weekly; prompt patching of security fixes; code review before release.",
          "Availability: health monitoring with alerting, automatic rollback of failed releases, nightly database backups with retention, and weekly restore tests.",
          "Logging: security events and workspace audit logs.",
          "Payments: card data is handled only by Stripe (PCI DSS Level 1).",
          "Incident response: a documented process, including customer notification within 72 hours.",
        ] },
      ] },
      { h: "Annex III: Subprocessors", body: [
        { table: SUBPROCESSORS },
      ] },
    ],
  },
  {
    slug: "subprocessors",
    name: "Subprocessors",
    title: "Subprocessors | DomainVitals",
    description: "Third parties that process personal data for DomainVitals, what for, and where.",
    intro: [
      `${COMPANY} uses the following subprocessors to provide DomainVitals. We give at least 30 days' notice of a new subprocessor here and by email to workspace owners, as set out in the Data Processing Addendum.`,
    ],
    sections: [{ h: "Current subprocessors", body: [{ table: SUBPROCESSORS }] }],
  },
];

export const legalDoc = (slug?: string) => LEGAL.find((d) => d.slug === slug);
