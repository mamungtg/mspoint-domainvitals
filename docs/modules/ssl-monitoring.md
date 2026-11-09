# SSL/TLS monitoring

Code: `backend/apps/ssl_monitor/`. Tests: `backend/tests/test_ssl.py`.

- Verifying a domain adds the apex and `www` as monitored hosts and queues their first scan immediately. Domains verified before this module existed are picked up the first time their certificates are listed.
- `scanner.scan()` resolves the host to public addresses only (IPv4 preferred), performs a verified handshake against the certifi bundle, then an unverified one to read the certificate even when it is invalid, and reads HSTS from an HTTPS response.
- `evaluate.evaluate()` produces findings: `tls_expired`, `tls_expires_soon` (≤ 7 days), `tls_expiring` (≤ 30 days), `tls_name_mismatch`, `tls_self_signed`, `tls_untrusted`, `tls_old_protocol`, `tls_weak_signature`, `tls_weak_key`, `tls_no_hsts`, `tls_short_hsts`.
- The certificates report shows a 12-month expiry calendar and flags hosts with a scan in progress as pending; the page polls until they finish.
