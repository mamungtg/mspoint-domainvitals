// After `vite build`: write a real HTML file for each public tool page so search
// engines see the title, description and content without running JavaScript.
// React replaces the static markup inside #root when the app starts.
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { transform } from "esbuild";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const SITE = (process.env.SITE_URL || "https://app.mspointit.com").replace(/\/$/, "");

// Load the catalogue straight from the TypeScript source (it has no imports).
const ts = readFileSync(join(root, "src/lib/tools.ts"), "utf8");
const { code } = await transform(ts, { loader: "ts", format: "esm" });
const tmp = join(dist, ".tools.mjs");
writeFileSync(tmp, code);
const { TOOLS } = await import(pathToFileURL(tmp).href);
rmSync(tmp);

const shell = readFileSync(join(dist, "index.html"), "utf8");
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function page({ path, title, description, body, jsonld }) {
  const head = [
    `<title>${esc(title)}</title>`,
    `<meta name="description" content="${esc(description)}" />`,
    `<link rel="canonical" href="${SITE}${path}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:site_name" content="DomainVitals" />`,
    `<meta property="og:title" content="${esc(title)}" />`,
    `<meta property="og:description" content="${esc(description)}" />`,
    `<meta property="og:url" content="${SITE}${path}" />`,
    `<meta name="twitter:card" content="summary" />`,
    ...jsonld.map((j) => `<script type="application/ld+json">${JSON.stringify(j).replace(/</g, "\\u003c")}</script>`),
  ].join("\n    ");
  return shell
    .replace(/<meta name="description"[^>]*>\s*/, "") // drop the app-wide default first
    .replace(/<title>[^<]*<\/title>/, head)
    .replace('<div id="root"></div>', `<div id="root">${body}</div>`);
}

function write(path, html) {
  const dir = join(dist, path);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "index.html"), html);
}

const links = TOOLS.map((t) => `<li><a href="/tools/${t.slug}">${esc(t.name)}</a></li>`).join("");

for (const t of TOOLS) {
  const path = `/tools/${t.slug}`;
  const body = `<main><h1>${esc(t.h1)}</h1><p>${esc(t.lead)}</p>
<h2>About this tool</h2>${t.about.map((p) => `<p>${esc(p)}</p>`).join("")}
<h2>Questions</h2><dl>${t.faq.map((f) => `<dt>${esc(f.q)}</dt><dd>${esc(f.a)}</dd>`).join("")}</dl>
<h2>More free tools</h2><ul>${links}</ul></main>`;
  write(path, page({
    path,
    title: t.title,
    description: t.description,
    body,
    jsonld: [
      { "@context": "https://schema.org", "@type": "WebApplication", name: t.name, url: `${SITE}${path}`, applicationCategory: "UtilitiesApplication",
        operatingSystem: "Any", offers: { "@type": "Offer", price: "0", priceCurrency: "USD" }, publisher: { "@type": "Organization", name: "MSPoint LLC" } },
      { "@context": "https://schema.org", "@type": "FAQPage",
        mainEntity: t.faq.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) },
      { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: [
        { "@type": "ListItem", position: 1, name: "Free tools", item: `${SITE}/tools` },
        { "@type": "ListItem", position: 2, name: t.name, item: `${SITE}${path}` }] },
    ],
  }));
}

write("/tools", page({
  path: "/tools",
  title: "Free DNS, Email Authentication and SSL Tools | DomainVitals",
  description: "Free tools to check SPF, DKIM, DMARC, MX, DNS health, DNS propagation and SSL certificates, plus SPF and DMARC record generators.",
  body: `<main><h1>Free tools for mail authentication, DNS and SSL</h1><ul>${TOOLS.map((t) => `<li><a href="/tools/${t.slug}">${esc(t.name)}</a>: ${esc(t.lead)}</li>`).join("")}</ul></main>`,
  jsonld: [],
}));

const today = new Date().toISOString().slice(0, 10);
const urls = ["/", "/tools", ...TOOLS.map((t) => `/tools/${t.slug}`)];
writeFileSync(join(dist, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.map((u) => `  <url><loc>${SITE}${u}</loc><lastmod>${today}</lastmod></url>`).join("\n")}
</urlset>
`);
writeFileSync(join(dist, "robots.txt"), `User-agent: *
Allow: /$
Allow: /tools
Disallow: /api/
Disallow: /dashboard
Disallow: /domains
Disallow: /alerts
Disallow: /reports
Disallow: /settings
Disallow: /onboarding
Disallow: /invite

Sitemap: ${SITE}/sitemap.xml
`);
console.log(`prerendered ${TOOLS.length + 1} tool pages, sitemap.xml and robots.txt`);
