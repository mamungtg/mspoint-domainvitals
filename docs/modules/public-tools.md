# Free public tools

Code: `frontend/src/lib/tools.ts` (catalogue), `frontend/src/pages/tools/`, `frontend/src/components/tools/`,
`frontend/scripts/prerender-tools.mjs`, `backend/common/public.py`. Tests: `backend/tests/test_public_tools.py`.

## Pages

`/tools` lists every tool; each one lives at `/tools/<slug>`:

| Slug | Backend |
| --- | --- |
| `domain-health-check` | `POST tools/check/` (`check: all`) |
| `spf-checker`, `dmarc-checker`, `dkim-checker`, `mx-lookup`, `dns-health-check` | `POST tools/check/` with that check |
| `ssl-checker` | `POST tools/ssl/` (port 443 or 8443; public addresses only) |
| `dns-propagation` | `POST tools/propagation/` |
| `spf-generator`, `dmarc-generator` | None: they run in the browser |

- **Shareable results:** the checked name is kept in `?q=`, so a result can be shared or bookmarked.
- **Call to action:** every result is followed by a "Monitor free for 14 days" (or "Add to my workspace") link.
- **Nothing is stored:** results are not saved anywhere.

## Access and limits

The endpoints extend `common.public.PublicToolView`:

- **Signed-in users:** the `tools` limit (30/hour per user).
- **Anonymous visitors:** `public_tools` (20/hour per IP) and `public_ssl` (10/hour per IP). CSRF is enforced for them too.

| Variable | Default |
| --- | --- |
| `THROTTLE_PUBLIC_TOOLS` | `20/hour` |
| `THROTTLE_PUBLIC_SSL` | `10/hour` |

### Client IP

Rate limits by IP only work when the app sees the visitor's real IP:

1. Traffic reaches nginx from the `cloudflared` container.
2. `snippets/cloudflare-realip.conf` trusts the Docker network and takes `CF-Connecting-IP`.
3. nginx then sets `X-Forwarded-For` to that single address.
4. DRF uses it with `NUM_PROXIES = 1`.

## SEO

`npm run build` runs `scripts/prerender-tools.mjs` after Vite. It writes these files:

- `dist/tools/<slug>/index.html`, with:
  - a real `<title>`, meta description and canonical URL
  - Open Graph tags
  - JSON-LD (WebApplication, FAQPage, BreadcrumbList)
  - the page text inside `#root`
- `sitemap.xml` and `robots.txt`.

nginx serves the prerendered files with `try_files $uri $uri/index.html /index.html`. `SITE_URL` (default `https://app.mspointit.com`) sets the absolute URLs.

To add a tool, add an entry to `TOOLS` in `lib/tools.ts` and, if it needs one, a widget in `ToolPage.tsx`. The page, the prerendered HTML and the sitemap follow from the catalogue.

### After launch

1. Add `https://app.mspointit.com` to Google Search Console.
2. Submit `https://app.mspointit.com/sitemap.xml`.
3. Link `/tools` from the marketing site.
