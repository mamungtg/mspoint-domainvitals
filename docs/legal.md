# Legal documents

The Terms of Service, Privacy Policy, Data Processing Addendum and subprocessor list live in `frontend/src/lib/legal.ts`. They are shown at `/legal/<slug>`, and prerendered at build time for search engines and for visitors without JavaScript.

- **Sign-up:** you must tick the agreement box. The backend rejects the request without `accept_terms`, and stores `terms_version` and `terms_accepted_at` on the user.
- **Changing a document:**
  1. Edit `legal.ts`.
  2. For a material change, bump `LEGAL_VERSION` and `LEGAL_UPDATED` there, and `LEGAL_TERMS_VERSION` in `config/settings/base.py`. A test checks that the two versions match.
  3. Email workspace owners at least 30 days before the change takes effect. Both the Terms and the DPA promise this notice.
- **New subprocessor:** add it to `SUBPROCESSORS`, then notify owners 30 days in advance. Add Sentry if `SENTRY_DSN` is turned on.
- **Mailboxes the documents refer to:** support@, privacy@ and security@mspointit.com.

The texts are a business-standard starting point. They are not legal advice, so have a lawyer review them before you start selling.
